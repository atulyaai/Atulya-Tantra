"""Tests for Atulya Agent — tool functions, registry, agent loop."""
from __future__ import annotations

import asyncio

import pytest

from atulya.agent.tools import (
    TOOL_REGISTRY,
    get_tool_schemas,
    execute_tool,
    set_reminder,
    list_reminders,
    cancel_reminder,
    get_system_status,
    get_proactive_suggestions,
    send_email,
    fetch_emails,
    configure_email,
    analyze_image,
)
from atulya.agent.agent_loop import _parse_response
from atulya.agent.core import AgentCore


class TestToolRegistry:
    """The registry is just a dict of function + schema. That's it."""

    def test_tools_are_registered(self):
        assert len(TOOL_REGISTRY) >= 8
        assert "set_reminder" in TOOL_REGISTRY
        assert "send_email" in TOOL_REGISTRY
        assert "get_system_status" in TOOL_REGISTRY
        assert "get_proactive_suggestions" in TOOL_REGISTRY

    def test_every_tool_has_description_and_parameters(self):
        for name, info in TOOL_REGISTRY.items():
            assert "description" in info, f"{name} missing description"
            assert "parameters" in info, f"{name} missing parameters"
            assert "fn" in info, f"{name} missing fn"

    def test_get_tool_schemas_returns_openai_format(self):
        schemas = get_tool_schemas()
        assert isinstance(schemas, list)
        for s in schemas:
            assert s["type"] == "function"
            assert s["function"]["name"]
            assert s["function"]["description"]
            assert s["function"]["parameters"]

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        result = await execute_tool("nonexistent")
        assert "unknown" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_tool_with_bad_args_returns_error(self):
        result = await execute_tool("set_reminder", bad_arg=123)
        assert "error" in result.lower()


@pytest.mark.asyncio
class TestReminderTools:
    async def test_set_reminder_in_minutes(self):
        result = await set_reminder(message="test", time_str="in 5 minutes")
        assert "Reminder set" in result

    async def test_set_reminder_tomorrow(self):
        result = await set_reminder(message="test", time_str="tomorrow at 9am")
        assert "Reminder set" in result

    async def test_set_reminder_bad_time(self):
        result = await set_reminder(message="test", time_str="whenever")
        assert "Could not understand" in result

    async def test_list_and_cancel(self):
        await set_reminder(message="list test", time_str="in 60 minutes")
        lst = await list_reminders(hours=2)
        assert isinstance(lst, str)
        first_id = "rem_0"
        result = await cancel_reminder(first_id)
        assert "not found" in result.lower()


@pytest.mark.asyncio
class TestSystemTools:
    async def test_get_system_status(self):
        result = await get_system_status()
        assert "CPU" in result
        assert "RAM" in result
        assert "Disk" in result

    async def test_get_proactive_suggestions(self):
        result = await get_proactive_suggestions()
        assert isinstance(result, str)
        assert len(result) > 0


@pytest.mark.asyncio
class TestEmailTools:
    async def test_send_without_config(self):
        result = await send_email(to="a@b.com", subject="hi", body="hello")
        assert "not configured" in result.lower() or "not installed" in result.lower()

    async def test_fetch_without_config(self):
        result = await fetch_emails(limit=3)
        assert "not configured" in result.lower() or "not installed" in result.lower()

    async def test_configure_email(self):
        result = await configure_email(
            imap_server="imap.test.com",
            username="test@test.com",
            password="secret",
        )
        assert "configured" in result.lower()


@pytest.mark.asyncio
class TestVisionTools:
    async def test_analyze_without_model(self):
        result = await analyze_image(image_path="test.jpg")
        assert "not loaded" in result.lower() or "download" in result.lower()


class TestAgentLoop:
    def test_parse_response_plain_string(self):
        text, calls = _parse_response("Hello world")
        assert text == "Hello world"
        assert calls is None

    def test_parse_response_tuple(self):
        text, calls = _parse_response(("Hello", "test_provider"))
        assert text == "Hello"
        assert calls is None

    def test_parse_response_openai_format(self):
        resp = {"choices": [{"message": {"content": "Hello"}}]}
        text, calls = _parse_response(resp)
        assert text == "Hello"
        assert calls is None

    def test_parse_response_with_tool_call(self):
        resp = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {"function": {"name": "get_system_status", "arguments": "{}"}}
                        ],
                    }
                }
            ]
        }
        text, calls = _parse_response(resp)
        assert text is None
        assert calls is not None
        assert calls[0]["name"] == "get_system_status"


@pytest.mark.asyncio
class TestAgentCore:
    async def test_list_tools(self):
        a = AgentCore()
        tools = a.list_tools()
        assert isinstance(tools, list)
        assert len(tools) >= 8
        assert "set_reminder" in [t["name"] for t in tools]

    async def test_process_without_llm(self):
        a = AgentCore()
        result = await a.process("hello")
        assert "not connected" in result.lower()

    async def test_register_callback_and_event(self):
        a = AgentCore()
        events = []
        async def cb(event_type, data):
            events.append((event_type, data))
        a.register_callback(cb)
        await a._on_event("test", {"key": "value"})
        assert len(events) == 1

    async def test_get_tool_schemas(self):
        a = AgentCore()
        schemas = a.get_tool_schemas()
        assert isinstance(schemas, list)
        assert all(s["type"] == "function" for s in schemas)

    async def test_reminder_fires_callback(self):
        a = AgentCore()
        events = []
        async def cb(event_type, data):
            events.append((event_type, data))
        a.register_callback(cb)
        await set_reminder(message="cb test", time_str="in 2 seconds")
        await asyncio.sleep(3)
        reminder_events = [e for e in events if e[0] == "reminder"]
        assert len(reminder_events) >= 1
