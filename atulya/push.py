"""Backward-compatible imports for Web Push, now implemented in ``sandesh``."""
from __future__ import annotations

from atulya.sandesh import (
    _legacy_path as _legacy_path,
    _path as _path,
    _read as _read,
    _write as _write,
    configured,
    public_key,
    send,
    subscribe,
    unsubscribe,
)

__all__ = ["configured", "public_key", "send", "subscribe", "unsubscribe"]
