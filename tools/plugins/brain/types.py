"""Shared message and result types for Atulya's reasoning layer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A model's request to run one named tool with JSON-encoded arguments."""

    id: str
    name: str
    arguments: str = "{}"


@dataclass(frozen=True, slots=True)
class Message:
    """One text or image-grounded message exchanged with the model.

    Assistant messages may carry tool calls instead of text; tool messages
    carry one tool's result and the id of the call they answer.
    """

    role: Role
    content: str
    image_url: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None

    def __post_init__(self) -> None:
        if self.role not in {"system", "user", "assistant", "tool"}:
            raise ValueError(f"Unsupported message role: {self.role}")
        if not isinstance(self.content, str):
            raise ValueError("Message content must be a string")
        if not self.content.strip() and not (self.role == "assistant" and self.tool_calls):
            raise ValueError("Message content must be a non-empty string")
        if self.role == "tool" and not self.tool_call_id:
            raise ValueError("Tool results must reference a tool call")
        if self.image_url is not None and not self.image_url.startswith("data:image/jpeg;base64,"):
            raise ValueError("Image attachments must be JPEG data URLs")


@dataclass(frozen=True, slots=True)
class BrainReply:
    """Text returned by a configured model provider."""

    text: str
    provider: str
    model: str


class BrainError(RuntimeError):
    """Base error for reasoning or model-provider failures."""


class ProviderError(BrainError):
    """A model provider could not return a usable reply."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
