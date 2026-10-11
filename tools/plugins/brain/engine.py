"""Atulya's text reasoning coordinator."""
from __future__ import annotations

import asyncio
import inspect
from collections.abc import Sequence

from atulya.persona import build_system_prompt
from .providers import ChatProvider
from .textcalls import TextCallFilter
from .types import BrainError, BrainReply, Message, ToolCall


class Brain:
    """Turn conversation text into a model reply.

    Brain owns message validation and delegates identity instructions to the
    persona layer and model transport to a provider. It does not access
    microphones, memory stores, desktop controls, or API keys on its own; tools are
    only run through a caller-supplied toolbox.
    """

    def __init__(
        self,
        provider: ChatProvider,
        *,
        assistant_name: str = "Atulya",
        system_instructions: str = "",
    ) -> None:
        if not assistant_name.strip():
            raise ValueError("Assistant name must not be empty")
        self._provider = provider
        self._assistant_name = assistant_name.strip()
        self._system_instructions = system_instructions.strip()

    async def respond(
        self,
        conversation: Sequence[Message],
        *,
        system_instructions: str = "",
    ) -> BrainReply:
        """Generate a reply from text-only conversation history."""
        messages = self._prepare_messages(conversation, system_instructions)
        try:
            text = await self._provider.complete(messages)
        except BrainError:
            raise
        except Exception as exc:
            raise BrainError("The model provider failed while generating a reply") from exc
        if not isinstance(text, str) or not text.strip():
            raise BrainError("The model provider returned an empty reply")
        return BrainReply(text=text.strip(), provider=self._provider.name, model=self._provider.model)

    @property
    def provider_name(self) -> str:
        return self._provider.name

    @property
    def model_name(self) -> str:
        return self._provider.model

    def _prepare_messages(self, conversation: Sequence[Message], system_instructions: str) -> list[Message]:
        if not conversation:
            raise ValueError("Conversation must include at least one message")
        if not any(message.role == "user" for message in conversation):
            raise ValueError("Conversation must include a user message")

        trusted_instructions = [
            self._system_instructions,
            system_instructions.strip(),
            *(message.content for message in conversation if message.role == "system"),
        ]
        prompt = build_system_prompt(
            self._assistant_name,
            "\n\n".join(item for item in trusted_instructions if item),
        )
        messages = [Message(role="system", content=prompt)]
        messages.extend(message for message in conversation if message.role != "system")
        if messages[-1].role != "user":
            raise ValueError("The latest conversation message must be from the user")

        return messages

    async def stream(
        self,
        conversation: Sequence[Message],
        *,
        system_instructions: str = "",
        toolbox=None,
    ):
        """Yield reply text chunks, running any tool calls the model makes in between.

        `toolbox` (tools/plugins/toolkit.Toolbox) is optional. Each round streams
        text immediately; requested tools run concurrently and their results are
        fed back. The final round is sent without tools so the model must answer.
        """
        stream_method = getattr(self._provider, "stream", None)
        if stream_method is None or "tools" not in inspect.signature(stream_method).parameters:
            toolbox = None
        if toolbox:
            system_instructions = "\n\n".join(item for item in (system_instructions, toolbox.instructions()) if item)
        messages = self._prepare_messages(conversation, system_instructions)
        rounds = toolbox.MAX_ROUNDS if toolbox else 1
        try:
            if stream_method is None:
                text = await self._provider.complete(messages)
                if text:
                    yield text
                return
            for round_index in range(rounds):
                use_tools = bool(toolbox) and round_index < rounds - 1
                calls: list[ToolCall] = []
                text_parts: list[str] = []
                stream = stream_method(messages, tools=toolbox.schemas) if use_tools else stream_method(messages)
                text_filter = TextCallFilter()
                async for chunk in stream:
                    if isinstance(chunk, ToolCall):
                        calls.append(chunk)
                    elif chunk:
                        visible = text_filter.feed(chunk)
                        if visible:
                            text_parts.append(visible)
                            yield visible
                text_calls, leftover = text_filter.finish()
                if use_tools:
                    calls.extend(text_calls)
                elif text_calls:
                    leftover = ""  # tools are closed this round: never show raw call markup
                if leftover:
                    text_parts.append(leftover)
                    yield leftover
                if not calls:
                    return
                results = await asyncio.gather(*(toolbox.call(call.name, call.arguments) for call in calls))
                messages.append(Message(role="assistant", content="".join(text_parts), tool_calls=tuple(calls)))
                messages.extend(
                    Message(role="tool", content=result or "(no result)", tool_call_id=call.id)
                    for call, result in zip(calls, results)
                )
        except BrainError:
            raise
        except Exception as exc:
            raise BrainError("The model provider failed while generating a reply") from exc

    async def respond_with_tools(self, conversation: Sequence[Message], toolbox, *, system_instructions: str = "") -> BrainReply:
        """Non-streaming convenience for channels like Telegram."""
        text = "".join([chunk async for chunk in self.stream(
            conversation, system_instructions=system_instructions, toolbox=toolbox)]).strip()
        if not text:
            raise BrainError("The model provider returned an empty reply")
        return BrainReply(text=text, provider=self._provider.name, model=self._provider.model)
