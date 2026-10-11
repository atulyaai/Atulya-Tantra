"""Atulya's text-only reasoning layer.

Voice transcription is expected to produce user messages; speech synthesis can
read the resulting BrainReply. Tools are supplied per request by the caller
(see tools/plugins/toolkit.py); the brain only runs the bounded call loop.
"""
from .engine import Brain
from .providers import AutomaticProvider, ChatProvider, OllamaProvider, OpenAICompatibleProvider
from .types import BrainError, BrainReply, Message, ProviderError, ToolCall

__all__ = [
    "Brain",
    "BrainError",
    "BrainReply",
    "AutomaticProvider",
    "ChatProvider",
    "Message",
    "OllamaProvider",
    "OpenAICompatibleProvider",
    "ProviderError",
    "ToolCall",
]
