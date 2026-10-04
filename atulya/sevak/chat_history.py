"""Persistent chat history for Atulya users."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atulya.raksha import vault

_ROOT = Path(__file__).resolve().parents[2]
HISTORY_FILE = _ROOT / "kosh" / "chat_history.json"
_lock = threading.Lock()
_MAX_MESSAGES = 300


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_store() -> dict[str, Any]:
    if not HISTORY_FILE.exists():
        return {"users": {}}
    try:
        data = json.loads(vault.read_text(HISTORY_FILE))
    except vault.VaultLocked:
        raise  # locked is not empty: callers must not overwrite it
    except Exception:
        return {"users": {}}
    if not isinstance(data, dict):
        return {"users": {}}
    data.setdefault("users", {})
    return data


def _write_store(data: dict[str, Any]) -> None:
    vault.write_text(HISTORY_FILE, json.dumps(data, indent=2, ensure_ascii=False))


def _user_key(user: dict[str, Any] | None) -> str:
    return str((user or {}).get("username") or "anonymous").strip().lower() or "anonymous"


def list_messages(user: dict[str, Any] | None, limit: int = 120) -> list[dict[str, Any]]:
    key = _user_key(user)
    with _lock:
        store = _read_store()
        messages = list(store["users"].get(key, {}).get("messages") or [])
    return messages[-max(1, min(limit, _MAX_MESSAGES)):]


def append_exchange(
    user: dict[str, Any] | None,
    prompt: str,
    response: str,
    *,
    provider: str = "",
    surface: str = "chat",
) -> None:
    prompt = str(prompt or "").strip()
    response = str(response or "").strip()
    if not prompt and not response:
        return

    key = _user_key(user)
    created = _now()
    new_messages = []
    if prompt:
        new_messages.append({"role": "user", "text": prompt, "created_at": created, "surface": surface})
    if response:
        new_messages.append({
            "role": "assistant",
            "text": response,
            "created_at": _now(),
            "surface": surface,
            "provider": provider,
        })

    try:
        with _lock:
            store = _read_store()
            user_store = store["users"].setdefault(key, {"messages": []})
            user_store["messages"] = (list(user_store.get("messages") or []) + new_messages)[-_MAX_MESSAGES:]
            user_store["updated_at"] = _now()
            _write_store(store)
    except vault.VaultLocked:
        pass  # history is locked (wrong passphrase): skip saving rather than break the chat or overwrite it


def clear_messages(user: dict[str, Any] | None) -> None:
    key = _user_key(user)
    with _lock:
        store = _read_store()
        if key in store["users"]:
            del store["users"][key]
        _write_store(store)
