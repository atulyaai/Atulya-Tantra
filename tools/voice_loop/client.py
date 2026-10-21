"""The voice loop talks to the Atulya server like any other client: HTTP, a paired device token."""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx


class ServerClient:
    def __init__(self, url: str, token: str, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._http = httpx.AsyncClient(base_url=url.rstrip("/"), transport=transport,
                                       headers={"Authorization": f"Bearer {token}"},
                                       timeout=httpx.Timeout(120, connect=5))

    async def transcribe(self, wav: bytes, language: str = "") -> str:
        response = await self._http.post("/api/voice/transcribe", data={"language": language},
                                         files={"audio": ("turn.wav", wav, "audio/wav")})
        response.raise_for_status()
        return str(response.json().get("text", "")).strip()

    async def chat_stream(self, text: str, history: list[dict]) -> AsyncIterator[dict]:
        """Server-sent events of /api/chat in voice mode: {'text'}, {'confirm'}, {'ui'}, {'done'}, {'error'}.
        Closing the iterator closes the HTTP stream, which also stops the model's generation."""
        body = {"mode": "voice", "stream": True,
                "messages": [*history, {"role": "user", "content": text}]}
        async with self._http.stream("POST", "/api/chat", json=body) as response:
            response.raise_for_status()
            if not response.headers.get("content-type", "").startswith("text/event-stream"):
                yield json.loads(await response.aread())  # non-stream reply, e.g. a command plugin
                return
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    yield json.loads(line[6:])

    async def synthesize(self, text: str, language: str = "auto") -> bytes:
        response = await self._http.post("/api/voice/synthesize",
                                         json={"text": text[:1000], "language": language, "mode": "voice"})
        response.raise_for_status()
        return response.content

    async def aclose(self) -> None:
        await self._http.aclose()
