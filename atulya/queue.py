"""Shared JSON storage and short-lived command queues for paired devices.

The paired-computer companion (companion), the paired-phone inbox (phone) and
the web-push subscriptions in channels each kept a private copy of the same
file-backed store; this is the one implementation they share.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from atulya import security

AGENT_DATA_DIR = "ATULYA_AGENT_DATA_DIR"
DEFAULT_AGENT_DATA_DIR = "data/agent"


def store_path(filename: str) -> Path:
    """Where a paired-device store lives; ATULYA_AGENT_DATA_DIR overrides it."""
    return Path(os.environ.get(AGENT_DATA_DIR, DEFAULT_AGENT_DATA_DIR)) / filename


def read_store(path: Path, default: dict[str, Any], invalid: str = "") -> dict[str, Any]:
    """Read a JSON object store, returning ``default`` while it does not exist.

    ``invalid`` names the error raised when the file holds a non-object.
    """
    try:
        value = json.loads(security.read_text(path))
    except FileNotFoundError:
        return default
    if not isinstance(value, dict):
        if invalid:
            raise ValueError(invalid)
        return default
    return value


def write_store(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    security.write_text(path, json.dumps(value, ensure_ascii=False, separators=(",", ":")))


class CommandQueue:
    """A device-scoped queue of short-lived commands in one JSON file."""

    def __init__(self, filename: str, *, ttl: float, limit: int,
                 pending_only: bool = False, invalid: str = ""):
        self.filename = filename
        self.ttl = ttl
        self.limit = limit
        self.pending_only = pending_only
        self.invalid = invalid
        self._lock = threading.RLock()

    @property
    def path(self) -> Path:
        return store_path(self.filename)

    @property
    def lock(self) -> threading.RLock:
        """The lock guarding this store; hold it across read-modify-write cycles."""
        return self._lock

    def read(self) -> dict[str, list[dict[str, Any]]]:
        store = read_store(self.path, {"commands": []}, invalid=self.invalid)
        store.setdefault("commands", [])
        return store

    def write(self, store: dict[str, list[dict[str, Any]]]) -> None:
        write_store(self.path, store)

    def update(self, mutate: Callable[[dict[str, Any]], Any]) -> Any:
        """Read, apply ``mutate(store)`` and write back, all under the queue lock."""
        with self._lock:
            store = self.read()
            result = mutate(store)
            self.write(store)
            return result

    def enqueue(self, device_id: str, **fields: Any) -> dict[str, Any]:
        now = time.time()
        command = {"id": uuid.uuid4().hex, "device_id": device_id,
                   "created_at": now, "expires_at": now + self.ttl,
                   "status": "pending", **fields}
        with self._lock:
            store = self.read()
            store["commands"] = self._prune(store["commands"], now)[-self.limit:]
            store["commands"].append(command)
            self.write(store)
        return command

    def poll(self, device_id: str, keep: tuple[str, ...]) -> list[dict[str, Any]]:
        """Claim this device's pending commands; expired commands are discarded."""
        now = time.time()
        with self._lock:
            store = self.read()
            commands = store["commands"]
            ready = []
            for row in commands:
                if row.get("expires_at", 0) <= now:
                    row["status"] = "expired"
                elif row.get("device_id") == device_id and row.get("status") == "pending":
                    row["status"] = "sent"
                    ready.append({key: row[key] for key in keep})
            kept = [row for row in commands if row.get("expires_at", 0) > now]
            if self.pending_only:
                kept = kept[-self.limit:]
            store["commands"] = kept
            self.write(store)
        return ready

    def _prune(self, commands: list[dict[str, Any]], now: float) -> list[dict[str, Any]]:
        if self.pending_only:
            return [row for row in commands
                    if row.get("status") == "pending" and row.get("expires_at", 0) > now]
        return [row for row in commands if row.get("expires_at", 0) > now]
