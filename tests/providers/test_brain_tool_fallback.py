"""Actions must survive providers without native streaming tool support."""
import asyncio
import sys

import pytest
import httpx
import json

from tools.plugins.brain import AutomaticProvider, OpenAICompatibleProvider, Brain, Message, ToolCall

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class ToolboxStub:
    MAX_ROUNDS = 2
    schemas = [{"type": "function", "function": {"name": "save_note"}}]

    def __init__(self):
        self.calls = []

    def instructions(self):
        return "Use tools to save notes."

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        return "Saved note #1"


class CompletionProvider:
    name = model = "completion-test"

    async def complete(self, messages):
        if messages[-1].role == "tool":
            assert messages[-1].content == "Saved note #1"
            return "Saved your note."
        assert "save_note" in messages[0].content
        return '<tool_call>{"name":"save_note","arguments":{"text":"hello"}}</tool_call>'


class TextStreamProvider(CompletionProvider):
    async def stream(self, messages):
        text = await self.complete(messages)
        for offset in range(0, len(text), 5):
            yield text[offset:offset + 5]


@pytest.mark.parametrize("provider_type", [CompletionProvider, TextStreamProvider])
def test_text_calls_execute_without_native_tool_stream(provider_type):
    toolbox = ToolboxStub()
    reply = asyncio.run(Brain(provider_type()).respond_with_tools(
        [Message(role="user", content="Save a note saying hello")], toolbox))
    assert len(toolbox.calls) == 1
    assert toolbox.calls[0][0] == "save_note"
    assert "Saved your note." in reply.text
    assert "<tool_call>" not in reply.text


@pytest.mark.parametrize("provider_type", [CompletionProvider, TextStreamProvider])
def test_automatic_selection_preserves_actions_for_text_only_provider(provider_type):
    toolbox = ToolboxStub()
    provider = AutomaticProvider([provider_type()])
    reply = asyncio.run(Brain(provider).respond_with_tools(
        [Message(role="user", content="Save a note saying hello")], toolbox))
    assert len(toolbox.calls) == 1
    assert "Saved your note." in reply.text


def test_native_calls_are_ignored_when_tool_budget_is_closed():
    class Provider:
        name = model = "native-test"

        async def stream(self, messages, tools=None):
            if tools:
                yield ToolCall("first", "save_note", '{}')
            else:
                yield ToolCall("late", "save_note", '{}')
                yield "Finished."

    toolbox = ToolboxStub()
    reply = asyncio.run(Brain(Provider()).respond_with_tools(
        [Message(role="user", content="Save my note")], toolbox))
    assert len(toolbox.calls) == 1
    assert "Finished." in reply.text


def test_rejected_native_tool_field_keeps_text_actions_on_subsequent_turns():
    payloads = []
    def handler(request):
        payload = json.loads(request.content)
        payloads.append(payload)
        if "tools" in payload:
            return httpx.Response(400, json={"error": "tools unsupported"})
        if payload["messages"][-1]["role"] == "tool":
            text = "Saved your note."
        else:
            assert "save_note" in payload["messages"][0]["content"]
            text = '<tool_call>{"name":"save_note","arguments":{"text":"hello"}}</tool_call>'
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              content="data: " + json.dumps({"choices": [{"delta": {"content": text}}]}) + "\n\ndata: [DONE]\n\n")
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = OpenAICompatibleProvider(base_url="https://test/v1", model="test", client=client)
            for _ in range(2):
                toolbox = ToolboxStub()
                reply = await Brain(provider).respond_with_tools([Message(role="user", content="Save my note")], toolbox)
                assert len(toolbox.calls) == 1
                assert "Saved your note." in reply.text
    asyncio.run(exercise())
    assert sum("tools" in payload for payload in payloads) == 1
