"""Model tool calling: the brain loop, provider stream parsing, and the shared toolbox."""
from __future__ import annotations

import asyncio
import json
import logging

import httpx

from atulya.logging_setup import RedactingFilter, redact
from tools.plugins.brain import Brain, Message, OpenAICompatibleProvider, ToolCall
from tools.plugins.registry import PluginContext, build_default_registry
from tools.plugins.toolkit import Toolbox, list_skills


class ScriptedProvider:
    """Requests one calculation, then answers with the tool result it was given."""

    name = "scripted"
    model = "test"

    def __init__(self) -> None:
        self.calls: list[list[Message]] = []

    async def complete(self, messages):  # pragma: no cover - stream is always present
        raise AssertionError

    async def stream(self, messages, tools=None):
        self.calls.append(list(messages))
        if tools and not any(item.role == "tool" for item in messages):
            assert any(tool["function"]["name"] == "calculate" for tool in tools)
            yield "Let me check. "
            yield ToolCall("c1", "calculate", json.dumps({"expression": "6*7"}))
            return
        result = next(item.content for item in reversed(messages) if item.role == "tool")
        yield f"The answer is {result}."


def test_brain_runs_tool_calls_and_feeds_results_back() -> None:
    provider = ScriptedProvider()
    brain = Brain(provider)
    toolbox = Toolbox.for_registry(build_default_registry(), None)

    async def run() -> str:
        return "".join([chunk async for chunk in brain.stream(
            [Message(role="user", content="what is six times seven")], toolbox=toolbox)])

    text = asyncio.run(run())
    assert text.startswith("Let me check. The answer is")
    assert "42" in text
    second_round = provider.calls[1]
    assert second_round[-2].tool_calls[0].name == "calculate"
    assert second_round[-1].role == "tool" and second_round[-1].tool_call_id == "c1"


def test_toolbox_respects_disabled_plugins_and_context() -> None:
    registry = build_default_registry()
    registry.set_enabled("local-utilities", False)
    names = {tool["function"]["name"] for tool in Toolbox.for_registry(registry, None).schemas}
    assert "calculate" not in names and "get_time" not in names
    assert "remember_fact" not in names  # needs a user context
    assert "get_weather" in names and "use_skill" in names

    context = PluginContext("conv", object(), object(), "u1")
    with_context = {tool["function"]["name"] for tool in Toolbox.for_registry(registry, context).schemas}
    assert {"remember_fact", "add_meeting"} <= with_context


def test_toolbox_rejects_bad_input_without_raising() -> None:
    toolbox = Toolbox.for_registry(build_default_registry(), None)
    assert "Invalid input" in asyncio.run(toolbox.call("calculate", "not json"))
    assert "not available" in asyncio.run(toolbox.call("rm_rf", "{}"))
    assert "daily-briefing" in {skill["name"] for skill in list_skills()}
    assert "Follow these skill instructions" in asyncio.run(toolbox.call("use_skill", {"name": "daily-briefing"}))


def test_openai_stream_assembles_split_tool_call_deltas() -> None:
    events = [
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "x", "function": {"name": "get_", "arguments": ""}}]}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"name": "weather", "arguments": "{\"city\":"}}]}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "\"Delhi\"}"}}]}}]},
    ]
    body = "".join(f"data: {json.dumps(event)}\n\n" for event in events) + "data: [DONE]\n\n"
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    provider = OpenAICompatibleProvider(base_url="http://test/v1", model="m",
                                        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    async def run():
        return [item async for item in provider.stream([Message(role="user", content="hi")], tools=[{"x": 1}])]

    items = asyncio.run(run())
    assert items == [ToolCall("x", "get_weather", '{"city":"Delhi"}')]
    assert seen[0]["tools"] == [{"x": 1}]


def test_provider_without_tool_support_falls_back_to_plain_chat() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        if "tools" in payload:
            return httpx.Response(400, json={"error": "tools unsupported"})
        return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"hello"}}]}\n\ndata: [DONE]\n\n')

    provider = OpenAICompatibleProvider(base_url="http://test/v1", model="m",
                                        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    async def run():
        return [item async for item in provider.stream([Message(role="user", content="hi")], tools=[{"x": 1}])]

    assert asyncio.run(run()) == ["hello"]
    assert asyncio.run(run()) == ["hello"]
    assert ["tools" in item for item in requests] == [True, False, False]


def test_secrets_are_redacted_from_logs() -> None:
    leaked = "GET https://api.telegram.org/bot1234567890:AAFakeTestTokenOnly_abcdefghijklmnop/getUpdates"
    assert "AAFakeTest" not in redact(leaked)
    assert "Bearer <redacted>" in redact("Authorization: Bearer sk-abcdefghijklmnopqrstuv")
    record = logging.LogRecord("httpx", logging.INFO, __file__, 1, "Request %s", (leaked,), None)
    RedactingFilter().filter(record)
    assert "AAFakeTest" not in record.getMessage()


def test_pc_actions_wait_for_approval_and_only_run_for_that_user(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DISPLAY", ":test-desktop")
    from tools.plugins.toolkit import ActionQueue

    queue = ActionQueue(tmp_path)
    view = queue.view()
    context = PluginContext("conv", object(), object(), "u1", actions=view)
    toolbox = Toolbox.for_registry(build_default_registry(), context)
    reply = asyncio.run(toolbox.call("open_url", {"url": "https://example.com"}))
    assert "NOT run" in reply
    [pending] = view.drain_new()
    assert pending.summary == "Open website: https://example.com" and view.drain_new() == []
    assert queue.take(pending.id, "someone-else") is None
    assert queue.take(pending.id, "u1") is pending
    assert queue.take(pending.id, "u1") is None  # single use


def test_pc_actions_are_refused_without_an_approval_channel(monkeypatch) -> None:
    monkeypatch.setenv("DISPLAY", ":test-desktop")
    context = PluginContext("tg1", object(), object(), "tg_1")  # e.g. Telegram: no actions queue
    toolbox = Toolbox.for_registry(build_default_registry(), context)
    assert "only available in the Atulya WebUI" in asyncio.run(toolbox.call("take_screenshot", {}))


def test_search_past_chats_is_scoped_to_the_user(tmp_path) -> None:
    from atulya.history import ConversationHistory

    history = ConversationHistory(tmp_path)
    history.append("c1", "m1", "user", "my passport number ends in 42", "u1")
    history.append("c2", "m2", "user", "passport renewal next week", "u2")
    assert [row["content"] for row in history.search("passport", user_id="u1")] == ["my passport number ends in 42"]
    assert history.search("pass%", user_id="u1") == []


def test_tool_calls_written_as_text_are_executed_not_shown() -> None:
    from tools.plugins.brain.textcalls import TextCallFilter

    class TextCallingProvider:
        name = "local"
        model = "qwen"

        async def complete(self, messages):  # pragma: no cover
            raise AssertionError

        async def stream(self, messages, tools=None):
            if not any(item.role == "tool" for item in messages):
                for piece in ["Checking. <tool_", "call>\n<function=calculate>\n<parameter=expression>\n",
                              "6*7\n</parameter>\n</function>\n</tool_call>"]:
                    yield piece
                return
            yield "It is " + next(item.content for item in messages if item.role == "tool")

    async def run() -> str:
        toolbox = Toolbox.for_registry(build_default_registry(), None)
        return "".join([c async for c in Brain(TextCallingProvider()).stream(
            [Message(role="user", content="6 times 7?")], toolbox=toolbox)])

    text = asyncio.run(run())
    assert "<tool" not in text and "<function" not in text and "42" in text

    hermes = TextCallFilter()
    assert hermes.feed('<tool_call>{"name": "get_time", "arguments": {}}</tool_call>') == ""
    calls, rest = hermes.finish()
    assert [c.name for c in calls] == ["get_time"] and rest == ""
    plain = TextCallFilter()
    assert plain.feed("a < b is true") == "a < b is true"


def test_screen_control_queues_ui_action_only_inside_a_chat_stream():
    import asyncio

    from tools.plugins import toolkit

    assert "only work" in asyncio.run(toolkit._screen_control({"action": "hide_chat"}, None))
    queued: list[str] = []

    async def run():
        toolkit.UI_ACTIONS.set(queued)
        await toolkit._screen_control({"action": "hide_chat"}, None)
        return await toolkit._screen_control({"action": "format_disk"}, None)

    assert "Unknown" in asyncio.run(run())
    assert queued == ["hide_chat"]


def test_headless_server_does_not_offer_desktop_control(monkeypatch) -> None:
    import os
    import sys
    import pytest
    if os.name == "nt" or sys.platform == "darwin":
        pytest.skip("Headless server filtering applies to Linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    context = PluginContext("conv", object(), object(), "owner")
    toolbox = Toolbox.for_registry(build_default_registry(), context)
    names = {item["function"]["name"] for item in toolbox.schemas}
    assert "open_url" not in names and "take_screenshot" not in names
    assert "open_website" in names and "find_music" in names
