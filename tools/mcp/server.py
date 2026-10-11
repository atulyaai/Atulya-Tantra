"""Optional MCP server exposing Atulya's public plugin tools and every skill.

Tools come from the same plugin set the assistant uses (tools/plugins/), and
plugins disabled in the WebUI are left out. Each tools/skills/<name>/SKILL.md
is published as an MCP prompt. Private data (memory, calendar, history) is
never exposed here.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable

from mcp.server.mcpserver import MCPServer

from atulya.settings import Settings
from tools.plugins.information.news import headlines as get_headlines
from tools.plugins.information.weather import weather as get_weather
from tools.plugins.toolkit import list_skills, read_skill
from tools.plugins.utilities.calculator import calculate as run_calculation
from tools.plugins.utilities.clock import current_time

WeatherLookup = Callable[[str], Awaitable[str]]
HeadlinesLookup = Callable[[int], Awaitable[str]]
logger = logging.getLogger(__name__)


def _disabled_plugins() -> set[str]:
    try:
        path = Settings.from_environment().data_dir / "plugin_settings.json"
        saved = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {key for key, enabled in saved.items() if enabled is False} if isinstance(saved, dict) else set()


def create_server(
    weather_lookup: WeatherLookup = get_weather,
    headlines_lookup: HeadlinesLookup = get_headlines,
    *,
    disabled_plugins: set[str] | None = None,
) -> MCPServer:
    """Create the explicitly allowlisted Atulya MCP server."""
    disabled = _disabled_plugins() if disabled_plugins is None else disabled_plugins
    server = MCPServer(
        "Atulya",
        instructions="Public information and utility tools plus Atulya skills (as prompts). "
                     "No account, memory, or device data is exposed.",
    )

    if "online-information" not in disabled:
        @server.tool()
        async def weather(city: str) -> str:
            """Get current weather for a city using Open-Meteo."""
            try:
                return await weather_lookup(city)
            except Exception as exc:
                logger.warning("MCP weather lookup failed (%s)", type(exc).__name__)
                return "Weather is unavailable for that city right now. Check the city name or try again later."

        @server.tool()
        async def news_headlines(limit: int = 5) -> str:
            """Get up to ten current BBC News headlines."""
            bounded_limit = max(1, min(int(limit), 10))
            try:
                return await headlines_lookup(bounded_limit)
            except Exception as exc:
                logger.warning("MCP news lookup failed (%s)", type(exc).__name__)
                return "News headlines are unavailable right now. Try again later."

    if "local-utilities" not in disabled:
        @server.tool()
        def get_time() -> str:
            """Current local date and time on the Atulya host."""
            return current_time()

        @server.tool()
        def calculate(expression: str) -> str:
            """Evaluate an arithmetic expression exactly (+ - * / % and parentheses)."""
            try:
                return run_calculation(expression[:200])
            except ValueError as exc:
                return str(exc)

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
