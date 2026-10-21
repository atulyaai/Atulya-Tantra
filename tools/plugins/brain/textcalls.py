"""Recover tool calls that a model wrote as plain text instead of structured tool calls.

Small local models (Qwen via llama.cpp without --jinja, some OpenRouter routes) print
either Qwen's XML form or the Hermes JSON form:

    <tool_call>
    <function=get_weather>
    <parameter=city>
    Delhi
    </parameter>
    </function>
    </tool_call>

    <tool_call>{"name": "get_weather", "arguments": {"city": "Delhi"}}</tool_call>

The streaming filter holds back text from the first marker on, so the raw markup is
never shown or spoken; at the end it returns the parsed calls (or releases the text
unchanged when it turns out not to be a call).
"""
from __future__ import annotations

import json
import re

from .types import ToolCall

MARKERS = ("<tool_call>", "<function=")
_BLOCK = re.compile(r"<tool_call>(.*?)(?:</tool_call>|$)", re.S)
_XML_FUNCTION = re.compile(r"<function=([\w.-]+)>(.*?)(?:</function>|$)", re.S)
_XML_PARAM = re.compile(r"<parameter=([\w.-]+)>\s*(.*?)\s*</parameter>", re.S)


def parse(text: str) -> tuple[list[ToolCall], str]:
    """Return (calls, remaining_text)."""
    calls: list[ToolCall] = []
    bodies = [m.group(1) for m in _BLOCK.finditer(text)] or ([text] if "<function=" in text else [])
    for body in bodies:
        body = body.strip()
        if body.startswith("{"):
            try:
                data = json.loads(body)
            except ValueError:
                continue
            name = data.get("name")
            arguments = data.get("arguments", data.get("parameters", {}))
            if isinstance(name, str) and name:
                calls.append(ToolCall(f"text_{len(calls)}", name,
                                      arguments if isinstance(arguments, str) else json.dumps(arguments)))
            continue
        for function in _XML_FUNCTION.finditer(body):
            args = {}
            for key, value in _XML_PARAM.findall(function.group(2)):
                try:
                    args[key] = json.loads(value)
                except ValueError:
                    args[key] = value
            calls.append(ToolCall(f"text_{len(calls)}", function.group(1), json.dumps(args)))
    remaining = _BLOCK.sub("", text)
    if calls and "<function=" in remaining:
        remaining = _XML_FUNCTION.sub("", remaining)
    return calls, remaining.strip() if calls else text


_ANSWER_KEYS = ("answer", "response", "reply", "final", "text", "message", "content")
_REASONING_KEYS = {"reasoning", "thought", "thoughts", "thinking", "analysis", "plan"}


def _json_reply(held: str) -> tuple[list[ToolCall], str] | None:
    """A whole reply written as a JSON object: a call, an answer field, or reasoning to drop.
    None when it is not such an object (the text is then shown unchanged)."""
    try:
        data = json.loads(held)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    name = data.get("name")
    if isinstance(name, str) and name and ("arguments" in data or "parameters" in data):
        arguments = data.get("arguments", data.get("parameters", {}))
        return [ToolCall("text_0", name, arguments if isinstance(arguments, str) else json.dumps(arguments))], ""
    for key in _ANSWER_KEYS:
        if isinstance(data.get(key), str) and data[key].strip():
            return [], data[key].strip()
    if set(data) & _REASONING_KEYS:
        return [], ""  # private reasoning: never shown or spoken
    return None


class TextCallFilter:
    """Feed streamed text; get back what is safe to show now."""

    def __init__(self) -> None:
        self._held = ""
        self._holding = False
        self._json = False
        self._started = False

    def feed(self, chunk: str) -> str:
        if self._holding:
            self._held += chunk
            return ""
        combined = self._held + chunk
        if not self._started:
            if not combined.strip():
                self._held = combined
                return ""
            if combined.lstrip().startswith("{"):
                # Small models sometimes print {"reasoning": ...} as the reply (LOG.md gate run 2).
                self._holding = self._json = True
                self._held = combined.lstrip()
                return ""
            self._started = True
        index = min((combined.find(m) for m in MARKERS if m in combined), default=-1)
        if index >= 0:
            self._holding = True
            self._held = combined[index:]
            return combined[:index]
        # Keep a possible partial marker at the end (e.g. "<tool_") until the next chunk.
        tail = max((n for marker in MARKERS for n in range(1, len(marker)) if combined.endswith(marker[:n])), default=0)
        self._held = combined[len(combined) - tail:] if tail else ""
        return combined[:len(combined) - tail] if tail else combined

    def finish(self) -> tuple[list[ToolCall], str]:
        """Calls found in held text, plus any text that should still be shown."""
        held, self._held = self._held, ""
        if not self._holding:
            return [], held
        if self._json:
            json_reply = _json_reply(held.strip())
            if json_reply is not None:
                return json_reply
            # A token limit or disconnect can truncate an otherwise recognized reasoning object.
            # Do not release its private contents simply because the closing brace never arrived.
            if re.search(r'"(?:reasoning|thought|thoughts|thinking|analysis|plan)"\s*:', held):
                return [], ""
            return parse(held) if "<tool_call>" in held or "<function=" in held else ([], held)
        return parse(held) if "<" in held else ([], held)
