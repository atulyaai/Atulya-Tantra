"""Tiny local GGUF model provider using llama-cpp-python.

Downloads and loads Qwen2.5-0.5B-Instruct (Q4_K_M, ~350 MB) on first use.
No Ollama required. Falls back gracefully if llama-cpp-python is not installed.
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

MODEL_REPO = "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
MODEL_FILE = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
MODEL_URL = f"https://huggingface.co/{MODEL_REPO}/resolve/main/{MODEL_FILE}"
_DEFAULT_MODEL_DIR = Path.home() / ".cache" / "atulya" / "models"


def _resolve_model_path() -> Path | None:
    model_dir = Path(os.environ.get("ATULYA_MODEL_DIR", str(_DEFAULT_MODEL_DIR)))
    model_path = model_dir / MODEL_FILE
    if model_path.exists():
        return model_path
    alt = Path(os.environ.get("ATULYA_GGUF_PATH", ""))
    if alt and alt.exists():
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
        n_ctx = int(os.environ.get("ATULYA_LOCAL_MODEL_CONTEXT", "2048"))
        self._llm = llama_cpp.Llama(
            model_path=str(self._model_path),
            n_ctx=n_ctx,
            n_threads=int(os.environ.get("ATULYA_LOCAL_THREADS", "4")),
            verbose=False,
        )

    async def chat(self, prompt: str, system_prompt: str = "") -> str:
        try:
            self._load()
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = self._llm.create_chat_completion(
                messages=messages,
                max_tokens=int(os.environ.get("ATULYA_LOCAL_MAX_TOKENS", "256")),
                temperature=float(os.environ.get("ATULYA_LOCAL_TEMPERATURE", "0.7")),
                stop=["<|im_end|>", "<|endoftext|>"],
            )
            return response["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.warning("LocalGGUFProvider chat failed: %s", exc)
            raise
