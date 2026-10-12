"""Model-callable tools shared by chat, Telegram, and the MCP server.

Each tool belongs to a plugin manifest, so disabling a plugin in the WebUI also
removes its tools from the model and from MCP. Tools take validated JSON
arguments and return plain text; they never raise to the caller.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import secrets
import time
from collections import deque
from contextvars import ContextVar
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from tools.plugins.registry import PluginContext

logger = logging.getLogger(__name__)
SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"

ToolHandler = Callable[[dict, PluginContext | None], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    parameters: dict
    handler: ToolHandler
    plugin_id: str
    needs_context: bool = False
    # Side-effecting tools: the call only queues a request the user must approve.
    confirm: bool = False
    describe: Callable[[dict], str] | None = None
    # Low-risk confirm tools run without asking when the user's profile safety is "ask_risky".
    low_risk: bool = False

    def schema(self) -> dict:
        """OpenAI-style function definition, accepted by every supported provider."""
        return {"type": "function", "function": {
            "name": self.name, "description": self.description, "parameters": self.parameters,
        }}


def _params(properties: dict | None = None, required: Iterable[str] = ()) -> dict:
    return {"type": "object", "properties": properties or {}, "required": list(required),
            "additionalProperties": False}


def _text(args: dict, key: str, limit: int = 300) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{key}' is required")
    return value.strip()[:limit]


# --- information -----------------------------------------------------------

async def _weather(args: dict, _ctx: PluginContext | None) -> str:
    from tools.plugins.information.weather import weather
    return await weather(_text(args, "city", 80))


async def _news(args: dict, _ctx: PluginContext | None) -> str:
    from tools.plugins.information.news import headlines
    try:
        limit = max(1, min(int(args.get("limit", 5)), 10))
    except (TypeError, ValueError):
        limit = 5
    return await headlines(limit)


# --- utilities -------------------------------------------------------------

async def _time(_args: dict, _ctx: PluginContext | None) -> str:
    from tools.plugins.utilities.clock import current_time
    return current_time()


async def _calculate(args: dict, _ctx: PluginContext | None) -> str:
    from tools.plugins.utilities.calculator import calculate
    return calculate(_text(args, "expression", 200))


# --- personal memory ---------------------------------------------------------

async def _remember(args: dict, ctx: PluginContext | None) -> str:
    fact = _text(args, "fact", 500)
    created = await asyncio.to_thread(ctx.memory.remember, ctx.owner_id, fact, user_id=ctx.user_id)
    return "Saved to memory." if created else "That is already in memory."


async def _forget(args: dict, ctx: PluginContext | None) -> str:
    deleted = await asyncio.to_thread(ctx.memory.forget, ctx.owner_id, _text(args, "query", 200), user_id=ctx.user_id)
    return f"Forgot {deleted} matching memory item(s)." if deleted else "No matching memory found."


async def _recall(args: dict, ctx: PluginContext | None) -> str:
    query = str(args.get("query") or "").strip()[:200] or "everything"
    facts = await asyncio.to_thread(ctx.memory.relevant, ctx.owner_id, query, user_id=ctx.user_id)
    return "No saved memories match." if not facts else "\n".join(f"- {fact}" for fact in facts)


# --- calendar --------------------------------------------------------------

async def _add_meeting(args: dict, ctx: PluginContext | None) -> str:
    from tools.plugins.productivity.commands import _parse_calendar_datetime
    title = _text(args, "title", 300)
    starts_at = _parse_calendar_datetime(_text(args, "when", 80))
    event = await asyncio.to_thread(ctx.calendar.add, ctx.owner_id, title, starts_at, 15, user_id=ctx.user_id)
    local = datetime.fromisoformat(event["starts_at"]).astimezone().strftime("%b %d at %I:%M %p %Z")
    return f"Added '{event['title']}' on {local} with a 15-minute reminder."


async def _list_meetings(_args: dict, ctx: PluginContext | None) -> str:
    events = await asyncio.to_thread(ctx.calendar.list, ctx.owner_id, 10, user_id=ctx.user_id)
    if not events:
        return "No upcoming meetings."
    return "\n".join(
        f"- {datetime.fromisoformat(item['starts_at']).astimezone().strftime('%a %b %d, %I:%M %p')}: {item['title']}"
        for item in events
    )


# --- past conversations ------------------------------------------------------

async def _search_chats(args: dict, ctx: PluginContext | None) -> str:
    if ctx.history is None:
        return "Past conversations are not available on this channel."
    rows = await asyncio.to_thread(ctx.history.search, _text(args, "query", 200), 8, ctx.user_id)
    if not rows:
        return "No past messages match."
    return "\n".join(
        f"- [{row['created_at'][:16]}] {row['role']}: {row['content'][:300]}" for row in rows
    )


# --- profile ------------------------------------------------------------------

async def _update_profile(args: dict, ctx: PluginContext | None) -> str:
    from atulya.profiles import VOICE_EDITABLE

    if ctx.profile is None:
        return "Profiles are not available on this channel."
    field = _text(args, "field", 30)
    if field not in VOICE_EDITABLE:
        return f"'{field}' can't be changed by chat. Editable: {', '.join(sorted(VOICE_EDITABLE))}."
    profile = await asyncio.to_thread(ctx.profile.update, ctx.user_id, {field: _text(args, "value", 600)})
    return f"Saved: {field} = {profile[field]}"


# --- owner-only status ------------------------------------------------------------

# Set by the server at startup: returns a dict describing Atulya's live health.
STATUS_PROVIDER: Callable[[], dict] | None = None


def _owner_only(ctx: PluginContext | None) -> str | None:
    return None if ctx is not None and ctx.user_id == "admin" else "Only the owner can see system status."


async def _atulya_status(_args: dict, ctx: PluginContext | None) -> str:
    if (denied := _owner_only(ctx)) or STATUS_PROVIDER is None:
        return denied or "Status is unavailable."
    data = await asyncio.to_thread(STATUS_PROVIDER)
    return "\n".join(f"- {key}: {value}" for key, value in data.items())


def _server_list() -> list[tuple[str, str, str]]:
    """ATULYA_SERVERS="atulvij=ubuntu@1.2.3.4=C:/keys/a.key;sublimew=ubuntu@5.6.7.8=C:/keys/b.key" """
    servers = []
    for item in os.environ.get("ATULYA_SERVERS", "").split(";"):
        parts = [part.strip() for part in item.split("=")]
        if len(parts) == 3 and all(parts):
            servers.append((parts[0], parts[1], parts[2]))
    return servers


def _ssh_status(target: str, key: str) -> str:
    import subprocess

    # Fixed, read-only commands only; the model cannot pass anything to the server.
    command = ("uptime -p; echo load $(cut -d' ' -f1-3 /proc/loadavg); "
               "df -h / | awk 'NR==2{print \"disk \" $5 \" used of \" $2}'; "
               "free -m | awk '/Mem:/{printf \"memory %d%% used\\n\", $3*100/$2}'; "
               "echo nginx $(systemctl is-active nginx); echo fail2ban $(systemctl is-active fail2ban)")
    try:
        result = subprocess.run(["ssh", "-i", key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
                                 "-o", "StrictHostKeyChecking=accept-new", target, command],
                                capture_output=True, text=True, timeout=25)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"unreachable ({type(exc).__name__})"
    return "; ".join(result.stdout.split("\n")).strip("; ") if result.returncode == 0 else "unreachable"


async def _server_status(_args: dict, ctx: PluginContext | None) -> str:
    if denied := _owner_only(ctx):
        return denied
    servers = _server_list()
    if not servers:
        return "No servers are configured. Set ATULYA_SERVERS in .env."
    results = await asyncio.gather(*(asyncio.to_thread(_ssh_status, target, key) for _name, target, key in servers))
    return "\n".join(f"- {name}: {result}" for (name, _t, _k), result in zip(servers, results))


# --- PC control (approval required) ---------------------------------------------

def _pc(fn_name: str):
    async def run(args: dict, ctx: PluginContext | None) -> str:
        from tools.plugins.system import actions

        if fn_name == "take_screenshot":
            data_dir = getattr(ctx.actions, "data_dir", Path("data"))
            return await asyncio.to_thread(actions.take_screenshot, data_dir)
        if fn_name == "media_control":
            return await asyncio.to_thread(actions.media_control, _text(args, "command", 20), int(args.get("steps", 1) or 1))
        key = {"open_app": "name", "open_url": "url", "search_files": "query"}[fn_name]
        return await asyncio.to_thread(getattr(actions, fn_name), _text(args, key, 300))
    return run


def _describe_media(args: dict) -> str:
    command = str(args.get("command", "")).replace("_", " ")
    steps = args.get("steps")
    return f"Media: {command}" + (f" ×{steps}" if steps and "volume" in command else "")


# --- skills ----------------------------------------------------------------

def list_skills() -> list[dict[str, str]]:
    """Read SKILL.md front matter from tools/skills/<name>/SKILL.md."""
    skills = []
    for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta = dict(re.findall(r"^(name|description):\s*(.+)$", text.split("---", 2)[1] if text.startswith("---") else "", re.M))
        name = meta.get("name", path.parent.name).strip()
        if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", name):
            skills.append({"name": name, "description": meta.get("description", "").strip(), "path": str(path)})
    return skills


def read_skill(name: str) -> str | None:
    for skill in list_skills():
        if skill["name"] == name:
            text = Path(skill["path"]).read_text(encoding="utf-8")
            return text.split("---", 2)[2].strip() if text.startswith("---") else text
    return None


async def _use_skill(args: dict, _ctx: PluginContext | None) -> str:
    name = _text(args, "name", 64)
    body = read_skill(name)
    if body is None:
        return "Unknown skill. Available: " + ", ".join(s["name"] for s in list_skills())
    return f"Follow these skill instructions using your other tools:\n\n{body}"


# Screen actions the WebUI performs itself (hide chat, new chat, camera, ...). The chat stream drains this
# per-request list and sends each action to the browser, so any phrasing of a request works, not only the
# fixed phrases the page recognizes instantly.
UI_ACTIONS: ContextVar[list | None] = ContextVar("atulya_ui_actions", default=None)
SCREEN_ACTIONS = ("hide_chat", "show_chat", "conversation_mode", "new_chat", "open_history", "camera_on",
                  "camera_off", "voice_replies_on", "voice_replies_off", "reload", "open_settings")


async def _screen_control(args: dict, _ctx: PluginContext | None) -> str:
    action = _text(args, "action", 32)
    if action not in SCREEN_ACTIONS:
        return "Unknown screen action. Use one of: " + ", ".join(SCREEN_ACTIONS)
    actions = UI_ACTIONS.get()
    if actions is None:
        return "Screen controls only work in the Atulya app or website, not in this channel."
    actions.append(action)
    return f"Done: {action.replace('_', ' ')} (the screen updates now). Confirm briefly."


TOOLS: tuple[Tool, ...] = (
    Tool("screen_control", "Change the Atulya screen the user is looking at: hide or show the chat, "
         "conversation mode (full-screen hologram, hands-free), new chat, open history or settings, camera "
         "on/off, spoken replies on/off, reload. Use it whenever the user asks to change what they see.",
         _params({"action": {"type": "string", "enum": list(SCREEN_ACTIONS)}}, ["action"]),
         _screen_control, "local-utilities"),
    Tool("get_weather", "Current weather for a city (Open-Meteo).",
         _params({"city": {"type": "string", "description": "City name, e.g. 'Delhi'"}}, ["city"]),
         _weather, "online-information"),
    Tool("get_news", "Latest BBC News headlines.",
         _params({"limit": {"type": "integer", "minimum": 1, "maximum": 10}}),
         _news, "online-information"),
    Tool("get_time", "Current local date and time on the host.", _params(), _time, "local-utilities"),
    Tool("calculate", "Evaluate an arithmetic expression exactly (+ - * / % parentheses).",
         _params({"expression": {"type": "string"}}, ["expression"]), _calculate, "local-utilities"),
    Tool("remember_fact", "Save a fact the user explicitly asked you to remember.",
         _params({"fact": {"type": "string"}}, ["fact"]), _remember, "personal-memory", True),
    Tool("forget_fact", "Delete saved memories matching a query, when the user asks you to forget.",
         _params({"query": {"type": "string"}}, ["query"]), _forget, "personal-memory", True),
    Tool("recall_memories", "Search facts the user saved earlier.",
         _params({"query": {"type": "string"}}), _recall, "personal-memory", True),
    Tool("add_meeting", "Add a calendar meeting with a reminder 15 minutes before.",
         _params({"title": {"type": "string"},
                  "when": {"type": "string", "description": "ISO 'YYYY-MM-DD HH:MM' or 'today/tomorrow at 3pm'"}},
                 ["title", "when"]), _add_meeting, "productivity-calendar", True),
    Tool("list_meetings", "List upcoming calendar meetings.", _params(), _list_meetings, "productivity-calendar", True),
    Tool("search_past_chats", "Search the user's earlier conversations for something they said or asked before.",
         _params({"query": {"type": "string", "description": "Key words to look for"}}, ["query"]),
         _search_chats, "personal-memory", True),
    Tool("atulya_status", "Owner only: Atulya's own live health (model, voice, Telegram, tunnel, CPU/RAM, uptime, version).",
         _params(), _atulya_status, "local-utilities", True),
    Tool("server_status", "Owner only: read-only health of the owner's web servers (uptime, load, disk, memory, nginx).",
         _params(), _server_status, "local-utilities", True),
    Tool("open_app", "Open an installed application on the user's computer (asks the user first).",
         _params({"name": {"type": "string", "description": "App name, e.g. 'Spotify', 'Calculator'"}}, ["name"]),
         _pc("open_app"), "pc-control", True, True, lambda a: f"Open app: {a.get('name', '')}"),
    Tool("open_url", "Open a web page in the computer's browser (asks the user first).",
         _params({"url": {"type": "string", "description": "Full http(s) URL"}}, ["url"]),
         _pc("open_url"), "pc-control", True, True, lambda a: f"Open website: {a.get('url', '')}"),
    Tool("update_profile", "Save a lasting user preference: voice (male/female speaking voice), "
         "assistant_nickname (what this user wants to call you, "
         "e.g. 'call yourself Tony'), preferred_name, city, language "
         "(auto, english, hindi, hinglish, marathi, tamil, spanish, … lowercase name), tone "
         "(atulya/friendly/formal/brief/witty), length (short/normal/detailed), work_style, or about.",
         _params({"field": {"type": "string", "enum": ["voice", "assistant_nickname", "preferred_name", "city", "language", "tone", "length",
                                                        "work_style", "about"]},
                  "value": {"type": "string"}}, ["field", "value"]),
         _update_profile, "personal-memory", True),
    Tool("search_files", "Find files by name in the user's Desktop, Documents, Downloads, Pictures, Music and Videos (asks first).",
         _params({"query": {"type": "string", "description": "Words in the file name"}}, ["query"]),
         _pc("search_files"), "pc-control", True, True, lambda a: f"Search files for: {a.get('query', '')}", low_risk=True),
    Tool("media_control", "Play/pause, next/previous track, volume up/down, or mute on the computer (asks first).",
         _params({"command": {"type": "string", "enum": ["play_pause", "next", "previous", "volume_up", "volume_down", "mute"]},
                  "steps": {"type": "integer", "minimum": 1, "maximum": 10}}, ["command"]),
         _pc("media_control"), "pc-control", True, True, _describe_media, low_risk=True),
    Tool("take_screenshot", "Capture the computer's screen to a file (asks first).", _params(),
         _pc("take_screenshot"), "pc-control", True, True, lambda a: "Take a screenshot"),
    Tool("use_skill", "Load a named multi-step skill (workflow instructions) and follow it.",
         _params({"name": {"type": "string"}}, ["name"]), _use_skill, "skills"),
)


@dataclass
class PendingAction:
    id: str
    tool: str
    arguments: dict
    summary: str
    user_id: str
    created: float = field(default_factory=time.monotonic)


class ActionQueue:
    """Side-effecting tool calls wait here until the signed-in user approves them.

    One queue per app; each request gets a view that remembers which actions it
    created so the WebUI stream can show Approve/Deny buttons for them.
    """

    TTL_SECONDS = 180

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self._pending: dict[str, PendingAction] = {}

    def add(self, tool: str, arguments: dict, summary: str, user_id: str) -> PendingAction:
        self._expire()
        action = PendingAction(secrets.token_urlsafe(12), tool, arguments, summary, user_id)
        self._pending[action.id] = action
        return action

    def take(self, action_id: str, user_id: str) -> PendingAction | None:
        self._expire()
        action = self._pending.get(action_id)
        if action is None or action.user_id != user_id:
            return None
        return self._pending.pop(action_id)

    def _expire(self) -> None:
        cutoff = time.monotonic() - self.TTL_SECONDS
        for key in [key for key, item in self._pending.items() if item.created < cutoff]:
            del self._pending[key]

    def view(self) -> "ActionView":
        return ActionView(self)


class ActionView:
    def __init__(self, queue: ActionQueue) -> None:
        self.queue = queue
        self.data_dir = queue.data_dir
        self.created: list[PendingAction] = []
        self._sent = 0

    def add(self, tool: str, arguments: dict, summary: str, user_id: str) -> PendingAction:
        action = self.queue.add(tool, arguments, summary, user_id)
        self.created.append(action)
        return action

    def drain_new(self) -> list[PendingAction]:
        new = self.created[self._sent:]
        self._sent = len(self.created)
        return new


# Recent tool activity for the status panel (names and outcomes only, no arguments).
TOOL_ACTIVITY: deque[dict] = deque(maxlen=12)


def record_activity(name: str, outcome: str) -> None:
    TOOL_ACTIVITY.append({"tool": name, "outcome": outcome, "at": datetime.now().astimezone().isoformat(timespec="seconds")})


class Toolbox:
    """The enabled tool set for one request, with bounded, logged execution."""

    MAX_ROUNDS = 4

    def __init__(self, tools: Iterable[Tool], context: PluginContext | None = None) -> None:
        self._tools = {tool.name: tool for tool in tools if context is not None or not tool.needs_context}
        self.context = context

    @classmethod
    def for_registry(cls, registry, context: PluginContext | None) -> "Toolbox":
        enabled = {item["id"] for item in registry.manifests if item.get("enabled")} | {"skills"}
        return cls((tool for tool in TOOLS if tool.plugin_id in enabled), context)

    def __bool__(self) -> bool:
        return bool(self._tools)

    @property
    def schemas(self) -> list[dict]:
        return [tool.schema() for tool in self._tools.values()]

    def instructions(self) -> str:
        skills = list_skills()
        lines = ["You can call tools. Use them whenever they give fresher or more exact answers than memory "
                 "(weather, news, time, maths, the user's saved memories, meetings, and earlier conversations). "
                 "Never invent tool results. Computer actions (apps, websites, files, media, screenshots) only "
                 "run after the user taps Approve; say so instead of claiming they happened."]
        if skills:
            lines.append("Skills available through use_skill: " + "; ".join(
                f"{s['name']} ({s['description']})" for s in skills))
        return "\n".join(lines)

    async def call(self, name: str, raw_arguments: str | dict) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Tool '{name}' is not available."
        try:
            args = raw_arguments if isinstance(raw_arguments, dict) else json.loads(raw_arguments or "{}")
            if not isinstance(args, dict):
                raise ValueError("arguments must be an object")
            if tool.confirm and tool.low_risk and self._safety() == "ask_risky":
                result = (await asyncio.wait_for(tool.handler(args, self.context), timeout=20))[:4000]
                record_activity(name, "ok (low risk, no approval)")
                return result
            if tool.confirm:
                actions = getattr(self.context, "actions", None)
                if actions is None:
                    return "This action needs on-screen approval, which is only available in the Atulya WebUI."
                summary = (tool.describe or (lambda _a: name))(args)[:200]
                actions.add(name, args, summary, self.context.user_id)
                record_activity(name, "awaiting approval")
                return (f"Approval requested on screen: '{summary}'. It has NOT run yet. Tell the user briefly "
                        "to tap Approve (or Deny); do not claim it is done.")
            result = (await asyncio.wait_for(tool.handler(args, self.context), timeout=20))[:4000]
            record_activity(name, "ok")
            return result
        except (ValueError, TypeError) as exc:
            record_activity(name, "invalid input")
            return f"Invalid input for {name}: {exc}"
        except asyncio.TimeoutError:
            record_activity(name, "timed out")
            return f"{name} timed out."
        except Exception as exc:
            logger.warning("Tool %s failed (%s)", name, type(exc).__name__)
            record_activity(name, "failed")
            return f"{name} is unavailable right now."

    def _safety(self) -> str:
        store = getattr(self.context, "profile", None)
        if store is None:
            return "ask_all"
        try:
            return store.get(self.context.user_id).get("safety", "ask_all")
        except Exception:
            return "ask_all"

    async def run_approved(self, action: PendingAction) -> str:
        """Execute an action the user approved (bypasses the confirmation step only)."""
        tool = TOOLS_BY_NAME.get(action.tool)
        if tool is None:
            return "That action is no longer available."
        try:
            result = (await asyncio.wait_for(tool.handler(action.arguments, self.context), timeout=30))[:4000]
            record_activity(action.tool, "approved · ok")
            return result
        except (ValueError, TypeError) as exc:
            record_activity(action.tool, "approved · invalid input")
            return f"Couldn't do that: {exc}"
        except Exception as exc:
            logger.warning("Approved action %s failed (%s)", action.tool, type(exc).__name__)
            record_activity(action.tool, "approved · failed")
            return "That action failed on this computer."


TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}
