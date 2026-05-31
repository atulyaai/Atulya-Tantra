"""Free-first Atulya LLM bridge.

This module is the single brain entrypoint used by CLI, Drishti, and channels.
Tantra remains optional research/local inference; production behavior never
depends on it being available.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, AsyncIterator

from atulya.intelligence import ProviderRouter
from atulya.persona import Persona, get_atulya_fallback_response
from yantra.capabilities import ToolRegistry, create_default_registry


@dataclass
class LLMEvent:
    type: str
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    text: str
    provider: str
    tool_steps: list[dict[str, Any]] = field(default_factory=list)
    needs_approval: bool = False
    pending_tool: dict[str, Any] | None = None


RISKY_TOOLS = {
    "exec",
    "file_write",
    "file_edit",
    "code_execute",
    "sap_gui_automation",
}


class AtulyaLLM:
    """Free-first chat orchestrator with a small ReAct-style tool loop."""

    def __init__(
        self,
        tools: ToolRegistry | None = None,
        max_tool_iterations: int = 3,
        allow_exec: bool = False,
    ):
        self.tools = tools or create_default_registry()
        self.max_tool_iterations = max_tool_iterations
        self.allow_exec = allow_exec
        self.router = ProviderRouter()
        self.persona = Persona()

    async def ask(
        self,
        prompt: str,
        history: list[dict[str, str]] | None = None,
        tools_enabled: bool = True,
        approved_tool_call: dict[str, Any] | None = None,
        provider: str = "",
    ) -> LLMResponse:
        system_prompt = self._build_system_prompt(history or [])
        working_prompt = self._compose_prompt(prompt, history or [])
        steps: list[dict[str, Any]] = []
        provider = "Diagnostics Fallback"

        if approved_tool_call and tools_enabled:
            step = await self._execute_tool_call(approved_tool_call)
            steps.append(step)
            working_prompt = (
                f"{working_prompt}\n\n"
                f"User approved tool:\n{json.dumps(approved_tool_call, ensure_ascii=False)}\n\n"
                f"Tool result:\n{json.dumps(step, ensure_ascii=False)}\n\n"
                "Now answer the user directly. If another tool is essential, emit exactly one JSON tool call."
            )

        for _ in range(self.max_tool_iterations if tools_enabled else 1):
            text, provider_name = await self.router.chat(working_prompt, system_prompt, preferred_provider=provider)
            tool_call = self._extract_tool_call(text)
            if not tool_call or not tools_enabled:
                return LLMResponse(text=self._strip_tool_blocks(text).strip(), provider=provider_name, tool_steps=steps)

            tool_calls = self._normalize_tool_calls(tool_call)
            risky = [call for call in tool_calls if call["tool"] in RISKY_TOOLS]
            if risky:
                return LLMResponse(
                    text="Approval required before running this tool.",
                    provider=provider_name,
                    tool_steps=steps,
                    needs_approval=True,
                    pending_tool=risky[0],
                )

            new_steps = await asyncio.gather(*(self._execute_tool_call(call) for call in tool_calls))
            steps.extend(new_steps)
            working_prompt = (
                f"{working_prompt}\n\n"
                f"Assistant requested tool:\n{json.dumps(tool_call, ensure_ascii=False)}\n\n"
                f"Tool result:\n{json.dumps(new_steps, ensure_ascii=False)}\n\n"
                "Now answer the user directly. If another tool is essential, emit exactly one JSON tool call."
            )

        fallback = "I ran out of tool iterations before completing the request. Here is what I found:\n"
        fallback += "\n".join(f"- {s['tool']}: {s.get('output') or s.get('error')}" for s in steps)
        return LLMResponse(text=fallback, provider=provider, tool_steps=steps)

    async def _execute_tool_call(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_tool_call(tool_call)
        tool_name = normalized["tool"]
        arguments = normalized["arguments"]
        if tool_name == "exec":
            arguments.setdefault("allow_exec", self.allow_exec)
        result = await self.tools.execute(tool_name, **arguments)
        return {
            "tool": tool_name,
            "arguments": arguments,
            "success": result.success,
            "output": result.output[:4000],
            "error": result.error,
        }

    @staticmethod
    def _normalize_tool_call(tool_call: dict[str, Any]) -> dict[str, Any]:
        tool_name = str(tool_call.get("tool") or tool_call.get("name") or "").strip()
        arguments = tool_call.get("arguments") or tool_call.get("args") or {}
        if not isinstance(arguments, dict):
            arguments = {}
        return {"tool": tool_name, "arguments": arguments}

    @staticmethod
    def _normalize_tool_calls(tool_call: dict[str, Any]) -> list[dict[str, Any]]:
        raw_calls = tool_call.get("tools") or tool_call.get("tool_calls")
        if isinstance(raw_calls, list):
            return [AtulyaLLM._normalize_tool_call(call) for call in raw_calls if isinstance(call, dict)]
        return [AtulyaLLM._normalize_tool_call(tool_call)]

    async def stream(
        self,
        prompt: str,
        history: list[dict[str, str]] | None = None,
        tools_enabled: bool = True,
        approved_tool_call: dict[str, Any] | None = None,
        provider: str = "",
    ) -> AsyncIterator[LLMEvent]:
        response = await self.ask(
            prompt,
            history=history,
            tools_enabled=tools_enabled,
            approved_tool_call=approved_tool_call,
            provider=provider,
        )
        for step in response.tool_steps:
            yield LLMEvent("tool", metadata=step)
        if response.needs_approval:
            yield LLMEvent(
                "done",
                metadata={
                    "provider": response.provider,
                    "steps": response.tool_steps,
                    "needs_approval": True,
                    "pending_tool": response.pending_tool,
                    "tool": (response.pending_tool or {}).get("tool"),
                    "tool_args": (response.pending_tool or {}).get("arguments", {}),
                },
            )
            return
        for chunk in _chunk_text(response.text):
            yield LLMEvent("token", content=chunk)
            await asyncio.sleep(0)
        yield LLMEvent("done", metadata={"provider": response.provider, "steps": response.tool_steps})

    def _build_system_prompt(self, history: list[dict[str, str]]) -> str:
        prompt = self.persona.get_system_prompt()
        tools = self.tools.list_tools()
        tool_lines = [f"- {item['name']}: {item['description']}" for item in tools]
        return (
            f"{prompt}\n\n"
            "Operating policy:\n"
            "- Use free/local providers first. Paid APIs are optional fallbacks only when configured.\n"
            "- Tantra must never block production behavior.\n"
            "- For tool use, emit exactly one JSON object like "
            '{"tool":"web_search","arguments":{"query":"..."}} and no markdown around it.\n'
            '- For parallel safe tools, emit {"tools":[{"tool":"...","arguments":{}}, ...]}.\n'
            "- Do not call exec unless the user explicitly asks and execution is enabled.\n\n"
            "Available tools:\n" + "\n".join(tool_lines[:30]) + "\n\n"
            f"Recent turns available: {len(history)}"
        )

    @staticmethod
    def _compose_prompt(prompt: str, history: list[dict[str, str]]) -> str:
        trimmed = history[-10:]
        if not trimmed:
            return prompt
        turns = []
        for item in trimmed:
            role = item.get("role", "user")
            content = item.get("content") or item.get("text") or ""
            if content:
                turns.append(f"{role}: {content}")
        return "Conversation so far:\n" + "\n".join(turns) + f"\n\nUser: {prompt}"

    @staticmethod
    def _extract_tool_call(text: str) -> dict[str, Any] | None:
        candidates = [text]
        fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
        candidates.extend(fenced)
        brace = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if brace:
            candidates.append(brace.group(0))
        for candidate in candidates:
            try:
                data = json.loads(candidate.strip())
            except Exception:
                continue
            if isinstance(data, dict) and ("tool" in data or "name" in data or "tools" in data or "tool_calls" in data):
                return data
        return None

    @staticmethod
    def _strip_tool_blocks(text: str) -> str:
        if AtulyaLLM._extract_tool_call(text):
            cleaned = re.sub(r"```(?:json)?\s*\{.*?\}\s*```", "", text, flags=re.DOTALL).strip()
            if cleaned.startswith("{") and cleaned.endswith("}"):
                return ""
            return cleaned
        return text


def _chunk_text(text: str, size: int = 28) -> list[str]:
    if not text:
        return [""]
    chunks: list[str] = []
    current = ""
    for word in text.split(" "):
        candidate = f"{current} {word}".strip()
        if len(candidate) >= size and current:
            chunks.append(current + " ")
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


async def ask(prompt: str, history: list[dict[str, str]] | None = None) -> LLMResponse:
    return await get_default_llm().ask(prompt, history=history)


async def stream(
    prompt: str,
    history: list[dict[str, str]] | None = None,
    approved_tool_call: dict[str, Any] | None = None,
) -> AsyncIterator[LLMEvent]:
    async for event in get_default_llm().stream(prompt, history=history, approved_tool_call=approved_tool_call):
        yield event


def fallback_answer(prompt: str) -> str:
    return get_atulya_fallback_response(prompt, "en_female")


@lru_cache(maxsize=1)
def get_default_llm() -> AtulyaLLM:
    return AtulyaLLM()
