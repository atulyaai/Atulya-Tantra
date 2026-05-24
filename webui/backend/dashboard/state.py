"""Shared dashboard state."""

from __future__ import annotations

import secrets
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
OUTPUTS_DIR = _ROOT / "tantra" / "outputs" / "npdna"
DATASETS_DIR = _ROOT / "tantra" / "training" / "datasets"
MAX_PROMPT_CHARS = 20_000
MAX_CHAT_TOKENS = 512

def _load_admin_token() -> tuple[str, str]:
    env_token = __import__("os").environ.get("ATULYA_DASHBOARD_TOKEN")
    if env_token:
        return env_token, "env"
    return secrets.token_urlsafe(24), "generated_runtime"


ADMIN_TOKEN, ADMIN_TOKEN_SOURCE = _load_admin_token()


class DashboardState:
    MODEL_CACHE = {}
    MODEL_CACHE_MTIME = {}
    TRAIN_PROCESS = None


