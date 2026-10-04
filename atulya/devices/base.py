"""The device fabric: one way to describe and drive anything that can be controlled.

A *device* has a *driver* (how to talk to it) and *capabilities* (what it can do, in plain words). Atulya never
needs to know brands: it lists capabilities, picks one, and the driver does it. New devices are added by data
(a JSON profile) wherever possible, not by new code.
"""
from __future__ import annotations

import ipaddress
import os
import socket
from dataclasses import dataclass, field
from typing import Any


class DeviceError(RuntimeError):
    """A device could not be reached or refused a command. The message is meant to be said to the user."""


@dataclass
class Capability:
    name: str                                   # "power_off", "volume_up", "launch_app"
    description: str = ""
    phrases: list[str] = field(default_factory=list)   # how people say it: "turn off", "louder"
    params: dict[str, dict[str, Any]] = field(default_factory=dict)   # {"app": {"type": "string"}}
    risky: bool = False                         # asks first (unlock, restart, reset …)
    repeat: bool = False                        # "volume up 5" repeats it


@dataclass
class DeviceRecord:
    id: str
    name: str
    kind: str                                   # tv, phone, light, speaker, pc, switch, hub …
    driver: str                                 # "profile", "adb", "wol", "homeassistant"
    address: str = ""                           # host or IP
    config: dict[str, Any] = field(default_factory=dict)   # driver settings: profile id, port, mac, entity …
    aliases: list[str] = field(default_factory=list)
    room: str = ""
    capabilities: list[Capability] = field(default_factory=list)   # filled from the driver when added

    def cap(self, name: str) -> Capability | None:
        return next((c for c in self.capabilities if c.name == name), None)


# ── network safety ─────────────────────────────────────────────────────────────────────────────
def is_lan_host(host: str, allow_loopback: bool | None = None) -> bool:
    """Devices must be on your own network: private addresses, link-local, .local names (and loopback for tests).

    This stops a profile or a spoken request from steering Atulya at a public server."""
    if allow_loopback is None:
        allow_loopback = os.environ.get("ATULYA_DEVICES_ALLOW_LOOPBACK", "") in ("1", "on", "true")
    host = (host or "").strip().lower()
    if not host:
        return False
    if os.environ.get("ATULYA_DEVICES_ALLOW_PUBLIC", "") in ("1", "on", "true"):
        return True
    if host.endswith(".local") or (host == "localhost" and allow_loopback):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        try:  # a plain hostname: accept only if it resolves to private addresses
            ip = ipaddress.ip_address(socket.gethostbyname(host))
        except (OSError, ValueError):
            return False
    if ip.is_loopback:
        return allow_loopback
    return ip.is_private or ip.is_link_local


class Driver:
    """How to talk to one kind of device. Drivers are small; the variety lives in profile data."""

    id = "base"

    async def capabilities(self, device: DeviceRecord) -> list[Capability]:
        raise NotImplementedError

    async def execute(self, device: DeviceRecord, capability: str, args: dict[str, Any]) -> str:
        raise NotImplementedError

    async def state(self, device: DeviceRecord) -> dict[str, Any]:
        return {}


def coerce(value: Any, spec: dict[str, Any], name: str) -> Any:
    """Check a parameter against its declared type and range."""
    kind = spec.get("type", "string")
    try:
        if kind == "integer":
            value = int(float(value))
        elif kind == "number":
            value = float(value)
        elif kind == "boolean":
            value = value if isinstance(value, bool) else str(value).strip().lower() in ("1", "true", "yes", "on")
        else:
            value = str(value)
    except (TypeError, ValueError) as exc:
        raise DeviceError(f"“{name}” should be a {kind}.") from exc
    if kind in ("integer", "number"):
        if "min" in spec and value < spec["min"] or "max" in spec and value > spec["max"]:
            raise DeviceError(f"“{name}” must be between {spec.get('min', '-∞')} and {spec.get('max', '∞')}.")
    if kind == "string" and len(value) > int(spec.get("max_length", 200)):
        raise DeviceError(f"“{name}” is too long.")
    return value
