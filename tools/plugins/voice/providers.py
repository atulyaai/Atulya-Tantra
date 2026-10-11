"""Provider-neutral contracts for speech recognition and synthesis."""
from __future__ import annotations

from typing import Protocol


class VoiceError(RuntimeError):
    """A speech provider failed or returned unusable audio or text."""


class SpeechInput(Protocol):
    """Convert captured audio into text; implementations must be explicitly selected."""

    async def transcribe(self, audio: bytes, *, content_type: str, language: str) -> str: ...


class SpeechOutput(Protocol):
    """Convert text into audio without choosing a provider implicitly."""

    async def synthesize(self, text: str, *, voice: str, language: str) -> bytes: ...
