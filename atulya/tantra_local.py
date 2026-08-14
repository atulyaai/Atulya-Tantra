"""Tantra-style local model wrapper.

Wraps the LocalGGUFProvider with Atulya persona, tool awareness,
and Tantra-placeholder behavior until the real NP-DNA model is ready.
"""
from __future__ import annotations

import os
from typing import Any

from atulya.local_provider import LocalGGUFProvider
from atulya.persona import Persona


TANTRA_PLACEHOLDER_SYSTEM = """You are Atulya, a local-first AI assistant running on a compact 0.5B parameter model.
This model is a placeholder for the future Tantra NP-DNA (NeuroPlastic DNA) model - a sparse, CPU-native neural architecture.

Your capabilities:
- Answer questions, write code, analyze files
- Use tools when needed (file operations, web search, memory, etc.)
- Run locally without internet (except web_search tool)
- Maintain conversation context across sessions

Operating principles:
- Be helpful, honest, and concise
- Admit uncertainty - you're a small model standing in for a larger system
- Prefer local tools over external APIs
- Never hallucinate tool results - only use tools via the provided interface

When the Tantra NP-DNA model is ready, it will replace this placeholder with:
- Sparse routing across neural strands
- Genome-compressed memory
- CPU-native training and inference
- Neuroplastic adaptation"""


def _tool_to_schema(tool: dict[str, str]) -> dict[str, Any]:
    """Convert a simple tool entry to an OpenAI-style function schema."""
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": {"type": "object", "properties": {}},
        },
    }


class TantraLocalProvider(LocalGGUFProvider):
    """Tantra-style wrapper for the local 0.5B model."""

    def __init__(self, model_path: str | os.PathLike | None = None):
        super().__init__(model_path)
        self._persona = Persona()

    def name(self) -> str:
        return "Tantra Local (Qwen2.5-0.5B Placeholder)"

    def _build_tantra_system_prompt(self, user_system_prompt: str = "") -> str:
        """Combine Tantra placeholder context with user's system prompt."""
        parts = [TANTRA_PLACEHOLDER_SYSTEM]
        if user_system_prompt:
            parts.append(f"\n--- User Context ---\n{user_system_prompt}")
        return "\n".join(parts)

    async def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        tools: list[dict[str, Any]] | None = None,
    ) -> str:
        """Chat with Tantra-style system prompt injection + native tool calling."""
        tantra_system = self._build_tantra_system_prompt(system_prompt)
        return await super().chat(prompt, tantra_system, tools)


def create_tantra_local_provider(model_path: str | os.PathLike | None = None) -> TantraLocalProvider:
    """Factory for Tantra-style local provider."""
    return TantraLocalProvider(model_path)