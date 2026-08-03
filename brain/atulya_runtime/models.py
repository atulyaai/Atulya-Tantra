"""Text-only model providers. Providers cannot execute Atulya actions."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Protocol

from .config import Settings


class ModelProvider(Protocol):
    name: str

    def complete(self, messages: list[dict[str, str]]) -> str: ...


class OpenAICompatibleProvider:
    """Works with local OpenAI-compatible servers such as Ollama or vLLM."""

    name = "openai-compatible"

    def __init__(self, *, base_url: str, api_key: str, model: str, timeout_seconds: float):
        self.endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_settings(cls, settings: Settings) -> "OpenAICompatibleProvider | None":
        if not settings.model_base_url or not settings.model_name:
            return None
        return cls(
            base_url=settings.model_base_url,
            api_key=settings.model_api_key or "",
            model=settings.model_name,
            timeout_seconds=settings.model_timeout_seconds,
        )

    def complete(self, messages: list[dict[str, str]]) -> str:
        payload = json.dumps({"model": self.model, "messages": messages, "temperature": 0.2}).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Model provider unavailable: {error}") from error
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("Model provider returned an invalid completion payload.") from error
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Model provider returned an empty completion.")
        return content.strip()
