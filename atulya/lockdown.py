"""Lockdown profile: ``ATULYA_LOCKDOWN=on`` keeps Atulya reachable from this computer only."""
from __future__ import annotations

import os


def lockdown_on() -> bool:
    return os.environ.get("ATULYA_LOCKDOWN", "").strip().lower() in ("on", "1", "true", "yes")


def bind_host(default: str = "127.0.0.1") -> str:
    """Host to listen on: always localhost under lockdown, otherwise ``ATULYA_HOST`` or the default."""
    if lockdown_on():
        return "127.0.0.1"
    return os.environ.get("ATULYA_HOST", default)


def cors_origins() -> list[str] | None:
    """Explicit CORS origins, ``[]`` (none) under lockdown, or None to use the app's default."""
    listed = [o.strip() for o in os.environ.get("ATULYA_CORS_ORIGINS", "").split(",") if o.strip()]
    if listed:
        return listed
    return [] if lockdown_on() else None
