"""Model-callable tools shared by chat, Telegram, and the MCP server.

Each tool belongs to a plugin manifest, so disabling a plugin in the WebUI also
removes its tools from the model and from MCP. Tools take validated JSON
arguments and return plain text; they never raise to the caller.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
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


TOOLS: tuple[Tool, ...] = (
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
    Tool("use_skill", "Load a named multi-step skill (workflow instructions) and follow it.",
         _params({"name": {"type": "string"}}, ["name"]), _use_skill, "skills"),
)


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
                 "(weather, news, time, maths, the user's saved memories and meetings). Never invent tool results."]
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
            return (await asyncio.wait_for(tool.handler(args, self.context), timeout=20))[:4000]
        except (ValueError, TypeError) as exc:
            return f"Invalid input for {name}: {exc}"
        except asyncio.TimeoutError:
            return f"{name} timed out."
        except Exception as exc:
            logger.warning("Tool %s failed (%s)", name, type(exc).__name__)
            return f"{name} is unavailable right now."
