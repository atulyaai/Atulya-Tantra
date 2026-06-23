"""Atulya Agent Core — thin wrapper around the generic agent loop + tool registry."""
from __future__ import annotations

import logging
from typing import Any, Callable

from .tools import TOOL_REGISTRY, get_tool_schemas, register_reminder_callback
from .agent_loop import agent_loop

logger = logging.getLogger(__name__)


class AgentCore:
    """Thin coordinator. Initializes the agent loop and tool registry.

    Usage:
        agent = AgentCore()
        reply = await agent.process("set a reminder for 5 minutes")
    """

    def __init__(self, llm_provider: Any | None = None):
        self._llm = llm_provider
        self._callbacks: list[Callable] = []

        # Wire internal callbacks (reminders fire events)
        register_reminder_callback(self._on_event)

    def set_llm(self, llm: Any):
        self._llm = llm

    def register_callback(self, cb: Callable):
        """Register callback for push events (e.g. WebSocket).

        Signature: async def cb(event_type: str, data: dict)
        """
        self._callbacks.append(cb)

    async def _on_event(self, event_type: str, data: dict):
        for cb in self._callbacks:
            try:
                await cb(event_type, data)
            except Exception as e:
                logger.warning("Event callback error: %s", e)

    async def process(
        self,
        user_input: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
        """Run the agent loop on user input."""
        if not self._llm:
            return "Atulya Agent is not connected to an LLM provider."
        return await agent_loop(
            user_input=user_input,
            llm=self._llm,
            conversation_history=conversation_history,
        )

    def list_tools(self) -> list[dict]:
        """Return tool metadata (name + description)."""
        return [
            {"name": name, "description": info["description"]}
            for name, info in TOOL_REGISTRY.items()
        ]

    def get_tool_schemas(self) -> list[dict]:
        return get_tool_schemas()

    async def shutdown(self):
        logger.info("AgentCore shutdown")
