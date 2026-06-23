"""Atulya Intelligence Provider System.

Decouples the operating system from any single LLM brain.
Enables pluggable brains (Gemini, Claude, OpenAI, OpenRouter, NVIDIA NIM, Ollama, local Tantra)
with automatic failover fallbacks.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _benchmark_allows_tantra(model_path: str | Path) -> bool:
    if os.environ.get("ATULYA_TANTRA_ALLOW_MODEL", "").lower() in {"1", "true", "yes"}:
        return True
    benchmark_path = Path(model_path) / "benchmark.json"
    if not benchmark_path.exists():
        return False
    try:
        data = json.loads(benchmark_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    gate = data.get("production_gate")
    if isinstance(gate, dict) and gate.get("approved") is True:
        return True

    max_perplexity = _env_float("ATULYA_TANTRA_MAX_PERPLEXITY", 80.0)
    min_tok_sec = _env_float("ATULYA_TANTRA_MIN_TOK_PER_SEC", 5.0)
    min_utilization = _env_float("ATULYA_TANTRA_MIN_STRAND_UTILIZATION", 0.5)

    perplexity = float(data.get("perplexity") or 999999)
    speed = float((data.get("generation_speed") or {}).get("tokens_per_second") or 0)
    strand_scores = [
        float(item.get("utilization_score") or 0)
        for item in (data.get("strand_utilization") or {}).values()
        if isinstance(item, dict)
    ]
    utilization = min(strand_scores) if strand_scores else 0
    return perplexity <= max_perplexity and speed >= min_tok_sec and utilization >= min_utilization


class IntelligenceProvider:
    """Base interface for pluggable intelligence providers."""
    
    def name(self) -> str:
        raise NotImplementedError
        
    def is_available(self) -> bool:
        raise NotImplementedError
        
    async def chat(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError


class TantraProvider(IntelligenceProvider):
    """Native Tantra NP-DNA provider, gated by benchmark readiness."""
    
    def name(self) -> str:
        return "Tantra (Local NP-DNA)"
        
    def is_available(self) -> bool:
        try:
            from drishti.dashboard.helpers import _checkpoint_index
            allowed = _checkpoint_index()
            model_path = allowed.get("latest")
            return bool(model_path and _benchmark_allows_tantra(model_path))
        except Exception:
            return False
            
    async def chat(self, prompt: str, system_prompt: str = "") -> str:
        try:
            from drishti.dashboard.helpers import _checkpoint_index, _load_cached_model
            import torch
            allowed = _checkpoint_index()
            model_path = allowed.get("latest")
            if not model_path or not model_path.exists():
                raise FileNotFoundError("Tantra model not found")
                
            core = _load_cached_model(model_path)
            with torch.inference_mode():
                full_prompt = f"{system_prompt}\n\nUser: {prompt}\nAssistant:" if system_prompt else prompt
                response = core.generate(full_prompt, max_tokens=150, temperature=0.7)
                return response
        except Exception as e:
            logger.warning(f"TantraProvider chat failed: {e}")
            raise e


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


class OpenRouterProvider(IntelligenceProvider):
    """OpenRouter Cloud Model Aggregator Provider."""
    
    def name(self) -> str:
        return "OpenRouter"
        
    def is_available(self) -> bool:
        return bool(os.environ.get("OPENROUTER_API_KEY"))
        
    async def chat(self, prompt: str, system_prompt: str = "") -> str:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not configured")
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            model = os.environ.get("ATULYA_OPENROUTER_MODEL", "google/gemini-2.5-flash")
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": 150
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://github.com/atulyaai/Atulya-Tantra",
                    "X-Title": "Atulya OS"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10.0) as response:
                if response.status == 200:
                    res_body = json.loads(response.read().decode("utf-8"))
                    return res_body["choices"][0]["message"]["content"].strip()
                raise RuntimeError(f"OpenRouter returned status {response.status}")
        except Exception as e:
            logger.warning(f"OpenRouterProvider chat failed: {e}")
            raise e


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


class OpenCodeProvider(IntelligenceProvider):
    """OpenCode Zen Provider for lightweight local system fallbacks."""
    
    def name(self) -> str:
        return "OpenCode Zen"
        
    def is_available(self) -> bool:
        return True
        
    async def chat(self, prompt: str, system_prompt: str = "") -> str:
        from atulya.persona import get_atulya_fallback_response
        return get_atulya_fallback_response(prompt, "en_male")


class LocalGGUFProvider(IntelligenceProvider):
    """Provider that loads a tiny GGUF model directly via llama-cpp-python."""

    def __init__(self):
        self._impl = None

    def name(self) -> str:
        try:
            from atulya.local_provider import LocalGGUFProvider as LP
            if self._impl is None:
                self._impl = LP()
            return self._impl.name()
        except Exception:
            return "Tiny Local GGUF"

    def is_available(self) -> bool:
        try:
            from atulya.local_provider import LocalGGUFProvider as LP
            if self._impl is None:
                self._impl = LP()
            return self._impl.is_available()
        except Exception:
            return False

    async def chat(self, prompt: str, system_prompt: str = "") -> str:
        from atulya.local_provider import LocalGGUFProvider as LP
        if self._impl is None:
            self._impl = LP()
        return await self._impl.chat(prompt, system_prompt)


class ProviderRouter(IntelligenceProvider):
    """Atulya Intelligence Provider Fallback Chain Router."""
    
    def __init__(self):
        # Fallback priority chain order
        self.providers: list[IntelligenceProvider] = [
            OllamaProvider(),      # Free local model (1st choice)
            LocalGGUFProvider(),   # Tiny 350 MB local GGUF, no Ollama needed (2nd choice)
            GroqProvider(),        # Fast free developer-tier API (3rd choice)
            OpenRouterProvider(),  # Free model aggregator when configured (3rd choice)
            GeminiProvider(),      # Google free-tier key when configured (4th choice)
            TantraProvider(),      # Research model only after benchmark gate passes
            OpenAIProvider(),      # Paid/optional fallback only (6th choice)
            NvidiaNimProvider(),   # Optional provider fallback (7th choice)
            OpenCodeProvider()     # Bulletproof fallback (8th choice)
        ]
        
    def name(self) -> str:
        return "Atulya Provider Router"
        
    def is_available(self) -> bool:
        return True
        
    async def chat(self, prompt: str, system_prompt: str = "", preferred_provider: str = "") -> str:
        """Route request through priority chain and failover automatically."""
        attempted = []
        providers = self.providers
        preferred = (preferred_provider or "").strip().lower()
        if preferred and preferred not in {"auto", "latest"}:
            preferred_matches = [p for p in providers if preferred in p.name().lower()]
            providers = preferred_matches + [p for p in providers if p not in preferred_matches]

        for provider in providers:
            if provider.is_available():
                try:
                    logger.info(f"Atulya OS routing request to provider: {provider.name()}")
                    response = await provider.chat(prompt, system_prompt)
                    return response, provider.name()
                except Exception as exc:
                    logger.warning(f"Provider {provider.name()} failed: {exc}. Attempting next fallback.")
                    attempted.append(f"{provider.name()} (Error: {exc})")
            else:
                attempted.append(f"{provider.name()} (Unavailable)")
                
        # All providers failed, return a diagnostic error response
        errors_summary = ", ".join(attempted)
        return (
            f"Caution, sir. All neural intelligence channels are offline or unconfigured. "
            f"Attempted: {errors_summary}. Please verify your local Ollama connection or API keys.",
            "Diagnostics Fallback"
        )
