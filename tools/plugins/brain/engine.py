"""Atulya's text reasoning coordinator."""
from __future__ import annotations

import asyncio
import inspect
import json
import re
from collections.abc import Sequence

from atulya.persona import build_system_prompt
from .providers import ChatProvider
from .textcalls import TextCallFilter
from .types import BrainError, BrainReply, Message, ToolCall


# Instant acknowledgements from the user's words alone (no model round trip): spoken within ms.
_INTENT_FILLERS = (
    (re.compile(r"\b(weather|temperature|rain|forecast|humid|मौसम|बारिश)\b", re.I), "Checking the weather."),
    (re.compile(r"\b(news|headlines|खबर|समाचार)\b", re.I), "Pulling up the headlines."),
    (re.compile(r"\b(meeting|calendar|schedule|appointment)s?\b", re.I), "Checking your calendar."),
    (re.compile(r"\b(remember|recall|what did i (say|tell)|do you know my)\b", re.I), "Let me check what I remember."),
    (re.compile(r"\b(status|server|uptime|health)\b", re.I), "Checking the systems."),
)


def instant_ack(text: str) -> str:
    for pattern, phrase in _INTENT_FILLERS:
        if pattern.search(text):
            return phrase + " "
    return ""


_FILLERS = {
    "get_weather": "Checking the weather.",
    "get_news": "Pulling up the headlines.",
    "calculate": "",
    "get_time": "",
    "recall_memories": "Let me check what I remember.",
    "search_past_chats": "Looking through our past conversations.",
    "list_meetings": "Checking your calendar.",
    "add_meeting": "Adding that to your calendar.",
    "search_files": "Searching your files.",
    "use_skill": "On it.",
}


def _tool_filler(calls) -> str:
    """A short spoken acknowledgement for slow tools; empty for instant ones."""
    phrases = [_FILLERS.get(call.name, "") for call in calls]
    phrases = [phrase for phrase in dict.fromkeys(phrases) if phrase]
    return (" ".join(phrases[:2]) + " ") if phrases else ""


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
        acknowledge: bool = False,  # voice callers can explicitly request meaningful acknowledgements
    ):
        """Yield reply text chunks, running any tool calls the model makes in between.

        `toolbox` (tools/plugins/toolkit.Toolbox) is optional. Each round streams
        text immediately; requested tools run concurrently and their results are
        fed back. The final round is sent without tools so the model must answer.
        """
        stream_method = getattr(self._provider, "stream", None)
        stream_accepts_tools = stream_method is not None and any(
            parameter.name == "tools" or parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in inspect.signature(stream_method).parameters.values()
        )
        if toolbox:
            system_instructions = "\n\n".join(item for item in (system_instructions, toolbox.instructions()) if item)
            if not stream_accepts_tools:
                system_instructions += (
                    '\nTo request an action, output <tool_call>{"name":"tool_name",'
                    '"arguments":{}}</tool_call> using one of these tool schemas. '
                    'Wait for the tool result before claiming success.\n'
                    + json.dumps(toolbox.schemas)
                )
        messages = self._prepare_messages(conversation, system_instructions)
        rounds = toolbox.MAX_ROUNDS if toolbox else 1
        latest = next((item.content for item in reversed(messages) if item.role == "user"), "")
        early = instant_ack(latest) if toolbox and acknowledge else ""
        spoken: set[str] = set()  # each acknowledgement at most once per reply
        if early:
            spoken.add(early.strip())
            yield early  # spoken immediately while the model decides which tool to use
        try:
            for round_index in range(rounds):
                use_tools = bool(toolbox) and round_index < rounds - 1
                calls: list[ToolCall] = []
                text_parts: list[str] = []
                async def completion_stream():
                    yield await self._provider.complete(messages)

                stream = (
                    completion_stream() if stream_method is None else
                    stream_method(messages, tools=toolbox.schemas) if use_tools and stream_accepts_tools else
                    stream_method(messages)
                )
                text_filter = TextCallFilter()
                async for chunk in stream:
                    if isinstance(chunk, ToolCall):
                        if use_tools:
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
                if not text_parts and acknowledge:
                    # Say something immediately so voice users hear a reply while tools run.
                    filler = " ".join(part for part in _tool_filler(calls).replace(". ", ".|").split("|")
                                      if part.strip() and part.strip() not in spoken).strip()
                    filler = f"{filler} " if filler else ""
                    spoken.update(part.strip() for part in filler.replace(". ", ".|").split("|") if part.strip())
                    if filler:
                        text_parts.append(filler)
                        yield filler
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
            conversation, system_instructions=system_instructions, toolbox=toolbox, acknowledge=False)]).strip()
        if not text:
            raise BrainError("The model provider returned an empty reply")
        return BrainReply(text=text, provider=self._provider.name, model=self._provider.model)
