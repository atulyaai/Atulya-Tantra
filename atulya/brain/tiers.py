"""Brain tiers: what runs by default, what to recommend, which brain is active."""
from __future__ import annotations

import os
from typing import Any



from atulya import brain as _d

# ── brain ────────────────────────────────────────────────────────────
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
        return _d.recommend_tier()
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


