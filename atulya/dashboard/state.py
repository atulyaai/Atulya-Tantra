"""NP-DNA Dashboard State Management.

Centralizes environment configuration, directory paths, global limits,
and mutable runtime states (e.g., training subprocesses, caches).
"""
from __future__ import annotations
import os
import logging
import secrets
import subprocess
from pathlib import Path

logger = logging.getLogger("atulya.dashboard.state")

# Path calculation: state.py is in atulya/dashboard/
_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUTS_DIR = _ROOT / "tantra" / "outputs" / "npdna"

# Default configuration limits
MAX_STEPS = int(os.environ.get("ATULYA_DASHBOARD_MAX_STEPS", "10000"))
MAX_LIMIT = int(os.environ.get("ATULYA_DASHBOARD_MAX_LIMIT", "50000"))
MAX_SEQ_LIMIT = int(os.environ.get("ATULYA_DASHBOARD_MAX_SEQ_LIMIT", "512"))
MAX_PROMPT_CHARS = int(os.environ.get("ATULYA_DASHBOARD_MAX_PROMPT_CHARS", "4000"))
MAX_CHAT_TOKENS = int(os.environ.get("ATULYA_DASHBOARD_MAX_TOKENS", "256"))
MAX_HISTORY_POINTS = int(os.environ.get("ATULYA_DASHBOARD_HISTORY", "300"))
DEFAULT_SYSTEM_PROMPT = "You are Atulya. Be warm, thoughtful, and direct."


class DashboardState:
    """Container for mutable server runtime states."""
    TRAIN_PROC: subprocess.Popen | None = None
    TRAIN_LOG_F: object | None = None
    MODEL_CACHE: dict[str, object] = {}
    MODEL_CACHE_MTIME: dict[str, float] = {}
    ADMIN_TOKEN: str | None = None
    ADMIN_TOKEN_SOURCE: str | None = None


def load_admin_token() -> tuple[str, str]:
    """Retrieve or generate the administrator access token."""
    if DashboardState.ADMIN_TOKEN is not None:
        return DashboardState.ADMIN_TOKEN, DashboardState.ADMIN_TOKEN_SOURCE

    env_token = os.environ.get("ATULYA_DASHBOARD_TOKEN", "").strip()
    if env_token:
        DashboardState.ADMIN_TOKEN = env_token
        DashboardState.ADMIN_TOKEN_SOURCE = "env"
        return env_token, "env"

    token_path = OUTPUTS_DIR / "dashboard_token.txt"
    try:
        if token_path.exists():
            token = token_path.read_text(encoding="utf-8").strip()
            if token:
                DashboardState.ADMIN_TOKEN = token
                DashboardState.ADMIN_TOKEN_SOURCE = str(token_path)
                return token, str(token_path)
    except OSError:
        pass

    token = secrets.token_urlsafe(24)
    try:
        token_path.parent.mkdir(parents=True, exist_ok=True)
        # Open with owner-only permissions (0o600)
        fd = os.open(str(token_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(token + "\n")
        except Exception:
            os.close(fd)
            raise
        try:
            os.chmod(str(token_path), 0o600)
        except OSError:
            pass
        DashboardState.ADMIN_TOKEN = token
        DashboardState.ADMIN_TOKEN_SOURCE = str(token_path)
        return token, str(token_path)
    except OSError:
        DashboardState.ADMIN_TOKEN = token
        DashboardState.ADMIN_TOKEN_SOURCE = "session"
        return token, "session"


# Eager load the token on import to ensure token files exist and are logged
ADMIN_TOKEN, ADMIN_TOKEN_SOURCE = load_admin_token()
