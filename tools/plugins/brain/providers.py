"""Model provider interfaces and minimal local/compatible HTTP clients."""
from __future__ import annotations

import asyncio
import inspect
from dataclasses import replace
from collections.abc import Sequence
from collections.abc import Callable
import json
import time
from threading import Lock
from typing import Protocol

import httpx

from .types import BrainError, Message, ProviderError, ToolCall


def _text_tool_messages(messages, tools):
    if not tools:
        return messages
    prompt = ('To request a tool, output <tool_call>{"name":"tool_name","arguments":{}}</tool_call>. '
              'Wait for its result before claiming success. Available schemas: ' + json.dumps(list(tools)))
    if messages and messages[0].role == "system":
        return [replace(messages[0], content=messages[0].content + "\n" + prompt), *messages[1:]]
    return [Message(role="system", content=prompt), *messages]


async def _provider_stream(provider, messages, tools=None):
    method = getattr(provider, "stream", None)
    accepts_tools = method is not None and any(
        p.name == "tools" or p.kind == inspect.Parameter.VAR_KEYWORD
        for p in inspect.signature(method).parameters.values()
    )
    if not accepts_tools:
        messages = _text_tool_messages(messages, tools)
    if method is None:
        yield await provider.complete(messages)
    else:
        async for item in (method(messages, tools=tools) if tools and accepts_tools else method(messages)):
            yield item


class ChatProvider(Protocol):
    """A provider that accepts a conversation and returns assistant text."""

    @property
    def name(self) -> str: ...

    @property
    def model(self) -> str: ...

    async def complete(self, messages: Sequence[Message]) -> str: ...


class OpenAICompatibleProvider:
    """Client for OpenAI-style `/chat/completions` APIs.

    Pass the provider's API base URL (for example, one ending in `/v1`), model,
    and optional key explicitly. The provider never reads secrets from disk.
    """

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str = "",
        name: str = "OpenAI-compatible",
        timeout_seconds: float = 20.0,
        max_tokens: int | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("A model API base URL is required")
        if not model.strip():
            raise ValueError("A model name is required")
        self._base_url = base_url.rstrip("/")
        self._model = model.strip()
        self._api_key = api_key.strip()
        self._name = name.strip() or "OpenAI-compatible"
        self._timeout = timeout_seconds
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds, connect=min(5.0, timeout_seconds)),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=30),
        )
        self._owns_client = client is None
        if max_tokens is not None and max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        self._max_tokens = max_tokens
        # Set after a provider rejects the `tools` field so later turns skip it.
        self._tools_unsupported = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def model(self) -> str:
        return self._model

    @staticmethod
    def _wire_message(item: Message) -> dict:
        if item.role == "tool":
            return {"role": "tool", "tool_call_id": item.tool_call_id, "content": item.content}
        wire: dict = {
            "role": item.role,
            "content": (
                [
                    {"type": "text", "text": item.content},
                    {"type": "image_url", "image_url": {"url": item.image_url}},
                ]
                if item.image_url else item.content
            ),
        }
        if item.tool_calls:
            wire["content"] = item.content or None
            wire["tool_calls"] = [
                {"id": call.id, "type": "function", "function": {"name": call.name, "arguments": call.arguments}}
                for call in item.tool_calls
            ]
        return wire

    def _payload(self, messages: Sequence[Message], *, stream: bool, tools: Sequence[dict] | None = None) -> dict:
        payload = {
            "model": self._model,
            "messages": [self._wire_message(item) for item in messages],
            "stream": stream,
        }
        if tools and not self._tools_unsupported:
            payload["tools"] = list(tools)
        if self._max_tokens is not None:
            payload["max_tokens"] = self._max_tokens
        # Gemini 2.5 "thinks" before answering by default (seconds of delay); a voice assistant wants the answer.
        if "generativelanguage.googleapis.com" in self._base_url and "2.5" in str(payload.get("model", "")):
            payload["reasoning_effort"] = "none" if "flash" in str(payload["model"]) else "low"
        return payload

    def _headers(self, *, stream: bool = False) -> dict[str, str]:
        headers = {"Accept": "text/event-stream" if stream else "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def complete(self, messages: Sequence[Message]) -> str:
        try:
            response = await self._client.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=self._payload(messages, stream=False),
                timeout=httpx.Timeout(self._timeout, connect=min(5.0, self._timeout)),
            )
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"{self.name} returned HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
            ) from None
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"Could not get a valid reply from {self.name}") from exc

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"{self.name} returned an unexpected response") from exc
        if isinstance(content, list):
            content = "".join(
                block.get("text", "") for block in content if isinstance(block, dict)
            )
        if not isinstance(content, str) or not content.strip():
            raise ProviderError(f"{self.name} returned an empty reply")
        return content.strip()

    async def stream(self, messages: Sequence[Message], tools: Sequence[dict] | None = None):
        """Yield text deltas, then any requested ToolCall objects once the turn ends.

        If the provider rejects the `tools` field before producing output, the
        turn is retried once without tools and tools are skipped from then on.
        """
        if tools and self._tools_unsupported:
            async for item in self._stream_once(_text_tool_messages(messages, tools), None):
                yield item
            return
        produced = False
        try:
            async for item in self._stream_once(messages, tools):
                produced = True
                yield item
        except ProviderError as exc:
            if not tools or produced or self._tools_unsupported or exc.status_code not in {400, 404, 405, 422}:
                raise
            self._tools_unsupported = True
            async for item in self._stream_once(_text_tool_messages(messages, tools), None):
                yield item

    async def _stream_once(self, messages: Sequence[Message], tools: Sequence[dict] | None):
        pending_calls: dict[int, dict[str, str]] = {}
        try:
            async with self._client.stream(
                "POST", f"{self._base_url}/chat/completions", headers=self._headers(stream=True),
                json=self._payload(messages, stream=True, tools=tools),
                timeout=httpx.Timeout(self._timeout, connect=min(5.0, self._timeout)),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        body = json.loads(data)
                        choices = body.get("choices") or [{}]
                        delta_body = choices[0].get("delta") or {}
                        delta = delta_body.get("content") or ""
                        call_deltas = delta_body.get("tool_calls") or []
                    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
                        raise ProviderError(f"{self.name} returned an unexpected stream") from exc
                    for position, call in enumerate(call_deltas):
                        if not isinstance(call, dict):
                            continue
                        slot = pending_calls.setdefault(
                            int(call.get("index", position)), {"id": "", "name": "", "arguments": ""}
                        )
                        function = call.get("function") or {}
                        slot["id"] = call.get("id") or slot["id"]
                        slot["name"] += function.get("name") or ""
                        arguments = function.get("arguments") or ""
                        slot["arguments"] += arguments if isinstance(arguments, str) else json.dumps(arguments)
                    if isinstance(delta, list):
                        delta = "".join(part.get("text", "") for part in delta if isinstance(part, dict))
                    if isinstance(delta, str) and delta:
                        yield delta
            for index in sorted(pending_calls):
                slot = pending_calls[index]
                if slot["name"]:
                    yield ToolCall(slot["id"] or f"call_{index}", slot["name"], slot["arguments"] or "{}")
        except httpx.HTTPStatusError as exc:
            raise ProviderError(f"{self.name} returned HTTP {exc.response.status_code}", status_code=exc.response.status_code) from None
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"Could not get a valid reply from {self.name}") from exc

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


class OllamaProvider:
    """Client for a locally running Ollama chat endpoint."""

    def __init__(
        self,
        *,
        model: str,
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: float = 120.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not model.strip():
            raise ValueError("An Ollama model name is required")
        self._model = model.strip()
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds, connect=min(5.0, timeout_seconds)),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5, keepalive_expiry=30),
        )
        self._owns_client = client is None

    @property
    def name(self) -> str:
        return "Ollama"

    @property
    def model(self) -> str:
        return self._model

    async def complete(self, messages: Sequence[Message]) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": item.role, "content": item.content,
                 **({"images": [item.image_url.split(",", 1)[1]]} if item.image_url else {})}
                for item in messages
            ],
            "stream": False,
        }
        try:
            response = await self._client.post(
                f"{self._base_url}/api/chat", json=payload,
                timeout=httpx.Timeout(self._timeout, connect=min(5.0, self._timeout)),
            )
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"Ollama returned HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
            ) from None
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError("Could not connect to Ollama or read its response") from exc

        try:
            content = body["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise ProviderError("Ollama returned an unexpected response") from exc
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("Ollama returned an empty reply")
        return content.strip()

    @staticmethod
    def _wire_message(item: Message) -> dict:
        wire: dict = {"role": item.role, "content": item.content}
        if item.image_url:
            wire["images"] = [item.image_url.split(",", 1)[1]]
        if item.tool_calls:
            wire["tool_calls"] = [
                {"function": {"name": call.name, "arguments": json.loads(call.arguments or "{}")}}
                for call in item.tool_calls
            ]
        return wire

    async def stream(self, messages: Sequence[Message], tools: Sequence[dict] | None = None):
        payload = {
            "model": self._model,
            "messages": [self._wire_message(item) for item in messages],
            "stream": True,
        }
        if tools:
            payload["tools"] = list(tools)
        try:
            async with self._client.stream(
                "POST", f"{self._base_url}/api/chat", json=payload,
                timeout=httpx.Timeout(self._timeout, connect=min(5.0, self._timeout)),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        body = json.loads(line)
                        chunk = body.get("message", {}).get("content", "")
                        calls = body.get("message", {}).get("tool_calls") or []
                    except (ValueError, TypeError, AttributeError) as exc:
                        raise ProviderError("Ollama returned an unexpected stream") from exc
                    if isinstance(chunk, str) and chunk:
                        yield chunk
                    for index, call in enumerate(calls):
                        function = call.get("function", {}) if isinstance(call, dict) else {}
                        if function.get("name"):
                            arguments = function.get("arguments", {})
                            yield ToolCall(f"call_{index}", function["name"],
                                           arguments if isinstance(arguments, str) else json.dumps(arguments))
                    if body.get("done"):
                        break
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"Ollama returned HTTP {exc.response.status_code}", status_code=exc.response.status_code
            ) from None
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError("Could not connect to Ollama or read its response") from exc

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


class AutomaticProvider:
    """Race at most two cloud candidates, then lazily start local fallback."""

    def __init__(
        self,
        providers: Sequence[ChatProvider],
        *,
        local_provider: ChatProvider | None = None,
        start_local: Callable[[], None] | None = None,
        stop_local: Callable[[], None] | None = None,
        hedge_delay_seconds: float = 1.25,
        attempt_timeout_seconds: float = 20.0,
        provider_budget_seconds: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._providers = list(providers)
        self._local_provider = local_provider
        self._start_local = start_local
        self._stop_local = stop_local
        self._active: ChatProvider | None = None
        self._unavailable: set[int] = set()
        self._local_started = False
        self._local_lock = Lock()
        self._hedge_delay = max(0.0, hedge_delay_seconds)
        self._attempt_timeout = max(1.0, attempt_timeout_seconds)
        self._provider_budget = max(1.0, provider_budget_seconds)
        self._http_client = http_client
        self._cooldowns: dict[int, float] = {}

    @property
    def name(self) -> str:
        return self._active.name if self._active else "Automatic model selection"

    @property
    def model(self) -> str:
        return self._active.model if self._active else "automatic"

    @property
    def active_provider(self) -> ChatProvider | None:
        return self._active

    async def complete(self, messages: Sequence[Message]) -> str:
        providers = [provider for provider in self._ordered_providers() if self._available(provider)]
        running: dict[asyncio.Task, ChatProvider] = {}
        next_index = 0
        deadline = asyncio.get_running_loop().time() + self._provider_budget

        def launch(provider: ChatProvider) -> None:
            task = asyncio.create_task(asyncio.wait_for(
                provider.complete(messages), timeout=self._attempt_timeout
            ))
            running[task] = provider

        if providers:
            launch(providers[0])
            next_index = 1
        while running or next_index < len(providers):
            can_hedge = self._hedge_delay > 0 and next_index < len(providers) and len(running) < 2
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                for pending in running:
                    pending.cancel()
                if running:
                    await asyncio.gather(*running, return_exceptions=True)
                running.clear()
                break
            if running:
                done, _ = await asyncio.wait(
                    running, timeout=min(self._hedge_delay, remaining) if can_hedge else remaining,
                    return_when=asyncio.FIRST_COMPLETED,
                )
            else:
                done = set()
            if not done and can_hedge:
                if asyncio.get_running_loop().time() >= deadline:
                    continue
                launch(providers[next_index])
                next_index += 1
                continue
            if not done and asyncio.get_running_loop().time() >= deadline:
                for pending in running:
                    pending.cancel()
                if running:
                    await asyncio.gather(*running, return_exceptions=True)
                running.clear()
                break
            for task in done:
                provider = running.pop(task)
                try:
                    reply = task.result()
                except asyncio.CancelledError:
                    continue
                except ProviderError as exc:
                    self._record_failure(provider, exc.status_code)
                except (asyncio.TimeoutError, BrainError):
                    self._record_failure(provider, None)
                except Exception:
                    self._record_failure(provider, None)
                else:
                    self._active = provider
                    for pending in running:
                        pending.cancel()
                    if running:
                        await asyncio.gather(*running, return_exceptions=True)
                    return reply
            while next_index < len(providers) and len(running) < 2:
                launch(providers[next_index])
                next_index += 1

        if self._local_provider is not None:
            try:
                await asyncio.to_thread(self._ensure_local)
                reply = await self._local_provider.complete(messages)
            except Exception as exc:
                raise ProviderError("No configured model provider could answer. Check provider access or local setup.") from exc
            self._active = self._local_provider
            return reply

        raise ProviderError("No configured model provider is available.")

    def _ordered_providers(self) -> list[ChatProvider]:
        providers = list(self._providers)
        if self._active in providers:
            providers.remove(self._active)
            providers.insert(0, self._active)
        return providers

    def _available(self, provider: ChatProvider) -> bool:
        identity = id(provider)
        if self._cooldowns.get(identity, 0) <= time.monotonic():
            self._cooldowns.pop(identity, None)
        return identity not in self._unavailable and self._cooldowns.get(identity, 0) <= time.monotonic()

    def _record_failure(self, provider: ChatProvider, status_code: int | None) -> None:
        identity = id(provider)
        if status_code in {400, 401, 403, 404, 410}:
            self._unavailable.add(identity)
        elif status_code == 402:
            self._cooldowns[identity] = time.monotonic() + 3600
        elif status_code == 429:
            self._cooldowns[identity] = time.monotonic() + 60
        else:
            self._cooldowns[identity] = time.monotonic() + 8

    async def stream(self, messages: Sequence[Message], tools: Sequence[dict] | None = None):
        """Hedge initial token only; never replay partial content from another model."""
        providers = [provider for provider in self._ordered_providers() if self._available(provider)]
        running: dict[asyncio.Task, tuple[ChatProvider, object]] = {}
        next_index = 0
        deadline = asyncio.get_running_loop().time() + self._provider_budget

        async def first_token(iterator):
            return iterator, await asyncio.wait_for(iterator.__anext__(), timeout=self._attempt_timeout)

        def launch(provider: ChatProvider) -> None:
            iterator = _provider_stream(provider, messages, tools).__aiter__()
            running[asyncio.create_task(first_token(iterator))] = (provider, iterator)

        if providers:
            launch(providers[0])
            next_index = 1
        winner = None
        while running or next_index < len(providers):
            can_hedge = self._hedge_delay > 0 and next_index < len(providers) and len(running) < 2
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                for pending in running:
                    pending.cancel()
                if running:
                    await asyncio.gather(*running, return_exceptions=True)
                running.clear()
                break
            if running:
                done, _ = await asyncio.wait(
                    running, timeout=min(self._hedge_delay, remaining) if can_hedge else remaining,
                    return_when=asyncio.FIRST_COMPLETED,
                )
            else:
                done = set()
            if not done and can_hedge:
                if asyncio.get_running_loop().time() >= deadline:
                    continue
                launch(providers[next_index])
                next_index += 1
                continue
            if not done and asyncio.get_running_loop().time() >= deadline:
                for pending in running:
                    pending.cancel()
                if running:
                    await asyncio.gather(*running, return_exceptions=True)
                running.clear()
                break
            for task in done:
                provider, iterator = running.pop(task)
                try:
                    iterator, token = task.result()
                except ProviderError as exc:
                    self._record_failure(provider, exc.status_code)
                except Exception as exc:
                    self._record_failure(provider, getattr(exc, "status_code", None))
                else:
                    winner = provider, iterator, token
                    break
            if winner:
                losers = list(running.items())
                for task, (_provider, _iterator) in losers:
                    task.cancel()
                if losers:
                    await asyncio.gather(*(task for task, _ in losers), return_exceptions=True)
                for _task, (_provider, iterator) in losers:
                    close = getattr(iterator, "aclose", None)
                    if close is not None:
                        try:
                            await close()
                        except RuntimeError:
                            pass
                break
            while next_index < len(providers) and len(running) < 2:
                launch(providers[next_index])
                next_index += 1
        if winner:
            provider, iterator, token = winner
            self._active = provider
            if token:
                yield token
            try:
                async for token in iterator:
                    if token:
                        yield token
            except Exception as exc:
                raise ProviderError("The selected model stream ended unexpectedly.") from exc
            return
        if self._local_provider is not None:
            try:
                await asyncio.to_thread(self._ensure_local)
                async for token in _provider_stream(self._local_provider, messages, tools):
                    if token:
                        yield token
                self._active = self._local_provider
                return
            except Exception as exc:
                raise ProviderError("No configured model provider could answer. Check provider access or local setup.") from exc
        raise ProviderError("No configured model provider is available.")

    def warm(self) -> None:
        """Start the local model up front when no cloud provider is configured."""
        if not self._providers and self._local_provider is not None:
            self._ensure_local()

    def _ensure_local(self) -> None:
        with self._local_lock:
            if self._local_started:
                return
            if self._start_local is not None:
                self._start_local()
            self._local_started = True

    def close(self) -> None:
        if self._local_started and self._stop_local is not None:
            self._stop_local()

    async def aclose(self) -> None:
        self.close()
        clients = {
            id(getattr(provider, "_client", None)): getattr(provider, "_client", None)
            for provider in [*self._providers, self._local_provider]
            if provider is not None
        }
        if self._http_client is not None:
            clients[id(self._http_client)] = self._http_client
        for client in clients.values():
            if client is not None:
                await client.aclose()
