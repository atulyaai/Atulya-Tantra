"""Tantra-style local model wrapper.

Wraps the LocalGGUFProvider with Atulya persona, tool awareness,
and Tantra-placeholder behavior until the real NP-DNA model is ready.
"""
from __future__ import annotations

import os
from typing import Any

from atulya.local_provider import LocalGGUFProvider
from atulya.persona import Persona


# Kept short on purpose: a ~0.5B model follows a few plain rules far better
# than a long brief, and replies are usually spoken aloud.
TANTRA_PLACEHOLDER_SYSTEM = """You are Atulya, a personal AI assistant in the style of Jarvis from Iron Man.
You run locally on the user's own computer.

How you speak:
- Calm, warm and confident, with a light dry wit.
- Answer in one or two short sentences unless the user asks for more.
- Reply in the language the user spoke: English, Hindi (in Devanagari) or Hinglish. No emojis.
- If you don't know something, say so briefly. Never make up facts or tool results."""


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