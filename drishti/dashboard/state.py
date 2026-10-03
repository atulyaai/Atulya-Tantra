"""Shared dashboard state."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
# Dashboard runtime files (automation jobs). Git-ignored.
OUTPUTS_DIR = _ROOT / "outputs"
MAX_PROMPT_CHARS = 20_000
MAX_CHAT_TOKENS = 4096

def _load_admin_token() -> tuple[str, str]:
    env_token = os.environ.get("ATULYA_DASHBOARD_TOKEN")
    if env_token:
        return env_token, "env"
    return secrets.token_urlsafe(24), "generated_runtime"


ADMIN_TOKEN, ADMIN_TOKEN_SOURCE = _load_admin_token()


def _load_jwt_secret() -> str:
    """The key that signs sign-in tokens (including 90-day device tokens).

    ATULYA_JWT_SECRET wins; a configured ATULYA_DASHBOARD_TOKEN keeps working as
    before; otherwise a random key is created once in config/jwt_secret.key
    (owner-only) so tokens survive restarts and every worker agrees on it.
    """
    if os.environ.get("ATULYA_JWT_SECRET"):
        return os.environ["ATULYA_JWT_SECRET"]
    if ADMIN_TOKEN_SOURCE == "env":
        return ADMIN_TOKEN
    path = Path(os.environ.get("ATULYA_JWT_SECRET_FILE") or _ROOT / "config" / "jwt_secret.key")
    for _ in range(2):
        try:
            existing = path.read_text(encoding="utf-8").strip()
            if existing:
                return existing
        except OSError:
            pass
        secret = secrets.token_urlsafe(48)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue  # another worker created it first: read theirs
        except OSError:
            return secret  # read-only disk: tokens last until restart
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(secret)
        return secret
    return secrets.token_urlsafe(48)


JWT_SECRET = _load_jwt_secret()



