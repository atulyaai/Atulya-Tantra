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
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Max entries in the in-memory ring buffer
MAX_DEVICES = 50


@dataclass(slots=True)
class Device:
    """One registered device (server, laptop, or phone agent)."""
    id: str  # unique device identifier
    type: str  # "server" | "laptop" | "phone"
    status: str  # "online" | "offline" | "needs_approval" | "unsupported"
    abilities: frozenset[str]  # capability IDs granted to this device
    last_seen: float = field(default_factory=time.monotonic)
    owner_id: str = "admin"


class DeviceRegistry:
    """Thread-safe device registry with persistent JSON backing."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._path = data_dir / "devices.json"
        self._buffer: dict[str, Device] = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        """Load existing devices from disk."""
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
                    last_seen=d.get("last_seen", time.monotonic()),
                    owner_id=d.get("owner_id", "admin"),
                )
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            logger.warning("Failed to load devices: %s", exc)

    def _save(self) -> None:
        """Persist all devices to disk."""
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps({did: asdict(d) for did, d in self._buffer.items()}, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Failed to save devices: %s", exc)

    def register(self, did: str, dtype: str, abilities: list[str] | None = None,
                 status: str = "online") -> Device:
        """Register or update a device."""
        with self._lock:
            device = Device(
                id=did,
                type=dtype,
                status=status,
                abilities=frozenset(abilities or []),
                last_seen=time.monotonic(),
                owner_id="admin",
            )
            self._buffer[did] = device
            self._save()
            logger.info("Registered device %s (%s)", did, dtype)
            return device

    def revoke(self, did: str) -> bool:
        """Revoke/unregister a device. Returns True if it existed."""
        with self._lock:
            if did in self._buffer:
                del self._buffer[did]
                self._save()
                logger.info("Revoked device %s", did)
                return True
            return False

    def update_status(self, did: str, status: str, abilities: list[str] | None = None) -> Device | None:
        """Update a device's status and/or abilities."""
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
        """Get a device by ID."""
        with self._lock:
            return self._buffer.get(did)

    def list_devices(self) -> list[Device]:
        """List all registered devices."""
        with self._lock:
            return list(self._buffer.values())

    def list_abilities(self, did: str) -> frozenset[str] | None:
        """List granted abilities for a device."""
        with self._lock:
            d = self._buffer.get(did)
            return d.abilities if d else None

    def recent(self, limit: int = 20) -> list[dict]:
        """Return recent device status entries."""
        with self._lock:
            entries = sorted(
                self._buffer.values(), key=lambda d: d.last_seen, reverse=True
            )[:limit]
            return [
                {
                    "id": d.id,
                    "type": d.type,
                    "status": d.status,
                    "abilities": sorted(d.abilities),
                    "last_seen": d.last_seen,
                }
                for d in entries
            ]


# Global instance — set by the server at startup
_DEVICE_REGISTRY: DeviceRegistry | None = None


def init_device_registry(data_dir: Path) -> DeviceRegistry:
    """Initialize the global device registry. Called once at server startup."""
    global _DEVICE_REGISTRY
    _DEVICE_REGISTRY = DeviceRegistry(data_dir)
    return _DEVICE_REGISTRY


def get_device_registry() -> DeviceRegistry | None:
    """Get the global device registry instance."""
    return _DEVICE_REGISTRY


def record_device_action(
    *,
    did: str,
    action: str,
    outcome: str,
    duration_ms: int = 0,
) -> None:
    """Record a device action in the global registry. No-op if not initialized."""
    if _DEVICE_REGISTRY is None:
        return
    _DEVICE_REGISTRY.update_status(did, "online")  # keep it alive


# Alias for backward compat in toolkit
register_device = init_device_registry
get_device = get_device_registry
list_devices = lambda: get_device_registry().list_devices() if get_device_registry() else []
list_abilities = lambda did: get_device_registry().list_abilities(did) if get_device_registry() else None


def asdict(obj: Any) -> dict:
    """Simple dataclass → dict for JSON serialization."""
    if hasattr(obj, "__dataclass_fields__"):
        return {f: getattr(obj, f) for f in obj.__dataclass_fields__}
    if isinstance(obj, dict):
        return {k: asdict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [asdict(v) for v in obj]
    return obj