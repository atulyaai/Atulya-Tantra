"""Declarative HTTP driver: a device is described by a JSON profile, not by code.

A profile says how to recognise a device, and for each capability which HTTP request to send. Anything that is
controlled over HTTP (Roku, Tasmota, WLED, Shelly, Kodi, Hue-style bridges, many smart plugs and speakers) can be
added by writing a profile, and Atulya can draft one itself from a device's own answers (see ``learn``).

Profile shape::

    {"id": "tasmota", "label": "Tasmota switch", "kind": "switch", "port": 80, "scheme": "http",
     "detect": [{"path": "/cm?cmnd=Status", "contains": "StatusNET"}],
     "capabilities": {
        "power_on": {"description": "Turn on", "phrases": ["turn on"], "request": {"method": "GET", "path": "/cm?cmnd=Power%20On"}},
        "set_brightness": {"params": {"value": {"type": "integer", "min": 0, "max": 100}},
                           "request": {"method": "POST", "path": "/json/state", "json": {"bri": "{value}"}}}}}

Templates: ``{host}``, ``{port}`` and any parameter name. A JSON value that is exactly ``"{value}"`` keeps its type.
A request can only go to the device's own address: absolute URLs are refused.
"""
from __future__ import annotations

import json
import re
import urllib.parse
from pathlib import Path
from typing import Any

import httpx

from atulya.upakaran.base import Capability, DeviceError, DeviceRecord, Driver, coerce, is_lan_host

BUILTIN_DIR = Path(__file__).parent / "profiles"
_METHODS = {"GET", "POST", "PUT", "DELETE"}
_ID = re.compile(r"^[a-z0-9_]{1,40}$")
_TOKEN = re.compile(r"\{(\w+)\}")


def validate_profile(profile: Any) -> dict[str, Any]:
    """Raise DeviceError unless this is a safe, well-formed profile. Returns it unchanged."""
    if not isinstance(profile, dict):
        raise DeviceError("A profile must be a JSON object.")
    if not _ID.match(str(profile.get("id", ""))):
        raise DeviceError("Profile id must be lowercase letters, digits and underscores.")
    port = profile.get("port", 80)
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise DeviceError("Profile port is not valid.")
    if profile.get("scheme", "http") not in ("http", "https"):
        raise DeviceError("Profile scheme must be http or https.")
    caps = profile.get("capabilities")
    if not isinstance(caps, dict) or not caps or len(caps) > 80:
        raise DeviceError("A profile needs between 1 and 80 capabilities.")
    for name, cap in caps.items():
        if not _ID.match(name) or not isinstance(cap, dict):
            raise DeviceError(f"Capability “{name}” is not valid.")
        reqs = cap.get("requests") or ([cap["request"]] if "request" in cap else [])
        if not reqs or len(reqs) > 6:
            raise DeviceError(f"Capability “{name}” needs 1 to 6 requests.")
        declared = set(cap.get("params", {}))
        for req in reqs:
            path = str(req.get("path", ""))
            if str(req.get("method", "GET")).upper() not in _METHODS:
                raise DeviceError(f"Capability “{name}” uses an unsupported method.")
            if not path.startswith("/") or "://" in path or path.startswith("//") or ".." in path:
                raise DeviceError(f"Capability “{name}” must use a path on the device itself (starting with /).")
            used = set(_TOKEN.findall(path + json.dumps(req.get("json", ""))))
            if used - declared - {"host", "port"}:
                raise DeviceError(f"Capability “{name}” uses {sorted(used - declared - {'host', 'port'})} but does not declare it.")
    return profile


def load_profiles(extra_dirs: list[Path] | None = None) -> dict[str, dict[str, Any]]:
    """Built-in profiles plus any the user approved (kosh/devices/profiles). Bad files are skipped, never trusted."""
    profiles: dict[str, dict[str, Any]] = {}
    for folder in [BUILTIN_DIR, *(extra_dirs or [])]:
        for file in sorted(Path(folder).glob("*.json")) if Path(folder).exists() else []:
            try:
                profile = validate_profile(json.loads(file.read_text(encoding="utf-8")))
            except (OSError, ValueError, DeviceError):
                continue
            profiles[profile["id"]] = profile
    return profiles


def _fill(value: Any, params: dict[str, Any]) -> Any:
    if isinstance(value, str):
        whole = _TOKEN.fullmatch(value)
        if whole and whole.group(1) in params:
            return params[whole.group(1)]          # keeps numbers and booleans as they are
        return _TOKEN.sub(lambda m: str(params.get(m.group(1), m.group(0))), value)
    if isinstance(value, dict):
        return {k: _fill(v, params) for k, v in value.items()}
    if isinstance(value, list):
        return [_fill(v, params) for v in value]
    return value


def _quote_path(path: str, params: dict[str, Any]) -> str:
    """Fill {tokens} in a path, URL-encoding each value so a parameter can never add a new path or query."""
    return _TOKEN.sub(lambda m: urllib.parse.quote(str(params.get(m.group(1), m.group(0))), safe=""), path)


class ProfileDriver(Driver):
    id = "profile"

    def __init__(self, profiles: dict[str, dict[str, Any]] | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.profiles = profiles if profiles is not None else load_profiles()
        self._transport = transport

    def _profile(self, device: DeviceRecord) -> dict[str, Any]:
        profile = self.profiles.get(str(device.config.get("profile")))
        if profile is None:
            raise DeviceError(f"I don't have a profile called “{device.config.get('profile')}”.")
        return profile

    async def capabilities(self, device: DeviceRecord) -> list[Capability]:
        profile = self._profile(device)
        return [Capability(name=n, description=c.get("description", n.replace("_", " ")), phrases=list(c.get("phrases", [])),
                           params=dict(c.get("params", {})), risky=bool(c.get("risky")), repeat=bool(c.get("repeat")))
                for n, c in profile["capabilities"].items()]

    async def execute(self, device: DeviceRecord, capability: str, args: dict[str, Any]) -> str:
        profile = self._profile(device)
        cap = profile["capabilities"].get(capability)
        if cap is None:
            raise DeviceError(f"{device.name} can't “{capability.replace('_', ' ')}”.")
        host = device.address
        if not is_lan_host(host):
            raise DeviceError(f"{host} is not on your home network, so I won't send it commands.")
        params = {k: coerce(args.get(k, spec.get("default")), spec, k) for k, spec in cap.get("params", {}).items()
                  if args.get(k, spec.get("default")) is not None}
        missing = [k for k, spec in cap.get("params", {}).items() if k not in params and "default" not in spec]
        if missing:
            raise DeviceError(f"I need {', '.join(missing)} for that.")
        port = int(device.config.get("port") or profile.get("port", 80))
        base = f"{profile.get('scheme', 'http')}://{host}:{port}"
        reqs = cap.get("requests") or [cap["request"]]
        times = max(1, min(int(args.get("times") or 1), 20)) if cap.get("repeat") else 1
        verify = bool(device.config.get("verify_tls", False))
        try:
            async with httpx.AsyncClient(timeout=float(profile.get("timeout", 5)), transport=self._transport,
                                         verify=verify, follow_redirects=False) as client:
                for _ in range(times):
                    for req in reqs:
                        path = _quote_path(str(req["path"]), {**params, "host": host, "port": port})
                        body = _fill(req.get("json"), params) if "json" in req else None
                        headers = {str(k): str(v) for k, v in (req.get("headers") or {}).items()}
                        resp = await client.request(str(req.get("method", "GET")).upper(), base + path, json=body, headers=headers)
                        if resp.status_code >= 400:
                            raise DeviceError(f"{device.name} answered {resp.status_code}.")
        except httpx.HTTPError as exc:
            raise DeviceError(f"I couldn't reach {device.name} at {host}: {type(exc).__name__}.") from exc
        return cap.get("say", f"Done: {capability.replace('_', ' ')} on {device.name}.")

    async def state(self, device: DeviceRecord) -> dict[str, Any]:
        profile = self._profile(device)
        req = profile.get("state")
        if not req:
            return {}
        port = int(device.config.get("port") or profile.get("port", 80))
        try:
            async with httpx.AsyncClient(timeout=3.0, transport=self._transport, verify=False) as client:
                resp = await client.get(f"{profile.get('scheme', 'http')}://{device.address}:{port}{req['path']}")
            return {"online": resp.status_code < 400, "raw": resp.text[:300]}
        except httpx.HTTPError:
            return {"online": False}
