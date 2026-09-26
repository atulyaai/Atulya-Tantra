"""One-setting brain tiers.

``ATULYA_BRAIN`` picks how big a brain Atulya runs, trading speed and RAM for
quality:

  tiny      Qwen3-0.6B  (~0.4 GB)  runs on anything — the default
  balanced  Qwen3-1.7B  (~1.1 GB)  clearly better reasoning and tool use
  power     Qwen3-4B    (~2.5 GB)  best local quality; wants ~6 GB free RAM
  cloud     configured cloud providers first (Groq, OpenRouter, Gemini, …),
            with the tiny local model as the offline fallback

The chosen tier's model downloads into ``runtime/models`` on first run when
``ATULYA_AUTO_DOWNLOAD_MODEL=true``. If it isn't there yet, Atulya falls back to
any smaller local model it has, so switching tiers never leaves it brainless.
To run something else entirely, point ``ATULYA_GGUF_PATH`` at any GGUF file.

This module is dependency-free so the model provider can import it cheaply.
"""
from __future__ import annotations

import os
from typing import Any

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
