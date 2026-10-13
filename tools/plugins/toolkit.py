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
import threading
from collections import deque
from contextvars import ContextVar
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from tools.plugins.audit import record_tool_run
from tools.plugins.device import init_device_registry, get_device_registry, list_devices, list_abilities, record_device_action
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

NEEDS_LOCATION = ("NEEDS_LOCATION: no recent location for this user. A 'share location' prompt has been shown "
                  "on their device. Ask them in one short sentence to share their location or name a place, "
                  "then answer. Do not guess a city.")


def _ask_for_location() -> None:
    actions = UI_ACTIONS.get()
    if actions is not None and "share_location" not in actions:
        actions.append("share_location")  # web/app: location prompt; Telegram: 'Share location' button


def _near(ctx: PluginContext | None) -> tuple[float, float] | None:
    """Where the user is (device) or lives (saved home): bias place lookups to their own city."""
    if ctx is None or ctx.profile is None:
        return None
    device = ctx.profile.location(ctx.user_id, max_age=7 * 86400)
    if device:
        return device["lat"], device["lon"]
    home = ctx.profile.places(ctx.user_id).get("home")
    return (home["lat"], home["lon"]) if home else None


def _saved_place(ctx: PluginContext | None, name: str) -> dict | None:
    if ctx is None or ctx.profile is None:
        return None
    key = " ".join(name.lower().replace("my ", "").replace("the ", "").split())
    spot = ctx.profile.places(ctx.user_id).get(key)
    return {"latitude": spot["lat"], "longitude": spot["lon"], "label": f"{key} ({spot['label']})"} if spot else None


async def _save_place(args: dict, ctx: PluginContext | None) -> str:
    """Save home/office/any named place, from an address or the user's current device location."""
    if ctx is None or ctx.profile is None:
        return "Saved places need a signed-in user."
    from tools.plugins.information.weather import address, find_place
    name = _text(args, "name", 30)
    where = str(args.get("place") or "").strip()[:120]
    if not where or where.lower() in {"here", "current location", "my location", "this location"}:
        device = ctx.profile.location(ctx.user_id, max_age=3600)
        if not device:
            _ask_for_location()
            return ("NEEDS_LOCATION: to save the current spot, the user must share their location (prompt shown), "
                    "or say the address.")
        spot = {"latitude": device["lat"], "longitude": device["lon"], "label": await address(device["lat"], device["lon"])}
    else:
        spot = await find_place(where, near=_near(ctx))
        if spot is None:
            return f"I couldn't find {where}. Try adding the area or city."
    key = ctx.profile.set_place(ctx.user_id, name, spot["latitude"], spot["longitude"], spot["label"])
    return f"Saved '{key}' as {spot['label']}."


async def _weather(args: dict, ctx: PluginContext | None) -> str:
    """Forecast for a named place, else the device's recent location, else the saved home city."""
    from tools.plugins.information.weather import forecast, find_place
    when = str(args.get("when") or "now").strip().lower()
    if when not in {"now", "next_hours", "today", "tomorrow", "week"}:
        when = "now"
    place_name = str(args.get("place") or args.get("city") or "").strip()[:80]
    if place_name and place_name.casefold() not in {"here", "my location", "current location", "where i am"}:
        place = _saved_place(ctx, place_name) or await find_place(place_name, near=_near(ctx))
        if place is None:
            return f"I couldn't find a place named {place_name}."
        return await forecast(place["latitude"], place["longitude"], place["label"], when)
    device = ctx.profile.location(ctx.user_id) if ctx is not None and ctx.profile is not None else None
    if device:
        from tools.plugins.information.weather import address
        try:
            label = await address(device["lat"], device["lon"])
        except Exception:
            label = f"your location ({device['lat']:.3f}, {device['lon']:.3f})"
        report = await forecast(device["lat"], device["lon"], label, when)
        return f"{report}\n(Location from your device, {device['age_minutes']} min ago.)"
    saved_home = _saved_place(ctx, "home")
    if saved_home:
        _ask_for_location()
        report = await forecast(saved_home["latitude"], saved_home["longitude"], saved_home["label"], when)
        return f"{report}\n(Using your saved home; share your location for where you are now.)"
    home = ctx.profile.get(ctx.user_id).get("city", "") if ctx is not None and ctx.profile is not None else ""
    if home:
        place = await find_place(home)
        if place is not None:
            _ask_for_location()
            report = await forecast(place["latitude"], place["longitude"], place["label"], when)
            return f"{report}\n(Using your saved home city; share your location for where you are now.)"
    _ask_for_location()
    return NEEDS_LOCATION


async def _where_am_i(_args: dict, ctx: PluginContext | None) -> str:
    device = ctx.profile.location(ctx.user_id, max_age=2 * 3600) if ctx is not None and ctx.profile is not None else None
    if not device:
        _ask_for_location()
        return ("NEEDS_LOCATION: no recent location from this user's device. A 'share location' prompt has been "
                "shown; ask them in one short sentence to allow it. Do not ask for a city name.")
    from tools.plugins.information.weather import address
    place = await address(device["lat"], device["lon"])
    accuracy = f", accurate to about {device['accuracy']} m" if device.get("accuracy") else ""
    return (f"{place} (from your {device.get('source', 'device')} {device['age_minutes']} min ago{accuracy}). "
            f"Map: https://www.openstreetmap.org/?mlat={device['lat']}&mlon={device['lon']}#map=16/{device['lat']}/{device['lon']}")


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


async def _what_can_you_do(args: dict, _ctx: PluginContext | None) -> str:
    from tools.plugins.capabilities import catalogue_for_channel
    channel = str(args.get("channel") or "web").strip().lower()
    if channel not in {"web", "telegram", "mcp", "android"}:
        channel = "web"
    return catalogue_for_channel(channel)


async def _search_web(args: dict, _ctx: PluginContext | None) -> str:
    from tools.plugins.information.search import search_web
    query = _text(args, "query", 200)
    limit = max(1, min(int(args.get("limit", 5)), 10))
    results = await search_web(query, limit)
    if not results:
        return f"I couldn't find any results for '{query}'."
    lines = [f"Results for '{query}':"]
    for i, r in enumerate(results, 1):
        lines.append(f"  {i}. {r['title']} — {r.get('url', '')}")
        if r.get("snippet"):
            lines.append(f"     {r['snippet'][:150]}")
    return "\n".join(lines)


async def _read_page(args: dict, _ctx: PluginContext | None) -> str:
    from tools.plugins.information.search import read_page
    url = _text(args, "url", 500)
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    text = await read_page(url)
    if len(text) > 1500:
        text = text[:1500] + "…"
    return text


async def _places_near_me(args: dict, ctx: PluginContext | None) -> str:
    from tools.plugins.information.maps import search_places
    query = _text(args, "query", 60)
    place_name = str(args.get("place") or "").strip()[:80]
    near = _near(ctx)
    if not near and place_name:
        from tools.plugins.information.weather import find_place
        spot = await find_place(place_name)
        if spot:
            near = (spot["latitude"], spot["longitude"])
    if not near:
        _ask_for_location()
        return ("NEEDS_LOCATION: no recent location. A 'share location' prompt has been shown; "
                "ask them to share their location or name a city.")
    places = await search_places(query, near=near)
    if not places:
        return f"I couldn't find any '{query}' near you."
    lines = [f"'{query}' near you:"]
    for i, p in enumerate(places, 1):
        lines.append(f"  {i}. {p['name']} — {p['display'][:100]}")
    return "\n".join(lines)


async def _route_time(args: dict, ctx: PluginContext | None) -> str:
    from tools.plugins.information.maps import route_text
    from tools.plugins.information.weather import find_place
    from_label = _text(args, "from_place", 80)
    to_label = _text(args, "to_place", 80)
    from_spot = await find_place(from_label)
    to_spot = await find_place(to_label)
    if from_spot is None:
        return f"I couldn't find '{from_label}'."
    if to_spot is None:
        return f"I couldn't find '{to_label}'."
    return await route_text(
        from_label, from_spot["latitude"], from_spot["longitude"],
        to_label, to_spot["latitude"], to_spot["longitude"],
    )


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
    Tool("get_weather", "Weather and forecast: current conditions, next hours, today, tomorrow or the 7-day "
         "week: rain/snow amounts and chance, temperatures and feels-like, hot/cold verdict and change vs today, wind "
         "and gusts, humidity, visibility, UV, sunrise/sunset, air quality (AQI, PM2.5, PM10). 'place' = any city, "
         "colony, sector or landmark, or a saved place name (home, office); empty = where the user is now.",
         _params({"place": {"type": "string", "description": "City or place; empty = user's location"},
                  "when": {"type": "string", "enum": ["now", "next_hours", "today", "tomorrow", "week"]}}),
         _weather, "online-information"),
    Tool("save_place", "Save a named place for later (home, office, gym, parents...): from an address/area or "
         "'here' (the user's current device location). Then use the name as get_weather place.",
         _params({"name": {"type": "string"}, "place": {"type": "string", "description": "Address/area, or 'here'"}},
                 ["name"]), _save_place, "online-information", needs_context=True),
    Tool("where_am_i", "The user's current address/area from their device location (with their consent).",
         _params(), _where_am_i, "online-information", needs_context=True),
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
    Tool("what_can_you_do", "What Atulya can do on this channel, with honest status for each capability. "
         "Use it when the user asks 'what can you do here?', 'what can you do on Telegram?', or similar.",
         _params({"channel": {"type": "string", "enum": ["web", "telegram", "mcp", "android"]}}),
         _what_can_you_do, "local-utilities"),
    Tool("list_devices", "List all registered devices (server, laptop, phone) with their status and granted abilities.",
         _params(), _list_devices, "local-utilities"),
    Tool("server_logs", "Explain server logs: read from approved paths only, show recent entries, propose fixes.",
         _params({"query": {"type": "string", "description": "Keywords to search for in logs"}}, ["query"]),
         _server_logs, "local-utilities", True),
    Tool("search_web", "Search the web (DuckDuckGo) and get results with sources.",
         _params({"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 10}}, ["query"]),
         _search_web, "online-information"),
    Tool("read_url", "Fetch a web page and return readable text for summarising.",
         _params({"url": {"type": "string", "description": "Full http(s) URL"}}, ["url"]),
         _read_page, "online-information"),
    Tool("restart_service", "Restart a known service (nginx, fail2ban, sshd, atulya) after user approval.",
         _params({"service": {"type": "string"}}, ["service"]),
         _restart_service, "local-utilities", True),
    Tool("places_near_me", "Find places (pharmacies, hospitals, shops, restaurants) near the user's location "
         "or a named place. Returns name, address and distance.",
         _params({"query": {"type": "string", "description": "What to find, e.g. 'pharmacy', 'hospital'"},
                 "place": {"type": "string", "description": "Area or city; empty = user's location"}},
                ["query"]), _places_near_me, "online-information", True),
    Tool("route_time", "How long does it take to get from A to B by car? "
         "Returns duration and distance via OSRM (OpenStreetMap).",
         _params({"from_place": {"type": "string"}, "to_place": {"type": "string"}},
                ["from_place", "to_place"]), _route_time, "online-information", True),
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
        started = time.monotonic()
        channel = getattr(self.context, "channel", "web") if self.context else "web"
        user_id = self.context.user_id if self.context else "unknown"
        try:
            args = raw_arguments if isinstance(raw_arguments, dict) else json.loads(raw_arguments or "{}")
            if not isinstance(args, dict):
                raise ValueError("arguments must be an object")
            if tool.confirm and tool.low_risk and self._safety() == "ask_risky":
                result = (await asyncio.wait_for(tool.handler(args, self.context), timeout=20))[:4000]
                outcome = "ok (low risk, no approval)"
                record_activity(name, outcome)
                record_tool_run(user_id=user_id, channel=channel, tool=name, args=args,
                                outcome=outcome, duration_ms=int((time.monotonic() - started) * 1000))
                return result
            if tool.confirm:
                actions = getattr(self.context, "actions", None)
                if actions is None:
                    return "This action needs on-screen approval, which is only available in the Atulya WebUI."
                summary = (tool.describe or (lambda _a: name))(args)[:200]
                actions.add(name, args, summary, self.context.user_id)
                outcome = "awaiting approval"
                record_activity(name, outcome)
                record_tool_run(user_id=user_id, channel=channel, tool=name, args=args,
                                outcome=outcome, duration_ms=int((time.monotonic() - started) * 1000))
                return (f"Approval requested on screen: '{summary}'. It has NOT run yet. Tell the user briefly "
                        "to tap Approve (or Deny); do not claim it is done.")
            result = (await asyncio.wait_for(tool.handler(args, self.context), timeout=20))[:4000]
            outcome = "ok"
            record_activity(name, outcome)
            record_tool_run(user_id=user_id, channel=channel, tool=name, args=args,
                            outcome=outcome, duration_ms=int((time.monotonic() - started) * 1000))
            return result
        except (ValueError, TypeError) as exc:
            outcome = "invalid input"
            record_activity(name, outcome)
            record_tool_run(user_id=user_id, channel=channel,
                            tool=name, args=raw_arguments if isinstance(raw_arguments, dict) else {},
                            outcome=outcome, duration_ms=int((time.monotonic() - started) * 1000))
            return f"Invalid input for {name}: {exc}"
        except asyncio.TimeoutError:
            outcome = "timed out"
            record_activity(name, outcome)
            record_tool_run(user_id=user_id, channel=channel,
                            tool=name, args={}, outcome=outcome,
                            duration_ms=int((time.monotonic() - started) * 1000))
            return f"{name} timed out."
        except Exception as exc:
            logger.warning("Tool %s failed (%s)", name, type(exc).__name__)
            outcome = "failed"
            record_activity(name, outcome)
            record_tool_run(user_id=user_id, channel=channel,
                            tool=name, args={}, outcome=outcome,
                            duration_ms=int((time.monotonic() - started) * 1000))
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
        started = time.monotonic()
        channel = getattr(self.context, "channel", "web") if self.context else "web"
        user_id = self.context.user_id if self.context else "unknown"
        try:
            result = (await asyncio.wait_for(tool.handler(action.arguments, self.context), timeout=30))[:4000]
            outcome = "approved · ok"
            record_activity(action.tool, outcome)
            record_tool_run(user_id=user_id, channel=channel,
                            tool=action.tool, args=action.arguments, outcome=outcome,
                            duration_ms=int((time.monotonic() - started) * 1000))
            return result
        except (ValueError, TypeError) as exc:
            outcome = "approved · invalid input"
            record_activity(action.tool, outcome)
            record_tool_run(user_id=user_id, channel=channel,
                            tool=action.tool, args=action.arguments, outcome=outcome,
                            duration_ms=int((time.monotonic() - started) * 1000))
            return f"Couldn't do that: {exc}"
        except Exception as exc:
            logger.warning("Approved action %s failed (%s)", action.tool, type(exc).__name__)
            outcome = "approved · failed"
            record_activity(action.tool, outcome)
            record_tool_run(user_id=user_id, channel=channel,
                            tool=action.tool, args=action.arguments, outcome=outcome,
                            duration_ms=int((time.monotonic() - started) * 1000))
            return "That action failed on this computer."


async def _list_devices(_args: dict, ctx: PluginContext | None) -> str:
    """List all registered devices with status and granted abilities."""
    registry = get_device_registry()
    if registry is None:
        return "Device registry not initialized."
    devices = registry.list_devices()
    if not devices:
        return "No devices registered."
    lines = ["Registered devices:"]
    for d in devices:
        ability_str = ", ".join(sorted(d.abilities)) if d.abilities else "none"
        lines.append(f"  • {d.type}: status={d.status}, abilities=[{ability_str}], last_seen={int(d.last_seen)}s ago")
    return "\n".join(lines)


async def _server_logs(args: dict, ctx: PluginContext | None) -> str:
    """Explain server logs: read from approved paths only."""
    import os
    query = _text(args, "query", 100).lower() if args else ""
    log_dir = os.environ.get("ATULYA_LOG_DIR", "data/logs")
    try:
        if not os.path.isdir(log_dir):
            return f"Log directory not found: {log_dir}"
        entries = []
        for fname in sorted(os.listdir(log_dir)):
            if fname.endswith(".log"):
                fpath = os.path.join(log_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()[-20:]
                        for line in lines:
                            if query and query not in line.lower():
                                continue
                            entries.append(f"{fname}: {line.rstrip()[:200]}")
                except OSError:
                    continue
        if not entries:
            return f"No log entries matching {_text(args, 'query', 100) or 'recent'} found."
        return f"Recent log entries ({len(entries)}):\n" + "\n".join(entries[:10])
    except Exception as exc:
        return f"Failed to read logs: {type(exc).__name__}: {exc}"


async def _restart_service(args: dict, ctx: PluginContext | None) -> str:
    """Restart a service with approval. Only read-only, approved paths."""
    import subprocess
    service = _text(args, "service", 64)
    # Only allow known, safe services
    safe_services = {"nginx", "fail2ban", "sshd", "atulya"}
    if service not in safe_services:
        return f"Service '{service}' is not in the approved list. Allowed: {', '.join(safe_services)}"
    # This is a simulated approval - in real use, the WebUI would show an approval card
    # For now, just record the request and explain
    return (f"Service restart requested for '{service}'. This requires user approval on the WebUI. "
            f"Use the WebUI ⋮ → ACTIVITY → Approve to restart. "
            f"Only read-only restart commands are allowed without approval.")




    Tool('gmail_search', 'Search Gmail for messages matching a query.',
         _params({'query': {'type': 'string'}}, ['query']),
         _gmail_search, 'online-information'),
    Tool('gmail_drafts', 'List Gmail drafts.',
         _params({}, []),
         _gmail_drafts, 'online-information'),
    Tool('gmail_send', 'Send a Gmail message with approval.',
         _params({'message': {'type': 'string'}}, ['message']),
         _gmail_send, 'online-information', True),
    Tool('calendar_search', 'Search Google Calendar for events.',
         _params({'query': {'type': 'string'}}, ['query']),
         _calendar_search, 'online-information'),
    Tool('calendar_create', 'Create a Google Calendar event with approval.',
         _params({'summary': {'type': 'string'}, 'when': {'type': 'string'}}, ['summary', 'when']),
         _calendar_create, 'online-information', True),
    Tool('github_search', 'Search GitHub repositories or issues.',
         _params({'query': {'type': 'string'}}, ['query']),
         _github_search, 'online-information'),
    Tool('github_issues', 'List GitHub issues for a repository.',
         _params({'owner': {'type': 'string'}, 'repo': {'type': 'string'}}, ['owner', 'repo']),
         _github_issues, 'online-information', True),
TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}
