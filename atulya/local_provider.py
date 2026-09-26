"""Tiny local GGUF model provider using llama-cpp-python.

Downloads and loads Qwen2.5-0.5B-Instruct (Q4_K_M, ~350 MB) on first use.
No Ollama required. Falls back gracefully if llama-cpp-python is not installed.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


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


def _resolve_model_path() -> Path | None:
    search_dirs = []
    env_dir = os.environ.get("ATULYA_MODEL_DIR", "").strip()
    if env_dir:
        search_dirs.append(Path(env_dir))
    search_dirs += [_PORTABLE_MODEL_DIR, _LEGACY_MODEL_DIR]
    for model_dir in search_dirs:
        # Accept the configured file, or any Qwen3-0.6B GGUF quant present.
        candidate = model_dir / MODEL_FILE
        if candidate.exists():
            return candidate
        if model_dir.exists():
            for found in sorted(model_dir.glob("Qwen3-0.6B*.gguf")):
                return found
    alt_str = os.environ.get("ATULYA_GGUF_PATH", "").strip()
    if alt_str:
        alt = Path(alt_str)
        if alt.exists():
            return alt
    return None


def _download_progress(url: str, dest: Path) -> None:
    logger.info("Downloading %s to %s (this may take a moment)...", url, dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, str(dest))
    logger.info("Download complete: %s (%.0f MB)", dest, dest.stat().st_size / 1024 / 1024)


def _ensure_model() -> Path | None:
    existing = _resolve_model_path()
    if existing:
        return existing
    try:
        env_auto = os.environ.get("ATULYA_AUTO_DOWNLOAD_MODEL", "0")
        if env_auto.lower() in ("1", "true", "yes"):
            dest = _DEFAULT_MODEL_DIR / MODEL_FILE
            _download_progress(MODEL_URL, dest)
            return dest
    except Exception as exc:
        logger.warning("Model download failed: %s", exc)
    return None


class LocalGGUFProvider:
    """Provider that loads a tiny GGUF model directly via llama-cpp-python.

    No external server needed. Model auto-downloads on first use if
    ATULYA_AUTO_DOWNLOAD_MODEL=true is set.
    """

    def __init__(self, model_path: str | Path | None = None):
        self._model_path = Path(model_path) if model_path else _ensure_model()
        self._llm = None

    def name(self) -> str:
        return "Tiny Local (Qwen2.5-0.5B)"

    def is_available(self) -> bool:
        if not self._model_path or not self._model_path.exists():
            return False
        try:
            import llama_cpp
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

    async def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        tools: list[dict[str, Any]] | None = None,
    ) -> str:
        """Chat with optional native tool calling (llama-cpp chat template)."""
        try:
            self._load()
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

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

            response = self._llm.create_chat_completion(**kwargs)
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
            messages.append({"role": "user", "content": prompt})
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

            for piece in _gen():
                yield piece
        except Exception as exc:
            logger.warning("LocalGGUFProvider chat_stream failed: %s", exc)
            yield str(exc)
