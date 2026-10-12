"""Device registry: track server, laptop, and phone agents with status and granted abilities.

Each device has:
- type: "server" | "laptop" | "phone"
- status: "online" | "offline" | "needs_approval" | "unsupported"
- abilities: frozenset of capability IDs granted to this device
- last_seen: timestamp
- owner_id: the user who owns this device

The registry is the single source of truth for what each device can do.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MAX_DEVICES = 50


@dataclass(slots=True)
class Device:
    """One registered device (server, laptop, or phone agent)."""
    id: str
    type: str  # "server" | "laptop" | "phone"
    status: str  # "online" | "offline" | "needs_approval" | "unsupported"
    abilities: frozenset[str]
    last_seen: float = field(default_factory=time.monotonic)
    owner_id: str = "admin"


def _device_to_dict(d: Device) -> dict:
    return {
        "id": d.id,
        "type": d.type,
        "status": d.status,
        "abilities": sorted(d.abilities),
        "last_seen": d.last_seen,
        "owner_id": d.owner_id,
    }


class DeviceRegistry:
    """Thread-safe device registry with persistent JSON backing."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._path = data_dir / "devices.json"
        self._buffer: dict[str, Device] = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for did, d in data.items():
                self._buffer[did] = Device(
                    id=did,
                    type=d.get("type", "unknown"),
                    status=d.get("status", "offline"),
                    abilities=frozenset(d.get("abilities", [])),
                    last_seen=float(d.get("last_seen", time.monotonic())),
                    owner_id=d.get("owner_id", "admin"),
                )
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Failed to load devices: %s", exc)

    def _save(self) -> None:
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            payload = {did: _device_to_dict(d) for did, d in self._buffer.items()}
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to save devices: %s", exc)

    def register(self, did: str, dtype: str, abilities: list[str] | None = None,
                 status: str = "online", owner_id: str = "admin") -> Device:
        with self._lock:
            device = Device(
                id=did,
                type=dtype,
                status=status,
                abilities=frozenset(abilities or []),
                last_seen=time.monotonic(),
                owner_id=owner_id,
            )
            self._buffer[did] = device
            self._save()
            logger.info("Registered device %s (%s)", did, dtype)
            return device

    def revoke(self, did: str) -> bool:
        with self._lock:
            if did in self._buffer:
                del self._buffer[did]
                self._save()
                logger.info("Revoked device %s", did)
                return True
            return False

    def update_status(self, did: str, status: str, abilities: list[str] | None = None) -> Device | None:
        with self._lock:
            if did not in self._buffer:
                return None
            device = self._buffer[did]
            device.status = status
            if abilities is not None:
                device.abilities = frozenset(abilities)
            device.last_seen = time.monotonic()
            self._save()
            return device

    def get(self, did: str) -> Device | None:
        with self._lock:
            return self._buffer.get(did)

    def list_devices(self) -> list[Device]:
        with self._lock:
            return list(self._buffer.values())

    def list_abilities(self, did: str) -> frozenset[str] | None:
        with self._lock:
            d = self._buffer.get(did)
            return d.abilities if d else None

    def recent(self, limit: int = 20) -> list[dict]:
        with self._lock:
            entries = sorted(self._buffer.values(), key=lambda d: d.last_seen, reverse=True)[:limit]
            return [_device_to_dict(d) for d in entries]


_DEVICE_REGISTRY: DeviceRegistry | None = None


def init_device_registry(data_dir: Path) -> DeviceRegistry:
    global _DEVICE_REGISTRY
    _DEVICE_REGISTRY = DeviceRegistry(data_dir)
    return _DEVICE_REGISTRY


def get_device_registry() -> DeviceRegistry | None:
    return _DEVICE_REGISTRY


def record_device_action(*, did: str, action: str, outcome: str, duration_ms: int = 0) -> None:
    if _DEVICE_REGISTRY is None:
        return
    _DEVICE_REGISTRY.update_status(did, "online")


def list_devices():
    reg = get_device_registry()
    return reg.list_devices() if reg else []


def list_abilities(did: str):
    reg = get_device_registry()
    return reg.list_abilities(did) if reg else None
