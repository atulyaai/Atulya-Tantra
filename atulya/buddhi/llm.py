"""Free-first Atulya LLM bridge.

This module is the single brain entrypoint used by CLI, Drishti, and channels.
Tantra remains optional research/local inference; production behavior never
depends on it being available.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING, Any, AsyncIterator

if TYPE_CHECKING:
    from atulya.smriti.manager import MemoryManager

from atulya.buddhi.safety import RISKY_TOOLS, needs_confirmation  # noqa: F401  (RISKY_TOOLS re-exported)
from atulya.buddhi.intelligence import ProviderRouter
from atulya.bhava.persona import Persona, get_atulya_fallback_response
from atulya.bhava.emotion import MoodState, build_emotional_directive, detect_emotion
from atulya.yantra.capabilities import ToolRegistry


# Style rules that make replies read as a person, not a robot. Appended to
# every system prompt.
_HUMAN_STYLE = (
    "Voice & manner:\n"
    "- Speak like a sharp, caring friend — warm, direct, concise by default.\n"
    "- If the user seems upset, tired or anxious, acknowledge it in one natural "
    "sentence before helping.\n"
    "- Use the user's name when you know it. Light wit is welcome; never forced.\n"
    '- Never say "As an AI" or narrate your own limitations unprompted.\n'
    "- Never use emojis, emoticons or markdown: your replies are spoken aloud.\n"
)


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
    # The real stages the cognitive kernel went through (understand / decide /
    # act / remember / think), for UIs to show what actually happened.
    trace: list[dict[str, Any]] = field(default_factory=list)


# Which tools the model sees first when the advertised list is capped.
# Personal-assistant essentials lead; anything unranked keeps registry order.
_TOOL_PRIORITY = {
    "home_control": 1,
    "set_reminder": 2,
    "get_weather": 3,
    "current_time": 4,
    "web_search": 5,
    "memory_search": 6,
    "memory_store": 7,
    "calendar_list": 8,
    "calendar_add": 9,
    "fetch_emails": 10,
    "send_email": 11,
    "todo_create": 12,
    "calculate": 13,
    "web_fetch": 14,
}


def _words(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", (text or "").lower()).split())


def is_echo(prompt: str, reply: str) -> bool:
    """True when a reply just repeats the question back ("who are you" -> "Who are you?")."""
    q, a = _words(prompt), _words(reply)
    return bool(a) and (a == q or (len(a.split()) <= 8 and a in q) or (len(q.split()) <= 8 and q in a and len(a) <= len(q) + 4))


def copies_memory(prompt: str, reply: str, memories: list[str]) -> bool:
    """True when the reply is word-for-word an answer recalled for a *different* question."""
    a = _words(reply)
    for entry in memories:
        m = re.match(r"Q:\s*(.*?)\s*\nA:\s*(.*)\Z", entry or "", re.S)
        if m and _words(m.group(2)) == a and _words(m.group(1)) != _words(prompt):
            return True
    return False


_PAST_CUES = re.compile(
    r"\b(remember|recall|remind me|earlier|before|last time|previous|yesterday|you said|i said|i told|"
    r"we talked|did i|what did|my name|my favou?rite)\b|याद|पहले|कल|बताया था",
    re.I,
)


def wants_memory(prompt: str) -> bool:
    """Should past conversations be shown to the model for this question?

    The tiny local model copies a recalled answer straight back at unrelated
    questions, so with it, memory is only brought in when you ask about the past.
    Bigger brains (balanced / power / cloud) always get it.
    """
    from atulya.buddhi.brain import active_brain

    return active_brain() != "tiny" or bool(_PAST_CUES.search(prompt or ""))


def clean_history(history: list[dict[str, str]], keep: int = 10) -> list[dict[str, str]]:
    """Conversation turns safe to show a small model.

    A tiny model copies whatever it sees repeated, so a reply that only echoes
    its question, or repeats an earlier reply word for word, is dropped together
    with the question it answered. Only the last ``keep`` turns are used.
    """
    cleaned: list[dict[str, str]] = []
    seen: set[str] = set()
    last_user = ""
    pending_user: dict[str, str] | None = None
    for item in history:
        role = item.get("role", "user")
        content = item.get("content") or item.get("text") or ""
        if not content:
            continue
        if role == "user":
            if pending_user is not None:
                cleaned.append(pending_user)
            pending_user, last_user = item, content
            continue
        key = _words(content)
        if is_echo(last_user, content) or key in seen:
            pending_user = None  # drop the question and its bad answer
            continue
        seen.add(key)
        if pending_user is not None:
            cleaned.append(pending_user)
            pending_user = None
        cleaned.append(item)
    if pending_user is not None:
        cleaned.append(pending_user)
    return cleaned[-keep:]


def _echoed_memory(entry: str) -> bool:
    """A remembered 'Q: …\nA: …' pair whose answer only repeats its question."""
    m = re.match(r"Q:\s*(.*?)\s*\nA:\s*(.*)\Z", entry or "", re.S)
    return bool(m) and (not _words(m.group(1)) or is_echo(m.group(1), m.group(2)))


class AtulyaLLM:
    """Free-first chat orchestrator with a small ReAct-style tool loop."""

    def __init__(
        self,
        tools: ToolRegistry | None = None,
        max_tool_iterations: int = 3,
        allow_exec: bool = False,
        use_memory: bool = False,
        memory_dir: str = "data/memory",
    ):
        if tools is None:
            # One tool surface: yantra tools + personal-assistant tools.
            from atulya.buddhi.toolbelt import build_unified_registry
            tools = build_unified_registry()
        self.tools = tools
        self.max_tool_iterations = max_tool_iterations
        self.allow_exec = allow_exec
        self.router = ProviderRouter()
        self.persona = Persona()
        self.use_memory = use_memory
        self.memory_dir = memory_dir
        self._memory = None
        self.mood = MoodState.load()

    def _human_context(self, prompt: str) -> str:
        """Perceive the user's emotion, nudge Atulya's mood, and return a short
        directive block for the system prompt. Best-effort; never raises."""
        try:
            reading = detect_emotion(prompt)
            self.mood.nudge(reading)
            self.mood.save()
            return build_emotional_directive(reading, self.mood)
        except Exception:
            return ""

    def _ensure_memory(self):
        if self._memory is None and self.use_memory:
            try:
                from atulya.smriti.manager import MemoryManager

                self._memory = MemoryManager(self.memory_dir)
            except Exception:
                self._memory = False
        return self._memory or None

    async def _ensure_memory_initialized(self):
        mgr = self._ensure_memory()
        if not mgr:
            return None
        if not getattr(mgr, "_initialized", False):
            try:
                await mgr.initialize()
                mgr._initialized = True
            except Exception:
                return None
        return mgr

    def memory(self) -> "MemoryManager | None":
        return self._ensure_memory()

    async def _retrieve_memory_context(self, prompt: str, limit: int = 5) -> list[str]:
        mgr = await self._ensure_memory_initialized()
        if not mgr:
            return []
        try:
            entries = await mgr.semantic_search(prompt, limit)
            return [entry.content for entry in entries
                    if getattr(entry, "content", None) and not _echoed_memory(entry.content)]
        except Exception:
            return []

    async def _store_exchange(self, prompt: str, response_text: str) -> None:
        mgr = await self._ensure_memory_initialized()
        if not mgr or not response_text or is_echo(prompt, response_text):
            return  # never remember an answer that only parrots the question: a small model copies it back
        try:
            combined = f"Q: {prompt}\nA: {response_text}"
            await mgr.store_session(combined)
        except Exception:
            pass

    async def ask(
        self,
        prompt: str,
        history: list[dict[str, str]] | None = None,
        tools_enabled: bool = True,
        approved_tool_call: dict[str, Any] | None = None,
        provider: str = "",
        context: str = "",
    ) -> LLMResponse:
        system_prompt = self._build_system_prompt(history or [], user_prompt=prompt, context=context)
        working_prompt = self._turn_notes(prompt, context) + self._compose_prompt(prompt, history or [])
        steps: list[dict[str, Any]] = []
        requested_provider = provider
        memories: list[str] = []

        if requested_provider.startswith("public") or requested_provider == "public":
            pass
        elif self.use_memory and (requested_provider == "" or "private" in requested_provider or "local" in requested_provider.lower() or requested_provider == "private"):
            memories = await self._retrieve_memory_context(prompt) if wants_memory(prompt) else []
            if memories:
                working_prompt = (
                    "Relevant past interactions:\n"
                    + "\n".join(f"- {m}" for m in memories)
                    + f"\n\n{working_prompt}"
                )

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
            text, provider_name = await self.router.chat(
                working_prompt,
                system_prompt,
                preferred_provider=requested_provider,
                tools=self._build_tool_schemas() if tools_enabled else None,
            )
            if is_echo(prompt, text) or copies_memory(prompt, text, memories):
                # The model parroted the question or a recalled answer: ask it plainly once, without memory.
                text, provider_name = await self.router.chat(
                    prompt, system_prompt, preferred_provider=requested_provider, tools=None)
            tool_call = self._extract_tool_call(text)
            if not tool_call or not tools_enabled:
                final = LLMResponse(text=self._strip_tool_blocks(text).strip(), provider=provider_name, tool_steps=steps)
                await self._store_exchange(prompt, final.text)
                return final

            tool_calls = self._normalize_tool_calls(tool_call)
            risky = [call for call in tool_calls if needs_confirmation(call["tool"], call["arguments"])]
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
        final = LLMResponse(text=fallback, provider=requested_provider or "Diagnostics Fallback", tool_steps=steps)
        await self._store_exchange(prompt, final.text)
        return final

    async def _execute_tool_call(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_tool_call(tool_call)
        tool_name = normalized["tool"]
        arguments = normalized["arguments"]
        if tool_name == "exec":
            # Execution permission is server policy, never a caller- or
            # model-supplied argument: override (not setdefault) allow_exec and
            # drop any allow_list so ATULYA_EXEC_ALLOWLIST stays authoritative.
            arguments["allow_exec"] = self.allow_exec
            arguments.pop("allow_list", None)
        result = await self.tools.execute(tool_name, **arguments)
        return {
            "tool": tool_name,
            "arguments": arguments,
            "success": result.success,
            "output": result.output[:4000],
            "error": result.error,
        }

    async def run_tool(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        """Execute one tool call with the brain's policies applied; returns a step dict."""
        return await self._execute_tool_call(tool_call)

    async def remember(self, prompt: str, response_text: str) -> None:
        """Write an exchange (e.g. an action the kernel took) to long-term memory."""
        await self._store_exchange(prompt, response_text)

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
        context: str = "",
    ) -> AsyncIterator[LLMEvent]:
        # True incremental streaming when no tools/approval gate is involved:
        # each provider's chat_stream (llama-cpp token generator) is used directly.
        if not tools_enabled and not approved_tool_call:
            system_prompt = self._build_system_prompt(history or [], user_prompt=prompt, context=context)
            working_prompt = self._turn_notes(prompt, context) + self._compose_prompt(prompt, history or [])
            parts: list[str] = []
            async for piece, provider_name in self.router.stream(
                working_prompt,
                system_prompt,
                preferred_provider=provider,
            ):
                if piece:
                    parts.append(piece)
                    yield LLMEvent("token", content=piece)
                    await asyncio.sleep(0)
            yield LLMEvent(
                "done",
                metadata={"provider": provider_name, "steps": []},
            )
            return

        response = await self.ask(
            prompt,
            history=history,
            tools_enabled=tools_enabled,
            approved_tool_call=approved_tool_call,
            provider=provider,
            context=context,
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

    def _build_system_prompt(self, history: list[dict[str, str]], user_prompt: str = "", context: str = "") -> str:
        prompt = self.persona.get_system_prompt()
        tools = self.tools.list_tools()
        tool_lines = [f"- {item['name']}: {item['description']}" for item in tools]
        # Kept byte-identical across turns so llama.cpp can reuse its KV cache;
        # anything that changes per turn goes in _turn_notes instead.
        human_block = f"\n\n{_HUMAN_STYLE}"
        return (
            f"{prompt}"
            f"{human_block}\n\n"
            "Operating policy:\n"
            "- Use free/local providers first. Paid APIs are optional fallbacks only when configured.\n"
            "- Tantra must never block production behavior.\n"
            "- For tool use, emit exactly one JSON object like "
            '{"tool":"web_search","arguments":{"query":"..."}} and no markdown around it.\n'
            '- For parallel safe tools, emit {"tools":[{"tool":"...","arguments":{}}, ...]}.\n'
            "- Do not call exec unless the user explicitly asks and execution is enabled.\n\n"
            "Available tools:\n" + "\n".join(tool_lines[:30])
        )

    async def warm_up(self) -> None:
        """Prefill the stable system prompt once so the first real reply is
        fast (the local model otherwise spends ~30s reading it on turn one)."""
        await self.router.chat("hi", self._build_system_prompt([]), tools=self._build_tool_schemas())

    def _turn_notes(self, user_prompt: str = "", context: str = "") -> str:
        """Per-turn facts (clock, mood, what we know of the user), sent with
        the user message so the cached system prompt stays valid."""
        notes = [f"Current local date and time: {datetime.now().strftime('%A %d %B %Y, %I:%M %p')}"]
        emotional = self._human_context(user_prompt) if user_prompt else ""
        if emotional:
            notes.append(emotional)
        if context:  # what Atulya has learned about this user
            notes.append(context)
        return "[Notes for this turn]\n" + "\n".join(notes) + "\n\n"

    def _build_tool_schemas(self) -> list[dict[str, Any]]:
        """Build OpenAI-style function schemas for the model's native tool loop.

        Small models degrade with long tool lists, so only the top
        ``ATULYA_MAX_TOOL_SCHEMAS`` (default 14) are advertised, ranked
        assistant-first by ``_TOOL_PRIORITY``; unranked tools keep registry
        order. Tools that declare a JSON ``parameters`` schema expose it.
        """
        limit = max(1, int(os.environ.get("ATULYA_MAX_TOOL_SCHEMAS", "14")))
        listed = self.tools.list_tools()
        ranked = sorted(
            enumerate(listed),
            key=lambda item: (_TOOL_PRIORITY.get(item[1]["name"], 1000), item[0]),
        )
        schemas = []
        for _, tool in ranked[:limit]:
            obj = self.tools.get(tool["name"]) if hasattr(self.tools, "get") else None
            params = getattr(obj, "parameters", None) or {"type": "object", "properties": {}}
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"][:120],
                    "parameters": params,
                },
            })
        return schemas

    @staticmethod
    def _compose_prompt(prompt: str, history: list[dict[str, str]]) -> str:
        from atulya.buddhi.brain import active_brain

        # A tiny model copies earlier replies instead of answering, so it gets no history.
        trimmed = [] if active_brain() == "tiny" else clean_history(history)
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
    return AtulyaLLM(use_memory=True)
