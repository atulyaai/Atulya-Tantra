"""Shared dashboard state."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
# Local training progress must not be replaced by a bundled model sample.
OUTPUTS_DIR = _ROOT / "tantra" / "outputs" / "npdna"
MODEL_OUTPUT_DIRS = (OUTPUTS_DIR, _ROOT / "tantra" / "outputs" / "npdna_nano")
DATASETS_DIR = _ROOT / "tantra" / "training" / "datasets"
MAX_PROMPT_CHARS = 20_000
MAX_CHAT_TOKENS = 4096

def _load_admin_token() -> tuple[str, str]:
    env_token = os.environ.get("ATULYA_DASHBOARD_TOKEN")
    if env_token:
        return env_token, "env"
    return secrets.token_urlsafe(24), "generated_runtime"


ADMIN_TOKEN, ADMIN_TOKEN_SOURCE = _load_admin_token()


class DashboardState:
    MODEL_CACHE = {}
    MODEL_CACHE_MTIME = {}
    TRAIN_PROCESS = None


