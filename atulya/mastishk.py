"""Mastishk (मस्तिष्क, brain): brain tiers, the provider catalogue, safety rules, the tool belt, the failover router, the local model and the language-model layer."""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator

from atulya.bhava import MoodState, Persona, build_emotional_directive, detect_emotion
from atulya.kaushal import Tool, ToolRegistry, ToolResult, create_default_registry

# ── mastishk ────────────────────────────────────────────────────────────
_HF = "https://huggingface.co/{repo}/resolve/main/{file}"

BRAIN_TIERS: dict[str, dict[str, Any]] = {
    "tiny": {
        "label": "Qwen3-0.6B", "repo": "unsloth/Qwen3-0.6B-GGUF", "file": "Qwen3-0.6B-Q4_K_M.gguf",
        "glob": "Qwen3-0.6B*.gguf", "size": "~0.4 GB", "ram": "~1 GB",
    },
    "balanced": {
        "label": "Qwen3-1.7B", "repo": "unsloth/Qwen3-1.7B-GGUF", "file": "Qwen3-1.7B-Q4_K_M.gguf",
        "glob": "Qwen3-1.7B*.gguf", "size": "~1.1 GB", "ram": "~3 GB",
    },
    "power": {
        "label": "Qwen3-4B", "repo": "unsloth/Qwen3-4B-GGUF", "file": "Qwen3-4B-Q4_K_M.gguf",
        "glob": "Qwen3-4B*.gguf", "size": "~2.5 GB", "ram": "~6 GB",
    },
}
DEFAULT_TIER = "tiny"
CLOUD_TIER = "cloud"
# Smallest first: the fallback order when the chosen tier's model is missing.
_FALLBACK_ORDER = ["tiny", "balanced", "power"]


def active_brain() -> str:
    """The configured tier (unknown values fall back to the default)."""
    tier = os.environ.get("ATULYA_BRAIN", DEFAULT_TIER).strip().lower()
    if tier == "auto":  # the biggest local brain that fits this machine's free RAM
        return recommend_tier()
    return tier if tier in BRAIN_TIERS or tier == CLOUD_TIER else DEFAULT_TIER


def local_model_spec(tier: str | None = None) -> dict[str, Any]:
    """Model spec for the tier's local brain (the cloud tier runs tiny locally)."""
    tier = tier or active_brain()
    spec = dict(BRAIN_TIERS.get(tier, BRAIN_TIERS[DEFAULT_TIER]))
    spec["tier"] = tier if tier in BRAIN_TIERS else DEFAULT_TIER
    spec["url"] = _HF.format(repo=spec["repo"], file=spec["file"])
    return spec


def fallback_globs(tier: str | None = None) -> list[str]:
    """Globs to try, the chosen tier first, then smaller ones."""
    spec = local_model_spec(tier)
    order = [spec["tier"]] + [t for t in _FALLBACK_ORDER if t != spec["tier"]]
    # Never silently fall *up* to a heavier model than asked for.
    limit = _FALLBACK_ORDER.index(spec["tier"])
    return [BRAIN_TIERS[t]["glob"] for t in order if _FALLBACK_ORDER.index(t) <= limit]


def recommend_tier(free_ram_gb: float | None = None) -> str:
    """The biggest local tier that fits comfortably in free RAM (None = detect)."""
    if free_ram_gb is None:
        try:
            import psutil

            free_ram_gb = psutil.virtual_memory().available / 1024**3
        except Exception:  # noqa: BLE001
            return DEFAULT_TIER
    if free_ram_gb >= 8:
        return "power"
    if free_ram_gb >= 4:
        return "balanced"
    return DEFAULT_TIER


def cloud_first(tier: str | None = None) -> bool:
    return (tier or active_brain()) == CLOUD_TIER


def describe() -> dict[str, Any]:
    tier = active_brain()
    return {
        "tier": tier,
        "cloud_first": cloud_first(tier),
        "local_model": local_model_spec(tier),
        "tiers": {name: {k: v for k, v in spec.items() if k in ("label", "size", "ram")}
                  for name, spec in BRAIN_TIERS.items()} | {CLOUD_TIER: {"label": "Cloud providers first"}},
    }


# ── suchi ────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Spec:
    id: str
    label: str
    key_var: str
    model_var: str
    default_model: str
    base_url: str = ""          # OpenAI-style base (…/v1); empty for builtin classes
    free: str = "paid"          # "free" | "free tier" | "paid" | "local"
    docs: str = ""              # where to get a key
    builtin: bool = False


CATALOG: list[Spec] = [
    # Own classes
    Spec("anthropic", "Claude (Anthropic)", "ANTHROPIC_API_KEY", "ATULYA_CLAUDE_MODEL", "claude-haiku-4-5-20251001",
         free="paid", docs="https://console.anthropic.com/settings/keys", builtin=True),
    Spec("openai", "ChatGPT / OpenAI", "OPENAI_API_KEY", "ATULYA_OPENAI_MODEL", "gpt-4o-mini",
         free="paid", docs="https://platform.openai.com/api-keys", builtin=True),
    Spec("gemini", "Google Gemini", "GEMINI_API_KEY", "ATULYA_GEMINI_MODEL", "gemini-1.5-flash",
         free="free tier", docs="https://aistudio.google.com/app/apikey", builtin=True),
    Spec("groq", "Groq (very fast)", "GROQ_API_KEY", "ATULYA_GROQ_MODEL", "llama-3.3-70b-versatile",
         free="free tier", docs="https://console.groq.com/keys", builtin=True),
    Spec("nvidia", "NVIDIA NIM", "NVIDIA_API_KEY", "ATULYA_NVIDIA_MODEL", "meta/llama-3.1-8b-instruct",
         free="free tier", docs="https://build.nvidia.com/", builtin=True),
    Spec("openrouter", "OpenRouter (many models, free ones)", "OPENROUTER_API_KEY", "ATULYA_OPENROUTER_MODEL",
         "qwen/qwen3.8-27b:free", free="free tier", docs="https://openrouter.ai/keys", builtin=True),
    Spec("opencode", "OpenCode Go", "OPENCODE_API_KEY", "ATULYA_OPENCODE_MODEL", "deepseek-v4-flash",
         free="paid", docs="https://opencode.ai/auth", builtin=True),
    # One generic class, many providers
    Spec("mistral", "Mistral", "MISTRAL_API_KEY", "ATULYA_MISTRAL_MODEL", "mistral-small-latest",
         "https://api.mistral.ai/v1", "free tier", "https://console.mistral.ai/api-keys"),
    Spec("deepseek", "DeepSeek", "DEEPSEEK_API_KEY", "ATULYA_DEEPSEEK_MODEL", "deepseek-chat",
         "https://api.deepseek.com/v1", "paid", "https://platform.deepseek.com/api_keys"),
    Spec("qwen", "Qwen (Alibaba DashScope)", "DASHSCOPE_API_KEY", "ATULYA_QWEN_MODEL", "qwen-plus",
         "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "free tier", "https://bailian.console.alibabacloud.com/"),
    Spec("xai", "Grok (xAI)", "XAI_API_KEY", "ATULYA_XAI_MODEL", "grok-4",
         "https://api.x.ai/v1", "paid", "https://console.x.ai/"),
    Spec("together", "Together AI", "TOGETHER_API_KEY", "ATULYA_TOGETHER_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo",
         "https://api.together.xyz/v1", "free tier", "https://api.together.ai/settings/api-keys"),
    Spec("fireworks", "Fireworks AI", "FIREWORKS_API_KEY", "ATULYA_FIREWORKS_MODEL", "accounts/fireworks/models/llama-v3p3-70b-instruct",
         "https://api.fireworks.ai/inference/v1", "free tier", "https://fireworks.ai/account/api-keys"),
    Spec("cerebras", "Cerebras (very fast)", "CEREBRAS_API_KEY", "ATULYA_CEREBRAS_MODEL", "llama-3.3-70b",
         "https://api.cerebras.ai/v1", "free tier", "https://cloud.cerebras.ai/"),
    Spec("sambanova", "SambaNova", "SAMBANOVA_API_KEY", "ATULYA_SAMBANOVA_MODEL", "Meta-Llama-3.3-70B-Instruct",
         "https://api.sambanova.ai/v1", "free tier", "https://cloud.sambanova.ai/apis"),
    Spec("perplexity", "Perplexity (web answers)", "PERPLEXITY_API_KEY", "ATULYA_PERPLEXITY_MODEL", "sonar",
         "https://api.perplexity.ai", "paid", "https://www.perplexity.ai/settings/api"),
    Spec("moonshot", "Kimi (Moonshot)", "MOONSHOT_API_KEY", "ATULYA_MOONSHOT_MODEL", "kimi-k2-0905-preview",
         "https://api.moonshot.ai/v1", "paid", "https://platform.moonshot.ai/console/api-keys"),
    Spec("zhipu", "GLM (Zhipu)", "ZHIPU_API_KEY", "ATULYA_ZHIPU_MODEL", "glm-4-flash",
         "https://open.bigmodel.cn/api/paas/v4", "free tier", "https://open.bigmodel.cn/usercenter/apikeys"),
    Spec("siliconflow", "SiliconFlow", "SILICONFLOW_API_KEY", "ATULYA_SILICONFLOW_MODEL", "Qwen/Qwen2.5-7B-Instruct",
         "https://api.siliconflow.com/v1", "free tier", "https://cloud.siliconflow.com/account/ak"),
    Spec("huggingface", "Hugging Face", "HF_TOKEN", "ATULYA_HF_MODEL", "meta-llama/Llama-3.3-70B-Instruct",
         "https://router.huggingface.co/v1", "free tier", "https://huggingface.co/settings/tokens"),
    Spec("github", "GitHub Models", "GITHUB_MODELS_TOKEN", "ATULYA_GITHUB_MODEL", "openai/gpt-4o-mini",
         "https://models.github.ai/inference", "free tier", "https://github.com/settings/tokens"),
    Spec("custom", "Your own (LM Studio, vLLM, any OpenAI-style URL)", "ATULYA_CUSTOM_KEY", "ATULYA_CUSTOM_MODEL", "",
         "", "local", ""),
]
BY_ID = {s.id: s for s in CATALOG}


# ── maryada ────────────────────────────────────────────────────────────
ALLOW = "allow"
CONFIRM = "confirm"

# Code execution / file mutation / automation of external systems.
RISKY_TOOLS = {
    "exec",
    "file_write",
    "file_edit",
    "code_execute",
    "sap_gui_automation",
}

# Tools that always need confirmation, with the reason shown to the user.
_CONFIRM_TOOLS = {
    **{name: "runs code or changes files" for name in RISKY_TOOLS},
    "send_email": "sends a message on your behalf",
    "calendar_remove": "permanently deletes a calendar event",
    "cancel_reminder": "deletes a reminder",
    "configure_email": "stores email credentials",
    "download_vision_model": "downloads a large model",
    "pc_open_app": "opens an app on your computer",
    "pc_type": "types on your keyboard",
    "pc_hotkey": "presses keyboard shortcuts",
    "pc_screenshot": "captures your screen",
    "web_task": "drives a web browser to do a task for you",
    "device_remove": "forgets a device",
    "device_profile_approve": "lets me send a new kind of command to a device",
}

# Specific (tool, action) pairs that need confirmation.
_CONFIRM_ACTIONS = {
    ("home_control", "unlock"): "unlocks a door",
}


@dataclass
class Assessment:
    level: str
    reason: str = ""

    @property
    def needs_confirmation(self) -> bool:
        return self.level == CONFIRM


def _auto_approved() -> set[str]:
    raw = os.environ.get("ATULYA_AUTO_APPROVE", "")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def assess(tool: str, arguments: dict[str, Any] | None = None) -> Assessment:
    """Classify an action as ALLOW or CONFIRM."""
    tool = (tool or "").strip()
    action = str((arguments or {}).get("action") or "").strip().lower()
    approved = _auto_approved()

    if tool == "device_do":  # the device's own profile says which actions need a yes (unlock, restart, typing …)
        from atulya.upakaran import get_hub

        if get_hub().is_risky(str((arguments or {}).get("device", "")), str((arguments or {}).get("action", ""))) and "device_do" not in approved:
            return Assessment(CONFIRM, "could change or restart a device")
    reason = _CONFIRM_ACTIONS.get((tool, action))
    if reason and f"{tool}:{action}".lower() not in approved and tool.lower() not in approved:
        return Assessment(CONFIRM, reason)

    reason = _CONFIRM_TOOLS.get(tool)
    if reason and tool.lower() not in approved:
        return Assessment(CONFIRM, reason)

    return Assessment(ALLOW)


def needs_confirmation(tool: str, arguments: dict[str, Any] | None = None) -> bool:
    return assess(tool, arguments).needs_confirmation


def describe_action(tool: str, arguments: dict[str, Any] | None = None) -> str:
    """A short human phrase for a pending action, used in confirmation prompts."""
    args = arguments or {}
    if tool == "home_control":
        device = str(args.get("device_id", "the device")).replace("_", " ")
        action = str(args.get("action", "control"))
        if action == "set_temperature":
            return f"set the {device} to {args.get('value')}°"
        if action in ("on", "off"):
            return f"turn {action} the {device}"
        return f"{action} the {device}"
    if tool == "send_email":
        return f"send an email to {args.get('to', 'someone')} about \"{args.get('subject', '')}\""
    if tool == "calendar_remove":
        return f"delete calendar event {args.get('event_id', '')}".strip()
    if tool == "cancel_reminder":
        return f"cancel reminder {args.get('reminder_id', '')}".strip()
    if tool == "run_plan":
        return f"run “{args.get('title') or 'the plan'}” ({len(args.get('steps') or [])} steps)"
    if tool == "trust_action":
        return f"stop asking before I {args.get('label') or 'do that'}"
    if tool == "forget_profile":
        return "forget everything I've learned about you"
    if tool in ("get_weather", "get_forecast"):
        return f"check the weather in {args.get('location', 'your city')}"
    if tool == "open_website":
        return f"open {args.get('site', 'a website')}"
    if tool == "device_do":
        return f"{str(args.get('action', 'do something')).replace('_', ' ')} on {args.get('device', 'a device')}"
    if tool == "device_remove":
        return f"forget the device {args.get('device', '')}".strip()
    if tool == "device_profile_approve":
        return f"approve device profile {args.get('proposal', '')}".strip()
    if tool == "web_task":
        return f"do this on the web: {str(args.get('goal', 'a task'))[:80]}"
    if tool == "pc_open_app":
        return f"open {args.get('app', 'an app')}"
    if tool == "pc_type":
        return "type that on your keyboard"
    if tool == "pc_hotkey":
        return f"press {args.get('keys', 'a shortcut')}"
    if tool in _CHECKS:
        return _CHECKS[tool]
    return f"run {tool}"


_CHECKS = {"calendar_list": "check your calendar", "fetch_emails": "check your email", "current_time": "check the time",
           "list_reminders": "check your reminders", "home_list_devices": "check your devices"}


# ── aujar ────────────────────────────────────────────────────────────
# Setup/admin actions the conversational brain should not trigger on its own:
# downloading multi-GB models and storing mail credentials. Still available via
# the CLI agent and the dashboard settings.
EXCLUDED_FROM_BRAIN = {"download_vision_model", "configure_email"}


class AgentToolAdapter(Tool):
    """Expose an ``atulya.kriya`` function tool through the yantra Tool API."""

    def __init__(self, name: str, info: dict[str, Any]):
        self.name = name
        self.description = info.get("description", "")
        params = info.get("parameters") or {}
        # tools.py marks every param required=True inline; convert to a JSON
        # schema where only params without a declared default are required.
        self.parameters = {
            "type": "object",
            "properties": {
                pname: {k: v for k, v in pschema.items() if k != "required"}
                for pname, pschema in params.items()
            },
            "required": [p for p, s in params.items() if "default" not in s],
        }
        self._fn = info["fn"]

    async def execute(self, **kwargs: Any) -> ToolResult:
        from atulya.kriya import audit

        audit("tool", name=self.name, args=kwargs)  # every assistant action the brain takes is on the record
        try:
            out = await self._fn(**kwargs)
        except TypeError as exc:  # wrong/missing arguments from the model
            return ToolResult(success=False, error=f"Bad arguments for {self.name}: {exc}")
        except Exception as exc:  # noqa: BLE001 - surface tool failures as results
            return ToolResult(success=False, error=str(exc))
        return ToolResult(success=True, output=str(out) if out is not None else "")


def build_unified_registry(data_dir: str | Path = ".") -> ToolRegistry:
    """Return the yantra default registry plus the personal-assistant tools."""
    registry = create_default_registry(data_dir)
    from atulya import kriya as agent_tools  # lazy: avoids import cycles

    existing = {t["name"] for t in registry.list_tools()}
    for name, info in agent_tools.TOOL_REGISTRY.items():
        if name in EXCLUDED_FROM_BRAIN or name in existing:
            continue
        registry.register(AgentToolAdapter(name, info))
    return registry


# ── vahak ────────────────────────────────────────────────────────────
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


class LocalBrainProvider(IntelligenceProvider):
    """Provider that loads a tiny GGUF model directly via llama-cpp-python.
    
    Uses PersonaLocalProvider (the Atulya persona on the local model).
    """

    def __init__(self):
        self._impl = None

    def name(self) -> str:
        try:
            if self._impl is None:
                self._impl = create_local_provider()
            return self._impl.name()
        except Exception:
            return "Tantra Local (Placeholder)"

    def is_available(self) -> bool:
        try:
            if self._impl is None:
                self._impl = create_local_provider()
            return self._impl.is_available()
        except Exception:
            return False

    async def chat(self, prompt: str, system_prompt: str = "", tools: list[dict[str, Any]] | None = None) -> str:
        if self._impl is None:
            self._impl = create_local_provider()
        return await self._impl.chat(prompt, system_prompt, tools)

    async def chat_stream(self, prompt: str, system_prompt: str = "") -> AsyncIterator[str]:
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


_LOCAL_NAMES = ("Atulya Local", "Local Brain", "Ollama")
SLOW_SECONDS = 10.0          # a local answer slower than this is worth a fast cloud brain
FAST_FREE = ("groq", "openrouter", "gemini")   # free keys that are usually quick, best first


def speed_report(speeds: dict[str, dict[str, float]] | None = None, linked_cloud: int = 0) -> dict:
    """What the screen shows about speed: each brain's measured seconds, and advice when answers are slow.

    ``linked_cloud`` is how many cloud brains have a key. The advice only appears when there is none and
    the local model is the one answering slowly (or nothing has been measured yet)."""
    speeds = _SPEED if speeds is None else speeds
    rows = sorted(
        ({"name": n, "seconds": round(v["avg"], 1), "local": n.startswith(_LOCAL_NAMES)}
         for n, v in speeds.items() if v.get("avg") and n != "No brain loaded"),
        key=lambda r: r["seconds"],
    )
    advice = None
    if not linked_cloud:
        slow = next((r for r in rows if r["local"] and r["seconds"] > SLOW_SECONDS), None)
        if slow:
            advice = {"kind": "slow_local", "seconds": slow["seconds"],
                      "message": f"Answers come from the model on this computer and take about {slow['seconds']:g} s. "
                                 "A free cloud key usually answers in a few seconds (not measured on your connection yet)."}
        elif not rows:
            advice = {"kind": "unmeasured", "message": "No answers measured yet. Ask Atulya something, then look here again."}
    return {"brains": rows, "advice": advice, "recommended": [i for i in FAST_FREE if i in BY_ID]}


class ProviderRouter(IntelligenceProvider):
    """Atulya Intelligence Provider Fallback Chain Router."""
    
    def __init__(self):
        # Fallback priority chain order - local Qwen3-0.6B GGUF first, cloud APIs after.
        self.providers: list[IntelligenceProvider] = [
            AnthropicProvider(),   # Claude, only when ANTHROPIC_API_KEY is set (fastest, smartest)
            LocalBrainProvider(),   # Qwen3-0.6B GGUF (~380 MB), auto-downloads, no Ollama needed (1st choice)
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
        cloud_keys = [p for p in self.providers
                      if not isinstance(p, (LocalBrainProvider, OllamaProvider, OpenCodeProvider)) and p.is_available()]
        if cloud_first() or (not os.environ.get("ATULYA_BRAIN", "").strip() and cloud_keys):
            local = (LocalBrainProvider, OllamaProvider)
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
        # The "no brain" reply is never ranked: unmeasured, it would look faster than a real
        # brain that has been timed once, and would then answer in its place.
        last = [p for p in providers if isinstance(p, NoBrainProvider)]
        rest = [p for p in providers if not isinstance(p, NoBrainProvider)]
        ranked = sorted(enumerate(rest), key=lambda ir: _speed_score(ir[1].name(), ir[0]))
        return [p for _, p in ranked] + last
        
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


# ── sthaniya ────────────────────────────────────────────────────────────
def _normalize_tool_call_xml(text: str) -> str | None:
    """Convert Qwen-style <tool_call>{{"name":...,"arguments":{...}}}</tool_call> to plain JSON.

    AtulyaLLM expects {"tool":..., "arguments":{...}}; Qwen emits a wrapped object
    with "name"/"arguments" keys inside <tool_call> tags. Return None if no match.
    """
    import re

    if "<tool_call>" not in text:
        return None
    match = re.search(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", text, flags=re.DOTALL)
    if not match:
        return None
    raw = match.group(1)
    # Normalize the common Qwen double-brace escaping: {{...}} -> {...}
    if raw.startswith("{{") and raw.endswith("}}"):
        raw = raw[1:-1]
    try:
        data = json.loads(raw)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    name = data.get("name") or data.get("tool") or ""
    arguments = data.get("arguments") or data.get("args") or {}
    if name:
        return json.dumps({"tool": name, "arguments": arguments}, ensure_ascii=False)
    return None

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think(text: str) -> str:
    """Remove Qwen3 ``<think>…</think>`` reasoning blocks from a reply.

    Also handles a dangling opening tag (model cut off mid-thought) and stray
    closing tags so the user never sees internal reasoning.
    """
    if not text or "<think>" not in text and "</think>" not in text:
        return text
    cleaned = _THINK_RE.sub("", text)
    # Drop an unterminated think block and any orphan tags.
    if "<think>" in cleaned:
        cleaned = cleaned.split("<think>", 1)[0]
    cleaned = cleaned.replace("</think>", "")
    return cleaned.strip()


# Default ("tiny") brain; kept for compatibility. The active model follows the
# ATULYA_BRAIN tier — see atulya.mastishk.
MODEL_REPO = "unsloth/Qwen3-0.6B-GGUF"
MODEL_FILE = "Qwen3-0.6B-Q4_K_M.gguf"
MODEL_URL = f"https://huggingface.co/{MODEL_REPO}/resolve/main/{MODEL_FILE}"

# Portable-first: models live inside the project's ``runtime/models`` folder so
# the whole system can be copied to another machine and just run. An explicit
# ATULYA_MODEL_DIR env var still wins; the old ~/.cache location is kept as a
# read fallback so existing installs don't re-download.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_PORTABLE_MODEL_DIR = _REPO_ROOT / "runtime" / "models"
_LEGACY_MODEL_DIR = Path.home() / ".cache" / "atulya" / "models"
_DEFAULT_MODEL_DIR = _PORTABLE_MODEL_DIR


def _model_dirs() -> list[Path]:
    dirs = []
    env_dir = os.environ.get("ATULYA_MODEL_DIR", "").strip()
    if env_dir:
        dirs.append(Path(env_dir))
    return dirs + [_PORTABLE_MODEL_DIR, _LEGACY_MODEL_DIR]


def _resolve_model_path() -> Path | None:

    # An explicitly chosen file always wins (it used to be checked last, so it
    # was silently ignored whenever the default model was present).
    alt_str = os.environ.get("ATULYA_GGUF_PATH", "").strip()
    if alt_str:
        alt = Path(alt_str)
        if alt.exists():
            return alt
        logger.warning("ATULYA_GGUF_PATH=%s does not exist; using the brain tier's model", alt_str)

    # The ATULYA_BRAIN tier's model first, then any smaller tier as fallback.
    spec = local_model_spec()
    for pattern in fallback_globs():
        for model_dir in _model_dirs():
            if pattern == spec["glob"]:
                candidate = model_dir / spec["file"]
                if candidate.exists():
                    return candidate
            if model_dir.exists():
                for found in sorted(model_dir.glob(pattern)):
                    return found
    return None


def _download_progress(url: str, dest: Path) -> None:
    logger.info("Downloading %s to %s (this may take a moment)...", url, dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, str(dest))
    logger.info("Download complete: %s (%.0f MB)", dest, dest.stat().st_size / 1024 / 1024)


def _ensure_model() -> Path | None:

    spec = local_model_spec()
    existing = _resolve_model_path()
    # A smaller fallback was found but the chosen tier's model is missing:
    # fetch it when auto-download is on, otherwise use the fallback.
    if existing and (os.environ.get("ATULYA_GGUF_PATH") or existing.match(spec["glob"])):
        return existing
    try:
        env_auto = os.environ.get("ATULYA_AUTO_DOWNLOAD_MODEL", "0")
        if env_auto.lower() in ("1", "true", "yes"):
            dest = _DEFAULT_MODEL_DIR / spec["file"]
            _download_progress(spec["url"], dest)
            return dest
    except Exception as exc:
        logger.warning("Model download failed (%s): %s", spec["label"], exc)
    return existing



def _with_think_switch(prompt: str) -> str:
    """Turn off Qwen3's hidden reasoning unless ATULYA_LOCAL_THINK=1.

    Qwen3 otherwise writes ~500 <think> tokens before every reply (~20s on CPU)
    that are stripped anyway; "/no_think" brings a reply down to ~1s.
    """
    if os.environ.get("ATULYA_LOCAL_THINK", "").lower() in {"1", "true", "yes"}:
        return prompt
    return f"{prompt} /no_think"

_ACTION_CUES = re.compile(
    r"\b(play|pause|open|launch|search|google|look up|find|turn|switch|set|remind|reminder|alarm|timer|"
    r"send|call|text|message|email|book|buy|order|add|cart|schedule|calendar|weather|news|volume|"
    r"tv|music|song|lights?|youtube|website|screenshot|click|type|run|download|read|write|save|delete|"
    r"track|expense|budget|bill|device|phone|remember)\b",
    re.IGNORECASE,
)


def _asked(prompt: str) -> str:
    """The user's own words, without the per-turn notes or earlier turns around them."""
    prompt = prompt.rsplit("\n\nUser: ", 1)[-1]
    return prompt.split("\n\n", 1)[-1] if prompt.startswith("[Notes for this turn]") else prompt


def lean_request(prompt: str, system_prompt: str, tools):
    """Shrink what a local CPU model must read each turn.

    Measured: the system prompt plus 14 tool schemas is ~1,800 tokens, read
    again by a CPU for every answer. Plain questions get only the persona; the
    tool section is added back when the message sounds like an action.
    ATULYA_LOCAL_LEAN=off sends everything.
    """
    if os.environ.get("ATULYA_LOCAL_LEAN", "on").strip().lower() in {"off", "0", "false", "no"}:
        return system_prompt, tools

    if _ACTION_CUES.search(_asked(prompt)):
        return system_prompt, tools
    return system_prompt.split(POLICY_MARK)[0].rstrip(), None


class LocalGGUFProvider:
    """Provider that loads a tiny GGUF model directly via llama-cpp-python.

    No external server needed. Model auto-downloads on first use if
    ATULYA_AUTO_DOWNLOAD_MODEL=true is set.
    """

    def __init__(self, model_path: str | Path | None = None):
        self._model_path = Path(model_path) if model_path else _ensure_model()
        self._llm = None
        self._lock = threading.Lock()  # llama.cpp contexts are not thread-safe

    def name(self) -> str:
        custom = os.environ.get("ATULYA_LOCAL_MODEL_NAME", "").strip()
        if custom:
            return f"Local Brain ({custom})"
        # Name the model actually loaded (a tier may have fallen back).
        if self._model_path:
            label = re.sub(r"[-.]Q\d.*$", "", self._model_path.stem, flags=re.IGNORECASE)
            return f"Local Brain ({label})"

        return f"Local Brain ({local_model_spec()['label']})"

    def is_available(self) -> bool:
        if not self._model_path or not self._model_path.exists():
            return False
        try:
            import llama_cpp  # noqa: F401 - availability probe
            return True
        except ImportError:
            return False

    def _load(self):
        if self._llm is not None:
            return
        import llama_cpp
        n_ctx = int(os.environ.get("ATULYA_LOCAL_MODEL_CONTEXT", "4096"))
        self._llm = llama_cpp.Llama(
            model_path=str(self._model_path),
            n_ctx=n_ctx,
            n_threads=int(os.environ.get("ATULYA_LOCAL_THREADS", "4")),
            n_batch=int(os.environ.get("ATULYA_LOCAL_BATCH", "512")),
            verbose=False,
        )

    def _complete(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            return self._llm.create_chat_completion(**kwargs)

    async def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        tools: list[dict[str, Any]] | None = None,
    ) -> str:
        """Chat with optional native tool calling (llama-cpp chat template)."""
        try:
            self._load()
            system_prompt, tools = lean_request(prompt, system_prompt, tools)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": _with_think_switch(prompt)})

            kwargs: dict[str, Any] = {
                "messages": messages,
                "max_tokens": int(os.environ.get("ATULYA_LOCAL_MAX_TOKENS", "512")),
                "temperature": float(os.environ.get("ATULYA_LOCAL_TEMPERATURE", "0.6")),
                "stop": ["<|im_end|>", "<|endoftext|>"],
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
                # Keep responses short when tool calling so the model doesn't ramble
                kwargs["max_tokens"] = int(os.environ.get("ATULYA_LOCAL_TOOL_MAX_TOKENS", "256"))

            response = await asyncio.to_thread(self._complete, kwargs)
            message = response["choices"][0]["message"]
            content = (message.get("content") or "").strip()
            if not content and message.get("tool_calls"):
                tool_calls = message["tool_calls"]
                if tool_calls:
                    first = tool_calls[0]
                    args = first.get("function", {}).get("arguments", "{}")
                    try:
                        args_parsed = json.loads(args)
                    except Exception:
                        args_parsed = {"_raw": args}
                    return json.dumps(
                        {"tool": first.get("function", {}).get("name", ""), "arguments": args_parsed},
                        ensure_ascii=False,
                    )
            content = _strip_think(content)
            # Normalize Qwen-style <tool_call> XML output into the JSON AtulyaLLM expects
            return _normalize_tool_call_xml(content) or content
        except Exception as exc:
            logger.warning("LocalGGUFProvider chat failed: %s", exc)
            raise

    async def chat_stream(self, prompt: str, system_prompt: str = "") -> AsyncIterator[str]:
        """Stream tokens incrementally from the local model (llama-cpp stream=True).

        Falls back to yielding the whole response if streaming is unsupported.
        """
        try:
            self._load()
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": _with_think_switch(prompt)})
            kwargs: dict[str, Any] = {
                "messages": messages,
                "max_tokens": int(os.environ.get("ATULYA_LOCAL_MAX_TOKENS", "512")),
                "temperature": float(os.environ.get("ATULYA_LOCAL_TEMPERATURE", "0.6")),
                "stop": ["<|im_end|>", "<|endoftext|>"],
                "stream": True,
            }
            def _gen():
                in_think = False
                buffer = ""
                for chunk in self._llm.create_chat_completion(**kwargs):
                    delta = (chunk.get("choices") or [{}])[0].get("delta", {})
                    piece = delta.get("content") or ""
                    if not piece:
                        continue
                    # Suppress everything between <think> and </think> so the
                    # user only hears the final answer, not the reasoning.
                    buffer += piece
                    while buffer:
                        if in_think:
                            end = buffer.find("</think>")
                            if end == -1:
                                buffer = buffer[-8:] if len(buffer) > 8 else buffer
                                break
                            buffer = buffer[end + len("</think>"):]
                            in_think = False
                        else:
                            start = buffer.find("<think>")
                            if start == -1:
                                # Hold back a small tail in case a tag is split.
                                safe = buffer[:-8] if len(buffer) > 8 else ""
                                if safe:
                                    yield safe
                                    buffer = buffer[len(safe):]
                                break
                            if start > 0:
                                yield buffer[:start]
                            buffer = buffer[start + len("<think>"):]
                            in_think = True
                if buffer and not in_think:
                    yield buffer

            # Generate on a worker thread so the event loop (the web server,
            # voice socket) stays responsive while tokens are produced.
            loop = asyncio.get_running_loop()
            queue: asyncio.Queue = asyncio.Queue()
            done = object()

            def _pump():
                try:
                    with self._lock:
                        for piece in _gen():
                            loop.call_soon_threadsafe(queue.put_nowait, piece)
                except Exception as exc:  # surfaced to the async side below
                    loop.call_soon_threadsafe(queue.put_nowait, exc)
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, done)

            threading.Thread(target=_pump, daemon=True).start()
            while (piece := await queue.get()) is not done:
                if isinstance(piece, Exception):
                    raise piece
                yield piece
        except Exception as exc:
            logger.warning("LocalGGUFProvider chat_stream failed: %s", exc)
            yield str(exc)


# ── the Atulya persona on top of the local model ──────────────────────────
# Kept short on purpose: a ~0.5B model follows a few plain rules far better
# than a long brief, and replies are usually spoken aloud.
PERSONA_SYSTEM = """You are Atulya, a personal AI assistant in the style of Jarvis from Iron Man.
You run locally on the user's own computer.

How you speak:
- Calm, warm and confident, with a light dry wit.
- Answer in one or two short sentences unless the user asks for more.
- Reply in the language the user spoke: English, Hindi (in Devanagari) or Hinglish. No emojis.
- If you don't know something, say so briefly. Never make up facts or tool results."""


class PersonaLocalProvider(LocalGGUFProvider):
    """The local model wearing the Atulya persona (system prompt + native tool calling)."""

    def name(self) -> str:
        # Same label rule as the base class, so a model picked by path shows its real name.
        return super().name().replace("Local Brain", "Atulya Local", 1)

    @staticmethod
    def _system_prompt(extra: str = "") -> str:
        return PERSONA_SYSTEM + (f"\n\n--- Context ---\n{extra}" if extra else "")

    async def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        tools: list[dict[str, Any]] | None = None,
    ) -> str:
        return await super().chat(prompt, self._system_prompt(system_prompt), tools)


def create_local_provider(model_path: str | os.PathLike | None = None) -> PersonaLocalProvider:
    """Factory for the persona-wrapped local provider."""
    return PersonaLocalProvider(model_path)


# ── bhasha ────────────────────────────────────────────────────────────
if TYPE_CHECKING:
    from atulya.smriti import MemoryManager


# Style rules that make replies read as a person, not a robot. Appended to
# every system prompt.
_HUMAN_STYLE = (
    "Voice & manner:\n"
    "- Speak like a sharp, caring friend — warm, direct, concise by default.\n"
    "- If the user seems upset, tired or anxious, acknowledge it in one natural "
    "sentence before helping.\n"
    "- Use the user's name when you know it. Light wit is welcome; never forced.\n"
    '- Never say "As an AI" or narrate your own limitations unprompted.\n'
    "- Never use emojis, emoticons or markdown: your replies are spoken aloud.\n"
)


@dataclass
class LLMEvent:
    type: str
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    text: str
    provider: str
    tool_steps: list[dict[str, Any]] = field(default_factory=list)
    needs_approval: bool = False
    pending_tool: dict[str, Any] | None = None
    # The real stages the cognitive kernel went through (understand / decide /
    # act / remember / think), for UIs to show what actually happened.
    trace: list[dict[str, Any]] = field(default_factory=list)


# Which tools the model sees first when the advertised list is capped.
# Personal-assistant essentials lead; anything unranked keeps registry order.
_TOOL_PRIORITY = {
    "home_control": 1,
    "set_reminder": 2,
    "get_weather": 3,
    "current_time": 4,
    "web_search": 5,
    "memory_search": 6,
    "memory_store": 7,
    "calendar_list": 8,
    "calendar_add": 9,
    "fetch_emails": 10,
    "send_email": 11,
    "todo_create": 12,
    "calculate": 13,
    "web_fetch": 14,
}


def _words(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", (text or "").lower()).split())


def is_echo(prompt: str, reply: str) -> bool:
    """True when a reply just repeats the question back ("who are you" -> "Who are you?")."""
    q, a = _words(prompt), _words(reply)
    return bool(a) and (a == q or (len(a.split()) <= 8 and a in q) or (len(q.split()) <= 8 and q in a and len(a) <= len(q) + 4))


def copies_memory(prompt: str, reply: str, memories: list[str]) -> bool:
    """True when the reply is word-for-word an answer recalled for a *different* question."""
    a = _words(reply)
    for entry in memories:
        m = re.match(r"Q:\s*(.*?)\s*\nA:\s*(.*)\Z", entry or "", re.S)
        if m and _words(m.group(2)) == a and _words(m.group(1)) != _words(prompt):
            return True
    return False


# Everything from this line on is tool plumbing; a local CPU model is sent only what is above it.
POLICY_MARK = "Operating policy:"

_PAST_CUES = re.compile(
    r"\b(remember|recall|remind me|earlier|before|last time|previous|yesterday|you said|i said|i told|"
    r"we talked|did i|what did|my name|my favou?rite)\b|याद|पहले|कल|बताया था",
    re.I,
)


def wants_memory(prompt: str) -> bool:
    """Should past conversations be shown to the model for this question?

    The tiny local model copies a recalled answer straight back at unrelated
    questions, so with it, memory is only brought in when you ask about the past.
    Bigger brains (balanced / power / cloud) always get it.
    """

    return active_brain() != "tiny" or bool(_PAST_CUES.search(prompt or ""))


def clean_history(history: list[dict[str, str]], keep: int = 10) -> list[dict[str, str]]:
    """Conversation turns safe to show a small model.

    A tiny model copies whatever it sees repeated, so a reply that only echoes
    its question, or repeats an earlier reply word for word, is dropped together
    with the question it answered. Only the last ``keep`` turns are used.
    """
    cleaned: list[dict[str, str]] = []
    seen: set[str] = set()
    last_user = ""
    pending_user: dict[str, str] | None = None
    for item in history:
        role = item.get("role", "user")
        content = item.get("content") or item.get("text") or ""
        if not content:
            continue
        if role == "user":
            if pending_user is not None:
                cleaned.append(pending_user)
            pending_user, last_user = item, content
            continue
        key = _words(content)
        if is_echo(last_user, content) or key in seen:
            pending_user = None  # drop the question and its bad answer
            continue
        seen.add(key)
        if pending_user is not None:
            cleaned.append(pending_user)
            pending_user = None
        cleaned.append(item)
    if pending_user is not None:
        cleaned.append(pending_user)
    return cleaned[-keep:]


def _echoed_memory(entry: str) -> bool:
    """A remembered 'Q: …\nA: …' pair whose answer only repeats its question."""
    m = re.match(r"Q:\s*(.*?)\s*\nA:\s*(.*)\Z", entry or "", re.S)
    return bool(m) and (not _words(m.group(1)) or is_echo(m.group(1), m.group(2)))


class AtulyaLLM:
    """Free-first chat orchestrator with a small ReAct-style tool loop."""

    def __init__(
        self,
        tools: ToolRegistry | None = None,
        max_tool_iterations: int = 3,
        allow_exec: bool = False,
        use_memory: bool = False,
        memory_dir: str = "kosh/memory",
    ):
        if tools is None:
            # One tool surface: yantra tools + personal-assistant tools.
            tools = build_unified_registry()
        self.tools = tools
        self.max_tool_iterations = max_tool_iterations
        self.allow_exec = allow_exec
        self.router = ProviderRouter()
        self.persona = Persona()
        self.use_memory = use_memory
        self.memory_dir = memory_dir
        self._memory = None
        self.mood = MoodState.load()

    def _human_context(self, prompt: str) -> str:
        """Perceive the user's emotion, nudge Atulya's mood, and return a short
        directive block for the system prompt. Best-effort; never raises."""
        try:
            reading = detect_emotion(prompt)
            self.mood.nudge(reading)
            self.mood.save()
            return build_emotional_directive(reading, self.mood)
        except Exception:
            return ""

    def _ensure_memory(self):
        if self._memory is None and self.use_memory:
            try:
                from atulya.smriti import MemoryManager

                self._memory = MemoryManager(self.memory_dir)
            except Exception:
                self._memory = False
        return self._memory or None

    async def _ensure_memory_initialized(self):
        mgr = self._ensure_memory()
        if not mgr:
            return None
        if not getattr(mgr, "_initialized", False):
            try:
                await mgr.initialize()
                mgr._initialized = True
            except Exception:
                return None
        return mgr

    def memory(self) -> "MemoryManager | None":
        return self._ensure_memory()

    async def _retrieve_memory_context(self, prompt: str, limit: int = 5) -> list[str]:
        mgr = await self._ensure_memory_initialized()
        if not mgr:
            return []
        try:
            entries = await mgr.semantic_search(prompt, limit)
            return [entry.content for entry in entries
                    if getattr(entry, "content", None) and not _echoed_memory(entry.content)]
        except Exception:
            return []

    async def _store_exchange(self, prompt: str, response_text: str) -> None:
        mgr = await self._ensure_memory_initialized()
        if not mgr or not response_text or is_echo(prompt, response_text):
            return  # never remember an answer that only parrots the question: a small model copies it back
        try:
            combined = f"Q: {prompt}\nA: {response_text}"
            await mgr.store_session(combined)
        except Exception:
            pass

    async def ask(
        self,
        prompt: str,
        history: list[dict[str, str]] | None = None,
        tools_enabled: bool = True,
        approved_tool_call: dict[str, Any] | None = None,
        provider: str = "",
        context: str = "",
    ) -> LLMResponse:
        system_prompt = self._build_system_prompt(history or [], user_prompt=prompt, context=context)
        working_prompt = self._turn_notes(prompt, context) + self._compose_prompt(prompt, history or [])
        steps: list[dict[str, Any]] = []
        requested_provider = provider
        memories: list[str] = []

        if requested_provider.startswith("public") or requested_provider == "public":
            pass
        elif self.use_memory and (requested_provider == "" or "private" in requested_provider or "local" in requested_provider.lower() or requested_provider == "private"):
            memories = await self._retrieve_memory_context(prompt) if wants_memory(prompt) else []
            if memories:
                working_prompt = (
                    "Relevant past interactions:\n"
                    + "\n".join(f"- {m}" for m in memories)
                    + f"\n\n{working_prompt}"
                )

        if approved_tool_call and tools_enabled:
            step = await self._execute_tool_call(approved_tool_call)
            steps.append(step)
            working_prompt = (
                f"{working_prompt}\n\n"
                f"User approved tool:\n{json.dumps(approved_tool_call, ensure_ascii=False)}\n\n"
                f"Tool result:\n{json.dumps(step, ensure_ascii=False)}\n\n"
                "Now answer the user directly. If another tool is essential, emit exactly one JSON tool call."
            )

        for _ in range(self.max_tool_iterations if tools_enabled else 1):
            text, provider_name = await self.router.chat(
                working_prompt,
                system_prompt,
                preferred_provider=requested_provider,
                tools=self._build_tool_schemas() if tools_enabled else None,
            )
            if is_echo(prompt, text) or copies_memory(prompt, text, memories):
                # The model parroted the question or a recalled answer: ask it plainly once, without memory.
                text, provider_name = await self.router.chat(
                    prompt, system_prompt, preferred_provider=requested_provider, tools=None)
            tool_call = self._extract_tool_call(text)
            if not tool_call or not tools_enabled:
                final = LLMResponse(text=self._strip_tool_blocks(text).strip(), provider=provider_name, tool_steps=steps)
                await self._store_exchange(prompt, final.text)
                return final

            tool_calls = self._normalize_tool_calls(tool_call)
            risky = [call for call in tool_calls if needs_confirmation(call["tool"], call["arguments"])]
            if risky:
                return LLMResponse(
                    text="Approval required before running this tool.",
                    provider=provider_name,
                    tool_steps=steps,
                    needs_approval=True,
                    pending_tool=risky[0],
                )

            new_steps = await asyncio.gather(*(self._execute_tool_call(call) for call in tool_calls))
            steps.extend(new_steps)
            working_prompt = (
                f"{working_prompt}\n\n"
                f"Assistant requested tool:\n{json.dumps(tool_call, ensure_ascii=False)}\n\n"
                f"Tool result:\n{json.dumps(new_steps, ensure_ascii=False)}\n\n"
                "Now answer the user directly. If another tool is essential, emit exactly one JSON tool call."
            )

        fallback = "I ran out of tool iterations before completing the request. Here is what I found:\n"
        fallback += "\n".join(f"- {s['tool']}: {s.get('output') or s.get('error')}" for s in steps)
        final = LLMResponse(text=fallback, provider=requested_provider or "Diagnostics Fallback", tool_steps=steps)
        await self._store_exchange(prompt, final.text)
        return final

    async def _execute_tool_call(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_tool_call(tool_call)
        tool_name = normalized["tool"]
        arguments = normalized["arguments"]
        if tool_name == "exec":
            # Execution permission is server policy, never a caller- or
            # model-supplied argument: override (not setdefault) allow_exec and
            # drop any allow_list so ATULYA_EXEC_ALLOWLIST stays authoritative.
            arguments["allow_exec"] = self.allow_exec
            arguments.pop("allow_list", None)
        result = await self.tools.execute(tool_name, **arguments)
        return {
            "tool": tool_name,
            "arguments": arguments,
            "success": result.success,
            "output": result.output[:4000],
            "error": result.error,
        }

    async def run_tool(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        """Execute one tool call with the brain's policies applied; returns a step dict."""
        return await self._execute_tool_call(tool_call)

    async def remember(self, prompt: str, response_text: str) -> None:
        """Write an exchange (e.g. an action the kernel took) to long-term memory."""
        await self._store_exchange(prompt, response_text)

    @staticmethod
    def _normalize_tool_call(tool_call: dict[str, Any]) -> dict[str, Any]:
        tool_name = str(tool_call.get("tool") or tool_call.get("name") or "").strip()
        arguments = tool_call.get("arguments") or tool_call.get("args") or {}
        if not isinstance(arguments, dict):
            arguments = {}
        return {"tool": tool_name, "arguments": arguments}

    @staticmethod
    def _normalize_tool_calls(tool_call: dict[str, Any]) -> list[dict[str, Any]]:
        raw_calls = tool_call.get("tools") or tool_call.get("tool_calls")
        if isinstance(raw_calls, list):
            return [AtulyaLLM._normalize_tool_call(call) for call in raw_calls if isinstance(call, dict)]
        return [AtulyaLLM._normalize_tool_call(tool_call)]

    async def stream(
        self,
        prompt: str,
        history: list[dict[str, str]] | None = None,
        tools_enabled: bool = True,
        approved_tool_call: dict[str, Any] | None = None,
        provider: str = "",
        context: str = "",
    ) -> AsyncIterator[LLMEvent]:
        # True incremental streaming when no tools/approval gate is involved:
        # each provider's chat_stream (llama-cpp token generator) is used directly.
        if not tools_enabled and not approved_tool_call:
            system_prompt = self._build_system_prompt(history or [], user_prompt=prompt, context=context)
            working_prompt = self._turn_notes(prompt, context) + self._compose_prompt(prompt, history or [])
            parts: list[str] = []
            async for piece, provider_name in self.router.stream(
                working_prompt,
                system_prompt,
                preferred_provider=provider,
            ):
                if piece:
                    parts.append(piece)
                    yield LLMEvent("token", content=piece)
                    await asyncio.sleep(0)
            yield LLMEvent(
                "done",
                metadata={"provider": provider_name, "steps": []},
            )
            return

        response = await self.ask(
            prompt,
            history=history,
            tools_enabled=tools_enabled,
            approved_tool_call=approved_tool_call,
            provider=provider,
            context=context,
        )
        for step in response.tool_steps:
            yield LLMEvent("tool", metadata=step)
        if response.needs_approval:
            yield LLMEvent(
                "done",
                metadata={
                    "provider": response.provider,
                    "steps": response.tool_steps,
                    "needs_approval": True,
                    "pending_tool": response.pending_tool,
                    "tool": (response.pending_tool or {}).get("tool"),
                    "tool_args": (response.pending_tool or {}).get("arguments", {}),
                },
            )
            return
        for chunk in _chunk_text(response.text):
            yield LLMEvent("token", content=chunk)
            await asyncio.sleep(0)
        yield LLMEvent("done", metadata={"provider": response.provider, "steps": response.tool_steps})

    def _build_system_prompt(self, history: list[dict[str, str]], user_prompt: str = "", context: str = "") -> str:
        prompt = self.persona.get_system_prompt()
        tools = self.tools.list_tools()
        tool_lines = [f"- {item['name']}: {item['description']}" for item in tools]
        # Kept byte-identical across turns so llama.cpp can reuse its KV cache;
        # anything that changes per turn goes in _turn_notes instead.
        human_block = f"\n\n{_HUMAN_STYLE}"
        return (
            f"{prompt}"
            f"{human_block}\n\n"
            f"{POLICY_MARK}\n"
            "- Use free/local providers first. Paid APIs are optional fallbacks only when configured.\n"
            "- Tantra must never block production behavior.\n"
            "- For tool use, emit exactly one JSON object like "
            '{"tool":"web_search","arguments":{"query":"..."}} and no markdown around it.\n'
            '- For parallel safe tools, emit {"tools":[{"tool":"...","arguments":{}}, ...]}.\n'
            "- Do not call exec unless the user explicitly asks and execution is enabled.\n\n"
            "Available tools:\n" + "\n".join(tool_lines[:30])
        )

    async def warm_up(self) -> None:
        """Prefill the stable system prompt once so the first real reply is
        fast (the local model otherwise spends ~30s reading it on turn one)."""
        await self.router.chat("hi", self._build_system_prompt([]), tools=self._build_tool_schemas())

    def _turn_notes(self, user_prompt: str = "", context: str = "") -> str:
        """Per-turn facts (clock, mood, what we know of the user), sent with
        the user message so the cached system prompt stays valid."""
        notes = [f"Current local date and time: {datetime.now().strftime('%A %d %B %Y, %I:%M %p')}"]
        emotional = self._human_context(user_prompt) if user_prompt else ""
        if emotional:
            notes.append(emotional)
        if context:  # what Atulya has learned about this user
            notes.append(context)
        return "[Notes for this turn]\n" + "\n".join(notes) + "\n\n"

    def _build_tool_schemas(self) -> list[dict[str, Any]]:
        """Build OpenAI-style function schemas for the model's native tool loop.

        Small models degrade with long tool lists, so only the top
        ``ATULYA_MAX_TOOL_SCHEMAS`` (default 14) are advertised, ranked
        assistant-first by ``_TOOL_PRIORITY``; unranked tools keep registry
        order. Tools that declare a JSON ``parameters`` schema expose it.
        """
        limit = max(1, int(os.environ.get("ATULYA_MAX_TOOL_SCHEMAS", "14")))
        listed = self.tools.list_tools()
        ranked = sorted(
            enumerate(listed),
            key=lambda item: (_TOOL_PRIORITY.get(item[1]["name"], 1000), item[0]),
        )
        schemas = []
        for _, tool in ranked[:limit]:
            obj = self.tools.get(tool["name"]) if hasattr(self.tools, "get") else None
            params = getattr(obj, "parameters", None) or {"type": "object", "properties": {}}
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"][:120],
                    "parameters": params,
                },
            })
        return schemas

    @staticmethod
    def _compose_prompt(prompt: str, history: list[dict[str, str]]) -> str:

        # A tiny model copies earlier replies instead of answering, so it gets no history.
        trimmed = [] if active_brain() == "tiny" else clean_history(history)
        if not trimmed:
            return prompt
        turns = []
        for item in trimmed:
            role = item.get("role", "user")
            content = item.get("content") or item.get("text") or ""
            if content:
                turns.append(f"{role}: {content}")
        return "Conversation so far:\n" + "\n".join(turns) + f"\n\nUser: {prompt}"

    @staticmethod
    def _extract_tool_call(text: str) -> dict[str, Any] | None:
        candidates = [text]
        fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
        candidates.extend(fenced)
        brace = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if brace:
            candidates.append(brace.group(0))
        for candidate in candidates:
            try:
                data = json.loads(candidate.strip())
            except Exception:
                continue
            if isinstance(data, dict) and ("tool" in data or "name" in data or "tools" in data or "tool_calls" in data):
                return data
        return None

    @staticmethod
    def _strip_tool_blocks(text: str) -> str:
        if AtulyaLLM._extract_tool_call(text):
            cleaned = re.sub(r"```(?:json)?\s*\{.*?\}\s*```", "", text, flags=re.DOTALL).strip()
            if cleaned.startswith("{") and cleaned.endswith("}"):
                return ""
            return cleaned
        return text


def _chunk_text(text: str, size: int = 28) -> list[str]:
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


async def ask(prompt: str, history: list[dict[str, str]] | None = None) -> LLMResponse:
    return await get_default_llm().ask(prompt, history=history)


async def stream(
    prompt: str,
    history: list[dict[str, str]] | None = None,
    approved_tool_call: dict[str, Any] | None = None,
) -> AsyncIterator[LLMEvent]:
    async for event in get_default_llm().stream(prompt, history=history, approved_tool_call=approved_tool_call):
        yield event


@lru_cache(maxsize=1)
def get_default_llm() -> AtulyaLLM:
    return AtulyaLLM(use_memory=True)

