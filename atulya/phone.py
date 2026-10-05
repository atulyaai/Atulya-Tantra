"""Paired phone inbox and command queue, isolated from bank SMS parsing."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from atulya import raksha as vault

MAX_ITEMS_PER_POST = 100
MAX_STORED_ITEMS = 500
MAX_ITEM_CHARS = 4_000
MAX_BATCH_CHARS = 512_000
_COMMAND_TTL = 120
_LOCK = threading.RLock()


def _path() -> Path:
    return Path(os.environ.get("ATULYA_AGENT_DATA_DIR", "kosh/agent")) / "phone_inbox.json"


def _read() -> dict[str, Any]:
    try:
        value = json.loads(vault.read_text(_path()))
    except FileNotFoundError:
        return {"sms": [], "notifications": [], "location": [], "commands": []}
    if not isinstance(value, dict):
        raise ValueError("Phone store must be a JSON object.")
    for key in ("sms", "notifications", "location", "commands"):
        value.setdefault(key, [])
    return value


def _write(value: dict[str, Any]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    vault.write_text(path, json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def _normalise(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("Every phone inbox item must be a JSON object.")
    try:
        encoded = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Phone inbox items must contain JSON values only.") from exc
    if len(encoded) > MAX_ITEM_CHARS:
        raise ValueError(f"Phone inbox items must be {MAX_ITEM_CHARS} characters or smaller.")
    return json.loads(encoded)


def add_items(kind: str, device_id: str, items: list[Any]) -> dict[str, int]:
    """Store a bounded batch, deduplicating repeated phone messages by content and device."""
    if kind not in ("sms", "notifications", "location"):
        raise ValueError("Phone data type must be sms, notifications, or location.")
    if not isinstance(items, list) or len(items) > MAX_ITEMS_PER_POST:
        raise ValueError(f"Send an items array with no more than {MAX_ITEMS_PER_POST} items.")
    clean = [_normalise(item) for item in items]
    if sum(len(json.dumps(item, ensure_ascii=False)) for item in clean) > MAX_BATCH_CHARS:
        raise ValueError("Phone sync batches must be 512 KB or smaller.")
    added = 0
    with _LOCK:
        store = _read()
        rows = store[kind]
        known = {row.get("digest") for row in rows if isinstance(row, dict)}
        now = time.time()
        for item in clean:
            raw = json.dumps(item, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            digest = hashlib.sha256(f"{device_id}\0{kind}\0{raw}".encode()).hexdigest()
            if digest in known:
                continue
            rows.append({"id": uuid.uuid4().hex, "device_id": device_id, "received_at": now,
                         "digest": digest, "item": item})
            known.add(digest)
            added += 1
        store[kind] = rows[-MAX_STORED_ITEMS:]
        _write(store)
    return {"received": len(clean), "added": added, "duplicates": len(clean) - added}


def list_items(kind: str = "all", limit: int = 100) -> list[dict[str, Any]]:
    """Return newest phone inbox items; callers must authenticate as an administrator."""
    if kind not in ("all", "sms", "notifications", "location"):
        raise ValueError("Unknown phone inbox type.")
    limit = max(1, min(int(limit), 500))
    with _LOCK:
        store = _read()
    keys = ("sms", "notifications", "location") if kind == "all" else (kind,)
    result = [dict(row, kind=key) for key in keys for row in store[key]]
    return sorted(result, key=lambda row: float(row.get("received_at", 0)), reverse=True)[:limit]


def clear_items(kind: str = "all") -> int:
    """Delete selected phone inbox data and return the number of removed records."""
    if kind not in ("all", "sms", "notifications", "location"):
        raise ValueError("Unknown phone inbox type.")
    keys = ("sms", "notifications", "location") if kind == "all" else (kind,)
    with _LOCK:
        store = _read()
        removed = sum(len(store[key]) for key in keys)
        for key in keys:
            store[key] = []
        _write(store)
    return removed


def enqueue(device_id: str, action: str) -> dict[str, Any]:
    """Queue a short-lived command for a paired phone companion."""
    if action not in ("ring", "locate"):
        raise ValueError("Phone command must be ring or locate.")
    command = {"id": uuid.uuid4().hex, "device_id": device_id, "action": action,
               "created_at": time.time(), "expires_at": time.time() + _COMMAND_TTL,
               "status": "pending"}
    with _LOCK:
        store = _read()
        store["commands"] = [c for c in store["commands"]
                              if c.get("status") == "pending" and c.get("expires_at", 0) > time.time()][-100:]
        store["commands"].append(command)
        _write(store)
    return {key: value for key, value in command.items() if key != "device_id"}


def poll(device_id: str) -> list[dict[str, Any]]:
    """Claim pending commands for this device; expired commands are discarded."""
    now = time.time()
    with _LOCK:
        store = _read()
        commands = store["commands"]
        ready = []
        for command in commands:
            if command.get("expires_at", 0) <= now:
                command["status"] = "expired"
            elif command.get("device_id") == device_id and command.get("status") == "pending":
                command["status"] = "sent"
                ready.append({key: command[key] for key in ("id", "action", "expires_at")})
        store["commands"] = [c for c in commands if c.get("expires_at", 0) > now][-100:]
        _write(store)
    return ready


def acknowledge(device_id: str, command_id: str, result: dict[str, Any]) -> bool:
    """Record the bounded result of a phone command if it belongs to this device."""
    safe = _normalise(result)
    with _LOCK:
        store = _read()
        for command in store["commands"]:
            if command.get("id") == command_id and command.get("device_id") == device_id:
                if command.get("status") not in ("sent", "pending"):
                    return False
                command["status"] = "done"
                command["result"] = safe
                command["completed_at"] = time.time()
                _write(store)
                return True
    return False
