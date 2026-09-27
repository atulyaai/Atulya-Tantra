"""Atulya Agent Core — tool registry + event wiring. Thinking goes through the
one cognitive kernel (atulya.cognition), so there is a single brain loop."""
from __future__ import annotations

import logging
from typing import Any, Callable

from .tools import TOOL_REGISTRY, get_tool_schemas, register_reminder_callback

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
        user: Any = None,
    ) -> str:
        """Answer through the cognitive kernel (safety gates, approvals, tools)."""
        if not self._llm:
            return "Atulya Agent is not connected to an LLM provider."
        from atulya.cognition import get_kernel

        response = await get_kernel(self._llm).handle(
            user_input, user=user, history=conversation_history, source="api",
        )
        return response.text

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
