"""Optional MCP server exposing Atulya's shared tool registry and skills.

Tools come from the same plugin set the assistant uses (tools/plugins/), and
plugins disabled in the WebUI are left out. Each tools/skills/<name>/SKILL.md
is published as an MCP prompt. Private data (memory, calendar, history) is
never exposed here.

The MCP server no longer has its own copies of weather, news, time or
calculate — it exposes the same Tool handlers from toolkit.TOOLS, so there is
one shared path for all channels (PLT-01/03).
"""
from __future__ import annotations

import logging

from mcp.server.mcpserver import MCPServer

from atulya.settings import Settings
from tools.plugins.toolkit import TOOLS, TOOLS_BY_NAME, Toolbox, list_skills, read_skill

logger = logging.getLogger(__name__)


def _disabled_plugins() -> set[str]:
    import json
    try:
        path = Settings.from_environment().data_dir / "plugin_settings.json"
        saved = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {key for key, enabled in saved.items() if enabled is False} if isinstance(saved, dict) else set()


def create_server(
    *,
    disabled_plugins: set[str] | None = None,
) -> MCPServer:
    """Create the explicitly allowlisted Atulya MCP server.

    Exposes the shared toolkit tool handlers (not duplicates) plus skills as prompts.
    Each wrapper has an explicit signature so the MCP SDK can generate the schema;
    the actual logic lives in toolkit.py — one source of truth.
    """
    disabled = _disabled_plugins() if disabled_plugins is None else disabled_plugins
    server = MCPServer(
        "Atulya",
        instructions="Public information and utility tools plus Atulya skills (as prompts). "
                     "No account, memory, or device data is exposed.",
    )

    toolbox = Toolbox((tool for tool in TOOLS if tool.plugin_id not in disabled), public_only=True)

    def shared_tool(name):
        # Signatures remain SDK adapters; descriptions and execution are shared.
        return server.tool(name=name, description=TOOLS_BY_NAME[name].description)

    if "online-information" not in disabled:
        @shared_tool("get_weather")
        async def get_weather(place: str = "", when: str = "now") -> str:
            """Weather and forecast: current conditions, next hours, today, tomorrow or the 7-day week."""
            return await toolbox.call("get_weather", {"place": place, "when": when})

        @shared_tool("get_news")
        async def get_news(limit: int = 5) -> str:
            """Latest BBC News headlines."""
            return await toolbox.call("get_news", {"limit": limit})

    if "local-utilities" not in disabled:
        @shared_tool("get_time")
        async def get_time() -> str:
            """Current local date and time on the host."""
            return await toolbox.call("get_time", {})

        @shared_tool("calculate")
        async def calculate(expression: str) -> str:
            """Evaluate an arithmetic expression exactly (+ - * / % and parentheses)."""
            return await toolbox.call("calculate", {"expression": expression})

        @shared_tool("what_can_you_do")
        async def what_can_you_do(channel: str = "mcp") -> str:
            """What Atulya can do on this channel, with honest status for each capability."""
            return await toolbox.call("what_can_you_do", {})

    for skill in list_skills():
        _register_skill_prompt(server, skill["name"], skill["description"])

    return server


def _register_skill_prompt(server: MCPServer, name: str, description: str) -> None:
    def skill_prompt(request: str = "") -> str:
        body = read_skill(name) or ""
        return f"{body}\n\nUser request: {request}" if request else body

    server.prompt(name=name.replace("-", "_"), description=description or f"Atulya skill: {name}")(skill_prompt)


def main() -> None:
    """Run the MCP server over stdio for local MCP hosts."""
    create_server().run()


if __name__ == "__main__":
    main()
