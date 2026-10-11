"""MCP protocol tests use the SDK's in-memory client and fake providers."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
from mcp import Client
from mcp.client.stdio import StdioServerParameters

from tools.mcp.server import create_server


def test_mcp_tool_discovery_invocation_and_bounded_arguments() -> None:
    calls: list[tuple[str, int | str]] = []

    async def weather(city: str) -> str:
        calls.append(("weather", city))
        return f"Weather for {city}: clear."

    async def headlines(limit: int) -> str:
        calls.append(("headlines", limit))
        return f"{limit} test headlines"

    server = create_server(weather, headlines, disabled_plugins=set())

    async def exercise() -> None:
        async with Client(server, mode="legacy") as client:
            listed = await client.list_tools()
            assert {tool.name for tool in listed.tools} == {"weather", "news_headlines", "get_time", "calculate"}
            prompts = await client.list_prompts()
            assert "daily_briefing" in {prompt.name for prompt in prompts.prompts}
            briefing = await client.get_prompt("daily_briefing", {"request": "briefing for Pune"})
            assert "Pune" in briefing.messages[0].content.text
            assert "news_headlines" in briefing.messages[0].content.text
            total = await client.call_tool("calculate", {"expression": "6*7"})
            assert "42" in total.content[0].text

            forecast = await client.call_tool("weather", {"city": "Pune"})
            assert not forecast.is_error
            assert forecast.content[0].text == "Weather for Pune: clear."

            news = await client.call_tool("news_headlines", {"limit": 99})
            assert not news.is_error
            assert news.content[0].text == "10 test headlines"

    asyncio.run(exercise())
    assert calls == [("weather", "Pune"), ("headlines", 10)]


def test_mcp_service_errors_are_safe_and_malformed_inputs_are_rejected() -> None:
    async def broken_weather(_city: str) -> str:
        raise httpx.ConnectError("private endpoint detail")

    async def headlines(_limit: int) -> str:
        return "headlines"

    server = create_server(broken_weather, headlines, disabled_plugins=set())

    async def exercise() -> None:
        async with Client(server, mode="legacy") as client:
            failed = await client.call_tool("weather", {"city": "Pune"})
            assert not failed.is_error
            assert "unavailable" in failed.content[0].text.lower()
            assert "private endpoint detail" not in failed.content[0].text

            malformed = await client.call_tool("weather", {"city": 123})
            assert malformed.is_error

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
            assert {"weather", "news_headlines"} <= {tool.name for tool in listed.tools}

    asyncio.run(exercise())


def test_disabled_plugins_are_hidden_from_mcp() -> None:
    async def exercise() -> None:
        server = create_server(disabled_plugins={"online-information", "local-utilities"})
        async with Client(server, mode="legacy") as client:
            assert (await client.list_tools()).tools == []

    asyncio.run(exercise())
