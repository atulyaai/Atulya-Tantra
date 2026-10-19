"""WebUI channel adapter: keep HTTP transport separate from reasoning."""
from __future__ import annotations

from collections.abc import Sequence

from tools.plugins.brain import Brain, BrainReply, Message


class WebUIChannel:
    """Pass a WebUI conversation to the configured Atulya brain."""

    def __init__(self, brain: Brain) -> None:
        self._brain = brain

    async def respond(self, conversation: Sequence[Message], *, system_instructions: str = "") -> BrainReply:
        return await self._brain.respond(conversation, system_instructions=system_instructions)

    async def stream(self, conversation: Sequence[Message], *, system_instructions: str = "", toolbox=None,
                     acknowledge: bool = False):
        async for chunk in self._brain.stream(conversation, system_instructions=system_instructions, toolbox=toolbox,
                                              acknowledge=acknowledge):
            yield chunk
