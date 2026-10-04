"""Atulya Intelligence Provider System.

Decouples the operating system from any single LLM brain.
Enables pluggable brains (Gemini, Claude, OpenAI, OpenRouter, NVIDIA NIM, Ollama)
with automatic failover fallbacks.
"""
from __future__ import annotations

import asyncio
import json
import re
import logging
import os
import time
import inspect
import urllib.request
import urllib.error
from typing import Any, AsyncIterator

from atulya.buddhi.providers_catalog import CATALOG  # noqa: E402

logger = logging.getLogger(__name__)


def _supports_tools(provider: Any) -> bool:
    """True if provider.chat accepts a tools keyword argument."""
    chat = getattr(provider, "chat", None)
    if not callable(chat):
        return False
    try:
        return "tools" in inspect.signature(chat).parameters
    except (TypeError, ValueError):
        return False


def _chunk_stream_text(text: str, size: int = 28) -> list[str]:
    """Split a full response into small pieces for naive streaming fallback."""
    if not text:
        return [""]
    chunks: list[str] = []
    current = ""
    for word in text.split(" "):
        candidate = f"{current} {word}".strip()
        if len(candidate) >= size and current:
            chunks.append(current + " ")
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


class IntelligenceProvider:
    """Base interface for pluggable intelligence providers."""
    
    def name(self) -> str:
        raise NotImplementedError
        
    def is_available(self) -> bool:
        raise NotImplementedError
        
    async def chat(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError


class OllamaProvider(IntelligenceProvider):
    """Local Ollama model provider running on localhost."""
    
    def __init__(self, model_name: str = "llama3"):
        self.model_name = os.environ.get("ATULYA_OLLAMA_MODEL", model_name)
        self.host = os.environ.get("ATULYA_OLLAMA_HOST", "http://localhost:11434")
        
    def name(self) -> str:
        return f"Ollama ({self.model_name})"
        
    def is_available(self) -> bool:
        try:
            url = f"{self.host}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1.5) as response:
                return response.status == 200
        except Exception:
            return False
            
    async def chat(self, prompt: str, system_prompt: str = "") -> str:
        try:
            url = f"{self.host}/api/generate"
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url, 
                data=data, 
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10.0) as response:
                if response.status == 200:
                    res_body = json.loads(response.read().decode("utf-8"))
                    return res_body.get("response", "").strip()
                raise RuntimeError(f"Ollama returned status {response.status}")
        except Exception as e:
            logger.warning(f"OllamaProvider chat failed: {e}")
            raise e


class OpenAIProvider(IntelligenceProvider):
    """OpenAI API Provider."""
    
    def name(self) -> str:
        return "OpenAI"
        
    def is_available(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY"))
        
    async def chat(self, prompt: str, system_prompt: str = "") -> str:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not configured")
        try:
            url = "https://api.openai.com/v1/chat/completions"
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": os.environ.get("ATULYA_OPENAI_MODEL", "gpt-4o-mini"),
                "messages": messages,
                "max_tokens": 150
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10.0) as response:
                if response.status == 200:
                    res_body = json.loads(response.read().decode("utf-8"))
                    return res_body["choices"][0]["message"]["content"].strip()
                raise RuntimeError(f"OpenAI returned status {response.status}")
        except Exception as e:
            logger.warning(f"OpenAIProvider chat failed: {e}")
            raise e


class GeminiProvider(IntelligenceProvider):
    """Google Gemini API Provider."""
    
    def name(self) -> str:
        return "Gemini"
        
    def is_available(self) -> bool:
        return bool(os.environ.get("GEMINI_API_KEY"))
        
    async def chat(self, prompt: str, system_prompt: str = "") -> str:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not configured")
        try:
            model = os.environ.get("ATULYA_GEMINI_MODEL", "gemini-1.5-flash")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            
            contents = []
            if system_prompt:
                contents.append({"role": "user", "parts": [{"text": f"System Guidelines: {system_prompt}"}]})
                contents.append({"role": "model", "parts": [{"text": "Understood. I will operate within those guidelines."}]})
            contents.append({"role": "user", "parts": [{"text": prompt}]})
            
            payload = {
                "contents": contents,
                "generationConfig": {
                    "maxOutputTokens": 150,
                    "temperature": 0.7
                }
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10.0) as response:
                if response.status == 200:
                    res_body = json.loads(response.read().decode("utf-8"))
                    return res_body["candidates"][0]["content"]["parts"][0]["text"].strip()
                raise RuntimeError(f"Gemini returned status {response.status}")
        except Exception as e:
            logger.warning(f"GeminiProvider chat failed: {e}")
            raise e


def _looks_like_safety_label(text: str) -> bool:
    """Content-safety models reply with labels like "harassment" or "safe/unsafe", not answers."""
    words = re.sub(r"[^a-z ]", " ", (text or "").lower()).split()
    labels = {"safe", "unsafe", "harassment", "safety", "violence", "hate", "sexual", "self", "harm", "illegal",
              "category", "violation", "content", "policy", "none"}
    return 0 < len(words) <= 6 and all(w in labels for w in words)


class OpenRouterProvider(IntelligenceProvider):
    """OpenRouter: one key, many models. Tries a list of free models until one answers.

    Free models are often rate-limited (429) or "think" so long they return no
    text, so each is tried in turn. Set ``ATULYA_OPENROUTER_MODEL`` to one model
    or a comma-separated list.
    """

    URL = "https://openrouter.ai/api/v1/chat/completions"
    DEFAULT_MODELS = (
        "qwen/qwen3.8-27b:free",
        "google/gemma-4-31b-it:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
    )

    def name(self) -> str:
        return "OpenRouter"

    KEY_VARS = ("OPENROUTER_API_KEY",)
    MODEL_VAR = "ATULYA_OPENROUTER_MODEL"

    @classmethod
    def _key(cls) -> str:
        return next((os.environ[v] for v in cls.KEY_VARS if os.environ.get(v)), "")

    def is_available(self) -> bool:
        return bool(self._key())

    @classmethod
    def models(cls) -> list[str]:
        raw = os.environ.get(cls.MODEL_VAR, "")
        listed = [m.strip() for m in raw.split(",") if m.strip()]
        return listed or list(cls.DEFAULT_MODELS)

    def _ask(self, model: str, messages: list[dict[str, str]]) -> str:
        payload = {"model": model, "messages": messages, "max_tokens": 1024}
        req = urllib.request.Request(
            self.URL, data=json.dumps(payload).encode("utf-8"), method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._key()}",
                "HTTP-Referer": "https://github.com/atulyaai/Atulya-Tantra",
                "X-Title": "Atulya OS",
            },
        )
        with urllib.request.urlopen(req, timeout=30.0) as response:
            body = json.loads(response.read().decode("utf-8"))
        text = (body["choices"][0]["message"].get("content") or "").strip()
        if _looks_like_safety_label(text):
            return ""  # a moderation model answered instead of a chat model: treat as no answer
        # Some reasoning models wrap their thinking in <think>…</think>.
        return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()

    async def chat(self, prompt: str, system_prompt: str = "") -> str:
        if not self._key():
            raise ValueError(f"{self.KEY_VARS[0]} is not configured")
        messages = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + [
            {"role": "user", "content": prompt}]
        failures: list[str] = []
        for model in self.models():
            try:
                text = await asyncio.to_thread(self._ask, model, messages)
            except Exception as exc:  # noqa: BLE001 - 429, timeouts, 5xx: try the next model
                failures.append(f"{model}: {exc}")
                continue
            if text:
                return text
            failures.append(f"{model}: empty reply")
        logger.warning("%s: no model answered (%s)", self.name(), "; ".join(failures))
        raise RuntimeError(f"No {self.name()} model answered: " + "; ".join(failures))


class OpenCodeGoProvider(OpenRouterProvider):
    """OpenCode Go: an OpenAI-style endpoint (``OPENCODE_API_KEY``). Models and URL can be changed in .env."""

    KEY_VARS = ("OPENCODE_API_KEY", "OPENCODE_GO_API_KEY")
    MODEL_VAR = "ATULYA_OPENCODE_MODEL"
    DEFAULT_MODELS = ("deepseek-v4-flash", "kimi-k2.5", "glm-5.2")

    @property
    def URL(self) -> str:  # noqa: N802 - mirrors the parent's class attribute
        base = os.environ.get("ATULYA_OPENCODE_URL", "https://opencode.ai/zen/go/v1").rstrip("/")
        return base + "/chat/completions"

    def name(self) -> str:
        return "OpenCode Go"


class NvidiaNimProvider(IntelligenceProvider):
    """NVIDIA NIM Inference Microservice Provider."""
    
    def name(self) -> str:
        return "NVIDIA NIM"
        
    def is_available(self) -> bool:
        return bool(os.environ.get("NVIDIA_API_KEY") or os.environ.get("NIM_API_KEY"))
        
    async def chat(self, prompt: str, system_prompt: str = "") -> str:
        api_key = os.environ.get("NVIDIA_API_KEY") or os.environ.get("NIM_API_KEY")
        if not api_key:
            raise ValueError("NVIDIA_API_KEY is not configured")
        try:
            url = "https://integrate.api.nvidia.com/v1/chat/completions"
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            model = os.environ.get("ATULYA_NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": 150,
                "temperature": 0.7
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10.0) as response:
                if response.status == 200:
                    res_body = json.loads(response.read().decode("utf-8"))
                    return res_body["choices"][0]["message"]["content"].strip()
                raise RuntimeError(f"NVIDIA NIM returned status {response.status}")
        except Exception as e:
            logger.warning(f"NvidiaNimProvider chat failed: {e}")
            raise e


class AnthropicProvider(IntelligenceProvider):
    """Claude through the Anthropic Messages API: fast and smart. Leads the chain when a key is set."""

    URL = "https://api.anthropic.com/v1/messages"

    def name(self) -> str:
        return f"Claude ({self._model()})"

    @staticmethod
    def _model() -> str:
        return os.environ.get("ATULYA_CLAUDE_MODEL", "claude-haiku-4-5-20251001")

    def is_available(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    def _request(self, prompt: str, system_prompt: str) -> str:
        payload: dict[str, Any] = {
            "model": self._model(),
            "max_tokens": int(os.environ.get("ATULYA_CLAUDE_MAX_TOKENS", "700")),
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            payload["system"] = system_prompt
        req = urllib.request.Request(
            self.URL, data=json.dumps(payload).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", "anthropic-version": "2023-06-01",
                     "x-api-key": os.environ.get("ANTHROPIC_API_KEY", "")},
        )
        with urllib.request.urlopen(req, timeout=40.0) as response:
            body = json.loads(response.read().decode("utf-8"))
        return "".join(block.get("text", "") for block in body.get("content", []) if block.get("type") == "text").strip()

    async def chat(self, prompt: str, system_prompt: str = "") -> str:
        try:
            return await asyncio.to_thread(self._request, prompt, system_prompt)
        except Exception as exc:
            logger.warning("Claude request failed: %s", exc)
            raise


class GroqProvider(IntelligenceProvider):
    """Groq OpenAI-compatible provider."""

    def name(self) -> str:
        return "Groq"

    def is_available(self) -> bool:
        return bool(os.environ.get("GROQ_API_KEY"))

    async def chat(self, prompt: str, system_prompt: str = "") -> str:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not configured")
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": os.environ.get("ATULYA_GROQ_MODEL", "llama-3.3-70b-versatile"),
                "messages": messages,
                "max_tokens": 1024,
                "temperature": 0.7,
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30.0) as response:
                if response.status == 200:
                    res_body = json.loads(response.read().decode("utf-8"))
                    return res_body["choices"][0]["message"]["content"].strip()
                raise RuntimeError(f"Groq returned status {response.status}")
        except Exception as e:
            logger.warning(f"GroqProvider chat failed: {e}")
            raise e


CLOUD_BUSY_MESSAGE = (
    "My cloud brain didn't answer just now - free models are sometimes busy. "
    "Try again in a moment, or add another free key such as Groq."
)

NO_BRAIN_MESSAGE = (
    "My brain isn't loaded yet, so I can only do simple commands like the time or reminders. "
    "Run start.bat again to install the local model, then ask me again."
)


class OpenAICompatProvider(OpenRouterProvider):
    """Any OpenAI-style provider from ``providers_catalog`` (Mistral, DeepSeek, Qwen, Together …)."""

    def __init__(self, spec: Any):
        self.spec = spec

    @property
    def URL(self) -> str:  # noqa: N802
        base = os.environ.get("ATULYA_CUSTOM_URL", "") if self.spec.id == "custom" else self.spec.base_url
        return base.rstrip("/") + "/chat/completions"

    def name(self) -> str:
        return self.spec.label.split(" (")[0]

    def _key(self) -> str:  # type: ignore[override]
        # A custom local server often needs no key, so a URL alone makes it available.
        key = os.environ.get(self.spec.key_var, "")
        return key or ("none" if self.spec.id == "custom" and os.environ.get("ATULYA_CUSTOM_URL") else "")

    def models(self) -> list[str]:  # type: ignore[override]
        raw = os.environ.get(self.spec.model_var, "") or self.spec.default_model
        return [m.strip() for m in raw.split(",") if m.strip()]


class NoBrainProvider(IntelligenceProvider):
    """Last link in the chain: says plainly that no brain is loaded.

    It used to answer with canned persona lines ("At your service, sir…") that
    looked like real replies, which hid that nothing was actually thinking.
    """

    def name(self) -> str:
        return "No brain loaded"

    def is_available(self) -> bool:
        return True

    async def chat(self, prompt: str, system_prompt: str = "") -> str:
        return NO_BRAIN_MESSAGE


OpenCodeProvider = NoBrainProvider  # old name, kept so existing imports keep working


class LocalGGUFProvider(IntelligenceProvider):
    """Provider that loads a tiny GGUF model directly via llama-cpp-python.
    
    Uses PersonaLocalProvider (the Atulya persona on the local model).
    """

    def __init__(self):
        self._impl = None

    def name(self) -> str:
        try:
            from atulya.buddhi.local_provider import create_local_provider
            if self._impl is None:
                self._impl = create_local_provider()
            return self._impl.name()
        except Exception:
            return "Tantra Local (Placeholder)"

    def is_available(self) -> bool:
        try:
            from atulya.buddhi.local_provider import create_local_provider
            if self._impl is None:
                self._impl = create_local_provider()
            return self._impl.is_available()
        except Exception:
            return False

    async def chat(self, prompt: str, system_prompt: str = "", tools: list[dict[str, Any]] | None = None) -> str:
        from atulya.buddhi.local_provider import create_local_provider
        if self._impl is None:
            self._impl = create_local_provider()
        return await self._impl.chat(prompt, system_prompt, tools)

    async def chat_stream(self, prompt: str, system_prompt: str = "") -> AsyncIterator[str]:
        from atulya.buddhi.local_provider import create_local_provider
        if self._impl is None:
            self._impl = create_local_provider()
        stream = getattr(self._impl, "chat_stream", None)
        if stream is None:
            yield await self._impl.chat(prompt, system_prompt)
            return
        async for piece in stream(prompt, system_prompt):
            yield piece


# Learned speed of each brain: smoothed seconds to answer, and when a recent failure expires.
_SPEED: dict[str, dict[str, float]] = {}
_FAIL_COOLDOWN = 120.0
_FAIL_SCORE = 1000.0


def _record_speed(name: str, seconds: float | None) -> None:
    """Remember how long a brain took (None = it failed, so it goes to the back for a while)."""
    if name == "No brain loaded":  # the "nothing is configured" message is not a brain to rank
        return
    entry = _SPEED.setdefault(name, {})
    if seconds is None:
        entry["failed_until"] = time.monotonic() + _FAIL_COOLDOWN
        return
    entry["failed_until"] = 0.0
    entry["avg"] = seconds if "avg" not in entry else 0.7 * entry["avg"] + 0.3 * seconds


def _speed_score(name: str, rank: int) -> float:
    entry = _SPEED.get(name, {})
    if entry.get("failed_until", 0.0) > time.monotonic():
        return _FAIL_SCORE + rank
    # Not measured yet: the configured order decides, as a small head start for earlier brains.
    return entry.get("avg", 0.5 * rank)


class ProviderRouter(IntelligenceProvider):
    """Atulya Intelligence Provider Fallback Chain Router."""
    
    def __init__(self):
        # Fallback priority chain order - local Qwen3-0.6B GGUF first, cloud APIs after.
        self.providers: list[IntelligenceProvider] = [
            AnthropicProvider(),   # Claude, only when ANTHROPIC_API_KEY is set (fastest, smartest)
            LocalGGUFProvider(),   # Qwen3-0.6B GGUF (~380 MB), auto-downloads, no Ollama needed (1st choice)
            OllamaProvider(),      # Free local model via Ollama (2nd choice)
            GroqProvider(),        # Fast free developer-tier API (3rd choice)
            OpenRouterProvider(),  # Free model aggregator when configured (3rd choice)
            OpenCodeGoProvider(),  # OpenCode Go key, when configured
            *[OpenAICompatProvider(spec) for spec in CATALOG if not spec.builtin],  # Mistral, DeepSeek, Qwen …
            GeminiProvider(),      # Google free-tier key when configured (4th choice)
            OpenAIProvider(),      # Paid/optional fallback only (6th choice)
            NvidiaNimProvider(),   # Optional provider fallback (7th choice)
            OpenCodeProvider()     # Bulletproof fallback (8th choice)
        ]
        # ATULYA_BRAIN=cloud: configured cloud APIs lead; the local brain and
        # Ollama become the offline fallback (still ahead of the persona reply).
        # With no ATULYA_BRAIN chosen, a configured cloud key also leads: the tiny local model
        # is slow on CPU and weak, so it stays the offline fallback instead of answering first.
        from atulya.buddhi.brain import cloud_first
        cloud_keys = [p for p in self.providers
                      if not isinstance(p, (LocalGGUFProvider, OllamaProvider, OpenCodeProvider)) and p.is_available()]
        if cloud_first() or (not os.environ.get("ATULYA_BRAIN", "").strip() and cloud_keys):
            local = (LocalGGUFProvider, OllamaProvider)
            last = [p for p in self.providers if isinstance(p, OpenCodeProvider)]
            locals_ = [p for p in self.providers if isinstance(p, local)]
            clouds = [p for p in self.providers if p not in locals_ and p not in last]
            self.providers = clouds + locals_ + last
        
    def name(self) -> str:
        return "Atulya Provider Router"

    def _ordered(self, providers: list["IntelligenceProvider"]) -> list["IntelligenceProvider"]:
        """Fastest working brain first, unless ATULYA_BRAIN pins an order."""
        if os.environ.get("ATULYA_BRAIN", "").strip():
            return providers
        ranked = sorted(enumerate(providers), key=lambda ir: _speed_score(ir[1].name(), ir[0]))
        return [p for _, p in ranked]
        
    def is_available(self) -> bool:
        return True
        
    async def chat(self, prompt: str, system_prompt: str = "", preferred_provider: str = "", tools: list[dict[str, Any]] | None = None) -> str:
        """Route request through priority chain and failover automatically."""
        attempted = []
        providers = self._ordered(self.providers)
        preferred = (preferred_provider or "").strip().lower()
        if preferred and preferred not in {"auto", "latest"}:
            preferred_matches = [p for p in providers if preferred in p.name().lower()]
            providers = preferred_matches + [p for p in providers if p not in preferred_matches]

        for provider in providers:
            if provider.is_available():
                started = time.monotonic()
                try:
                    logger.info(f"Atulya OS routing request to provider: {provider.name()}")
                    if tools and _supports_tools(provider):
                        response = await provider.chat(prompt, system_prompt, tools=tools)
                    else:
                        response = await provider.chat(prompt, system_prompt)
                    _record_speed(provider.name(), time.monotonic() - started)
                    return response, provider.name()
                except Exception as exc:
                    _record_speed(provider.name(), None)
                    logger.warning(f"Provider {provider.name()} failed: {exc}. Attempting next fallback.")
                    attempted.append(f"{provider.name()} (Error: {exc})")
            else:
                attempted.append(f"{provider.name()} (Unavailable)")
                
        # All providers failed, return a diagnostic error response
        errors_summary = ", ".join(attempted)
        logger.warning("No brain answered. Attempted: %s", errors_summary)
        cloud_keys = tuple(spec.key_var for spec in CATALOG if spec.id != "custom")
        if any(os.environ.get(k) for k in cloud_keys):
            return CLOUD_BUSY_MESSAGE, "Diagnostics Fallback"
        return NO_BRAIN_MESSAGE, "Diagnostics Fallback"

    async def stream(
        self,
        prompt: str,
        system_prompt: str = "",
        preferred_provider: str = "",
    ) -> AsyncIterator[tuple[str, str]]:
        """Stream tokens from the first available provider that supports streaming.

        Falls back to chunking a full provider.chat() response when the chosen
        provider only implements chat(). Yields (text_piece, provider_name).
        """
        providers = self._ordered(self.providers)
        preferred = (preferred_provider or "").strip().lower()
        if preferred and preferred not in {"auto", "latest"}:
            preferred_matches = [p for p in providers if preferred in p.name().lower()]
            providers = preferred_matches + [p for p in providers if p not in preferred_matches]

        for provider in providers:
            if not provider.is_available():
                continue
            stream_method = getattr(provider, "chat_stream", None)
            started = time.monotonic()
            first = True
            try:
                if stream_method is not None:
                    async for piece in stream_method(prompt, system_prompt):
                        if first:
                            _record_speed(provider.name(), time.monotonic() - started)
                            first = False
                        yield piece, provider.name()
                else:
                    text = await provider.chat(prompt, system_prompt)
                    _record_speed(provider.name(), time.monotonic() - started)
                    for piece in _chunk_stream_text(text):
                        yield piece, provider.name()
                return
            except Exception as exc:
                if first:
                    _record_speed(provider.name(), None)
                logger.warning(f"Provider {provider.name()} stream failed: {exc}. Attempting next fallback.")

        yield NO_BRAIN_MESSAGE, "Diagnostics Fallback"
