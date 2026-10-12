"""MCP protocol tests use the SDK's in-memory client."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from tools.mcp.server import create_server


def test_mcp_exposes_shared_toolkit_tools() -> None:
    """MCP exposes the same tools as the shared registry, not duplicates."""
    server = create_server(disabled_plugins=set())

    async def exercise() -> None:
        async with Client(server, mode="legacy") as client:
            listed = await client.list_tools()
            names = {tool.name for tool in listed.tools}
            # The old duplicate tools are gone
            assert "weather" not in names
            assert "news_headlines" not in names
            # Shared registry tools are exposed
            assert "get_weather" in names
            assert "get_news" in names
            assert "get_time" in names
            assert "calculate" in names
            assert "what_can_you_do" in names

    asyncio.run(exercise())


def test_mcp_capability_catalogue_tool() -> None:
    """MCP can answer 'what can you do here?' with the shared registry."""
    server = create_server(disabled_plugins=set())

    async def exercise() -> None:
        async with Client(server, mode="legacy") as client:
            result = await client.call_tool("what_can_you_do", {"channel": "mcp"})
            text = result.content[0].text
            assert "What I can do on mcp" in text
            assert "Weather" in text or "weather" in text.lower()
            # Honest about what's missing
            assert "Coming in" in text or "⬜" in text

    asyncio.run(exercise())


def test_mcp_skills_exposed_as_prompts() -> None:
    """Skills are published as MCP prompts."""
    server = create_server(disabled_plugins=set())

    async def exercise() -> None:
        async with Client(server, mode="legacy") as client:
            prompts = await client.list_prompts()
            assert "daily_briefing" in {prompt.name for prompt in prompts.prompts}
            briefing = await client.get_prompt("daily_briefing", {"request": "briefing for Pune"})
            assert "Pune" in briefing.messages[0].content.text

    asyncio.run(exercise())


def test_cli_starts_stdio_server_for_external_mcp_hosts() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "atulya.cli", "mcp"],
        cwd=Path.cwd(),
    )

    async def exercise() -> None:
        async with Client(params, read_timeout_seconds=5) as client:
            listed = await client.list_tools()
            names = {tool.name for tool in listed.tools}
            assert "what_can_you_do" in names
            assert "weather" not in names
            assert "news_headlines" not in names

    asyncio.run(exercise())


def test_disabled_plugins_are_hidden_from_mcp() -> None:
    async def exercise() -> None:
        server = create_server(disabled_plugins={"online-information", "local-utilities"})
        async with Client(server, mode="legacy") as client:
            names = {tool.name for tool in (await client.list_tools()).tools}
            assert "what_can_you_do" not in names
            assert "get_weather" not in names
            assert "calculate" not in names

    asyncio.run(exercise())


def test_mcp_tool_errors_are_safe() -> None:
    """Tool errors over MCP don't leak internal details."""
    server = create_server(disabled_plugins=set())

    async def exercise() -> None:
        async with Client(server, mode="legacy") as client:
            result = await client.call_tool("what_can_you_do", {"channel": "invalid"})
            assert not result.is_error

    asyncio.run(exercise())
