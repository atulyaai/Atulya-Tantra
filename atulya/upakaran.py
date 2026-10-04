"""The device fabric: one way to describe and drive anything that can be controlled.

A *device* has a *driver* (how to talk to it) and *capabilities* (what it can do, in plain words). Atulya never
needs to know brands: it lists capabilities, picks one, and the driver does it. New devices are added by data
(a JSON profile) wherever possible, not by new code."""
from __future__ import annotations

import asyncio
import base64
import ipaddress
import json
import os
import re
import shutil
import socket
import ssl
import tempfile
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

# ── upakaran ────────────────────────────────────────────────────────────



# ── base ────────────────────────────────────────────────────────────
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


# ── adb ────────────────────────────────────────────────────────────
ADB_KEYS = {"home": 3, "back": 4, "power": 26, "volume_up": 24, "volume_down": 25, "mute": 164, "play_pause": 85, "next": 87,
        "previous": 88, "up": 19, "down": 20, "left": 21, "right": 22, "select": 66, "menu": 82, "wake": 224, "sleep": 223,
        "recent_apps": 187}
_PHRASES = {"home": ["go home", "home screen"], "back": ["go back"], "volume_up": ["volume up", "louder"], "volume_down": ["volume down", "quieter"],
            "mute": ["mute", "unmute"], "play_pause": ["play", "pause", "resume"], "next": ["next", "skip"], "previous": ["previous", "back track"],
            "wake": ["wake up", "turn on", "switch on"], "sleep": ["turn off", "switch off", "sleep", "lock the screen"], "select": ["select", "press ok"]}
_PKG = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$")
_TEXT = re.compile(r"^[A-Za-z0-9 .,@_\-!?:'/]{1,120}$")


def adb_path() -> str | None:
    return os.environ.get("ATULYA_ADB") or shutil.which("adb")


async def run_adb(*args: str, timeout: float = 15.0, binary: bool = False) -> bytes | str:
    exe = adb_path()
    if not exe:
        raise DeviceError("The adb tool isn't installed. Install Android platform-tools and make sure `adb` is on your PATH.")
    proc = await asyncio.create_subprocess_exec(exe, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError as exc:
        proc.kill()
        raise DeviceError("The device didn't answer in time.") from exc
    if proc.returncode != 0:
        raise DeviceError((err or out).decode(errors="replace").strip()[:200] or "adb failed.")
    return out if binary else out.decode(errors="replace")


class AdbDriver(Driver):
    id = "adb"

    def serial(self, device: DeviceRecord) -> str:
        if device.config.get("serial"):
            return str(device.config["serial"])
        if not is_lan_host(device.address):
            raise DeviceError(f"{device.address} is not on your home network, so I won't connect to it.")
        return f"{device.address}:{int(device.config.get('port') or 5555)}"

    async def _shell(self, device: DeviceRecord, *args: str, **kw: Any) -> str:
        serial = self.serial(device)
        if ":" in serial:
            await run_adb("connect", serial)
        return await run_adb("-s", serial, "shell", *args, **kw)  # type: ignore[return-value]

    async def capabilities(self, device: DeviceRecord) -> list[Capability]:
        caps = [Capability(k, k.replace("_", " "), _PHRASES.get(k, []), repeat=k in ("volume_up", "volume_down")) for k in ADB_KEYS]
        caps += [
            Capability("launch_app", "Open an app by name (YouTube, Netflix, Spotify …)", ["open", "launch", "start"], {"app": {"type": "string"}}),
            Capability("open_url", "Open a web link on the device", ["open link"], {"url": {"type": "string", "max_length": 500}}),
            Capability("battery", "Battery level", ["battery"]),
            Capability("screenshot", "Take a screenshot and save it", ["screenshot", "screen shot"]),
            Capability("type_text", "Type text on the device", ["type"], {"text": {"type": "string", "max_length": 120}}, risky=True),
        ]
        return caps

    async def execute(self, device: DeviceRecord, capability: str, args: dict[str, Any]) -> str:
        if capability in ADB_KEYS:
            times = max(1, min(int(args.get("times") or 1), 20)) if capability.startswith("volume") else 1
            for _ in range(times):
                await self._shell(device, "input", "keyevent", str(ADB_KEYS[capability]))
            return f"Done: {capability.replace('_', ' ')} on {device.name}."
        if capability == "launch_app":
            return await self._launch(device, str(args.get("app", "")))
        if capability == "open_url":
            url = str(args.get("url", ""))
            if urllib.parse.urlparse(url).scheme not in ("http", "https") or not re.fullmatch(r"[^\s'\"`;|&$<>\\]+", url):
                raise DeviceError("I can only open plain http or https links.")
            await self._shell(device, "am", "start", "-a", "android.intent.action.VIEW", "-d", url)
            return f"Opened the link on {device.name}."
        if capability == "battery":
            m = re.search(r"level:\s*(\d+)", await self._shell(device, "dumpsys", "battery"))
            return f"{device.name} battery is at {m.group(1)}%." if m else f"I couldn't read {device.name}'s battery."
        if capability == "screenshot":
            serial = self.serial(device)
            data = await run_adb("-s", serial, "exec-out", "screencap", "-p", binary=True)
            path = Path(tempfile.gettempdir()) / f"atulya-{device.id}.png"
            path.write_bytes(data)  # type: ignore[arg-type]
            return f"Saved a screenshot of {device.name} to {path}."
        if capability == "type_text":
            text = str(args.get("text", ""))
            if not _TEXT.match(text):
                raise DeviceError("I can only type simple text (letters, numbers and basic punctuation).")
            await self._shell(device, "input", "text", text.replace(" ", "%s"))
            return f"Typed it on {device.name}."
        raise DeviceError(f"{device.name} can't “{capability.replace('_', ' ')}”.")

    async def _launch(self, device: DeviceRecord, name: str) -> str:
        name = name.strip().lower()
        if not name:
            raise DeviceError("Which app should I open?")
        if _PKG.match(name):                   # already a package id
            package = name
        else:
            listing = await self._shell(device, "pm", "list", "packages", "-3")
            squashed = re.sub(r"[^a-z0-9]", "", name)
            found = [p.split(":", 1)[1].strip() for p in listing.splitlines() if p.startswith("package:")]
            matches = [p for p in found if squashed and squashed in re.sub(r"[^a-z0-9]", "", p.lower())]
            if not matches:
                raise DeviceError(f"I couldn't find an app called “{name}” on {device.name}.")
            package = sorted(matches, key=len)[0]
        await self._shell(device, "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")
        return f"Opened {name} on {device.name}."


# ── wol ────────────────────────────────────────────────────────────
_MAC = re.compile(r"^([0-9a-f]{2}[:-]){5}[0-9a-f]{2}$", re.I)


def magic_packet(mac: str) -> bytes:
    if not _MAC.match(mac or ""):
        raise DeviceError("That MAC address doesn't look right. It should be like AA:BB:CC:DD:EE:FF.")
    raw = bytes.fromhex(re.sub(r"[:-]", "", mac))
    return b"\xff" * 6 + raw * 16


class WolDriver(Driver):
    id = "wol"

    async def capabilities(self, device: DeviceRecord) -> list[Capability]:
        return [Capability("power_on", "Wake it up over the network", ["turn on", "switch on", "wake", "wake up", "power on"])]

    async def execute(self, device: DeviceRecord, capability: str, args: dict[str, Any]) -> str:
        if capability != "power_on":
            raise DeviceError(f"{device.name} can only be switched on this way.")
        packet = magic_packet(str(device.config.get("mac", "")))
        target = str(device.config.get("broadcast") or "255.255.255.255")
        if target != "255.255.255.255" and not is_lan_host(target):
            raise DeviceError("The broadcast address must be on your home network.")
        port = int(device.config.get("wol_port") or 9)

        def send() -> None:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                for _ in range(3):  # UDP can drop; three is the usual habit
                    s.sendto(packet, (target, port))
        try:
            await asyncio.to_thread(send)
        except OSError as exc:
            raise DeviceError(f"I couldn't send the wake signal: {exc}") from exc
        return f"Sent the wake signal to {device.name}. It can take a few seconds."


# ── samsung ────────────────────────────────────────────────────────────
_KEY = re.compile(r"^KEY_[A-Z0-9_]{1,24}$")
SAMSUNG_REMOTE_NAME = "Atulya"

# capability -> (Samsung key, phrases, repeats)
SAMSUNG_KEYS: dict[str, tuple[str, list[str], bool]] = {
    "power_off": ("KEY_POWER", ["turn off", "switch off", "power off", "sleep"], False),
    "volume_up": ("KEY_VOLUP", ["volume up", "louder"], True),
    "volume_down": ("KEY_VOLDOWN", ["volume down", "quieter"], True),
    "mute": ("KEY_MUTE", ["mute", "unmute"], False),
    "channel_up": ("KEY_CHUP", ["next channel", "channel up"], True),
    "channel_down": ("KEY_CHDOWN", ["previous channel", "channel down"], True),
    "home": ("KEY_HOME", ["go home", "home screen", "smart hub"], False),
    "back": ("KEY_RETURN", ["go back", "back"], False),
    "source": ("KEY_SOURCE", ["change source", "source", "input"], False),
    "menu": ("KEY_MENU", ["menu"], False),
    "up": ("KEY_UP", ["up"], True),
    "down": ("KEY_DOWN", ["down"], True),
    "left": ("KEY_LEFT", ["left"], True),
    "right": ("KEY_RIGHT", ["right"], True),
    "select": ("KEY_ENTER", ["select", "press ok", "ok"], False),
    "play": ("KEY_PLAY", ["play", "resume"], False),
    "pause": ("KEY_PAUSE", ["pause"], False),
}


class SamsungDriver(Driver):
    id = "samsung"

    async def capabilities(self, device: DeviceRecord) -> list[Capability]:
        caps = [Capability(n, f"Press {key[4:].title().replace('_', ' ')} on the remote", phrases, repeat=rep)
                for n, (key, phrases, rep) in SAMSUNG_KEYS.items()]
        caps.append(Capability("send_key", "Press any remote key, e.g. KEY_HDMI", params={"key": {"type": "string", "max_length": 28}}))
        return caps

    def _url(self, device: DeviceRecord) -> tuple[str, ssl.SSLContext | None]:
        if not is_lan_host(device.address):
            raise DeviceError(f"{device.address} is not on your home network, so I won't connect to it.")
        port = int(device.config.get("port") or 8002)
        tls = bool(device.config.get("tls", port == 8002))
        name = base64.b64encode(SAMSUNG_REMOTE_NAME.encode()).decode()
        token = device.config.get("token")
        url = f"{'wss' if tls else 'ws'}://{device.address}:{port}/api/v2/channels/samsung.remote.control?name={name}"
        if token:
            url += f"&token={token}"
        ctx = None
        if tls:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE        # the TV's certificate is self-signed; it is on your own network
        return url, ctx

    async def execute(self, device: DeviceRecord, capability: str, args: dict[str, Any]) -> str:
        if capability == "send_key":
            key = str(args.get("key", "")).upper()
            if not _KEY.match(key):
                raise DeviceError("That isn't a remote key name. They look like KEY_HDMI or KEY_VOLUP.")
        elif capability in SAMSUNG_KEYS:
            key = SAMSUNG_KEYS[capability][0]
        else:
            raise DeviceError(f"{device.name} can't “{capability}”.")
        times = max(1, min(int(float(args.get("times") or 1)), 20)) if capability != "send_key" else 1
        await self._press(device, key, times)
        return f"Done: {capability.replace('_', ' ')} on {device.name}." + (f" ({times} times)" if times > 1 else "")

    async def _press(self, device: DeviceRecord, key: str, times: int) -> None:
        import websockets

        url, ctx = self._url(device)
        try:
            async with websockets.connect(url, ssl=ctx, open_timeout=6, max_size=2**20) as ws:
                await self._wait_connected(ws, device)
                for _ in range(times):
                    await ws.send(json.dumps({"method": "ms.remote.control", "params": {
                        "Cmd": "Click", "DataOfCmd": key, "Option": "false", "TypeOfRemote": "SendRemoteKey"}}))
                    await asyncio.sleep(0.12 if times > 1 else 0)
        except DeviceError:
            raise
        except (OSError, asyncio.TimeoutError, websockets.WebSocketException) as exc:
            raise DeviceError(f"I couldn't reach {device.name}. Is the TV on and on the same Wi-Fi? ({type(exc).__name__})") from exc

    async def _wait_connected(self, ws: Any, device: DeviceRecord) -> None:
        # First time the TV waits for you to press Allow on screen, so give it time.
        wait = 30 if not device.config.get("token") else 8
        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), wait)
                msg = json.loads(raw) if isinstance(raw, (str, bytes)) else {}
                event = msg.get("event", "")
                if event == "ms.channel.connect":
                    token = (msg.get("data") or {}).get("token")
                    if token and token != device.config.get("token"):
                        device.config["token"] = str(token)     # kept by the hub, so the TV never asks again
                    return
                if event in ("ms.channel.unauthorized", "ms.error"):
                    raise DeviceError(f"{device.name} refused. On the TV, allow “{SAMSUNG_REMOTE_NAME}” (Settings > General > External Device Manager > Device Connection Manager).")
        except asyncio.TimeoutError as exc:
            raise DeviceError(f"{device.name} didn't answer. If a message appeared on the TV, choose Allow, then ask again.") from exc


# ── ha ────────────────────────────────────────────────────────────
# Home Assistant's own service names per domain: (capability, service, phrases, params, data builder)
_ONOFF = [("power_on", "turn_on", ["turn on", "switch on"]), ("power_off", "turn_off", ["turn off", "switch off"]), ("toggle", "toggle", ["toggle"])]
_DOMAINS: dict[str, list[tuple[str, str, list[str], dict[str, Any], str]]] = {
    "light": [(*c, {}, "") for c in _ONOFF] + [("set_brightness", "turn_on", ["brightness", "dim"], {"value": {"type": "integer", "min": 0, "max": 100}}, "brightness_pct")],
    "switch": [(*c, {}, "") for c in _ONOFF],
    "fan": [(*c, {}, "") for c in _ONOFF],
    "input_boolean": [(*c, {}, "") for c in _ONOFF],
    "media_player": [(*c, {}, "") for c in _ONOFF[:2]] + [
        ("volume_up", "volume_up", ["volume up", "louder"], {}, ""), ("volume_down", "volume_down", ["volume down", "quieter"], {}, ""),
        ("play_pause", "media_play_pause", ["play", "pause", "resume"], {}, ""), ("next", "media_next_track", ["next", "skip"], {}, ""),
        ("previous", "media_previous_track", ["previous"], {}, ""),
        ("set_volume", "volume_set", ["volume"], {"value": {"type": "integer", "min": 0, "max": 100}}, "volume_level"),
        ("select_source", "select_source", ["switch to", "change source", "input"], {"value": {"type": "string"}}, "source")],
    "climate": [(*c, {}, "") for c in _ONOFF[:2]] + [("set_temperature", "set_temperature", ["temperature", "set to"], {"value": {"type": "number", "min": 5, "max": 40}}, "temperature")],
    "cover": [("open", "open_cover", ["open"], {}, ""), ("close", "close_cover", ["close"], {}, ""), ("stop", "stop_cover", ["stop"], {}, "")],
    "lock": [("lock", "lock", ["lock"], {}, ""), ("unlock", "unlock", ["unlock"], {}, "")],
    "scene": [("activate", "turn_on", ["activate", "run", "start"], {}, "")],
    "script": [("run", "turn_on", ["run", "start"], {}, "")],
    "button": [("press", "press", ["press"], {}, "")],
    "vacuum": [("start", "start", ["start", "clean"], {}, ""), ("stop", "stop", ["stop"], {}, ""), ("return_home", "return_to_base", ["go home", "dock"], {}, "")],
}
KIND = {"light": "light", "switch": "switch", "fan": "fan", "media_player": "tv", "climate": "thermostat", "cover": "cover", "lock": "lock",
        "scene": "scene", "script": "script", "button": "button", "vacuum": "vacuum", "input_boolean": "switch"}


class HomeAssistantDriver(Driver):
    id = "homeassistant"

    def __init__(self, url: str | None = None, token: str | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.url = (url if url is not None else os.environ.get("HOME_ASSISTANT_URL", "")).rstrip("/")
        self.token = token if token is not None else os.environ.get("HOME_ASSISTANT_TOKEN", "")
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.url and self.token)

    def _client(self) -> httpx.AsyncClient:
        if not self.configured:
            raise DeviceError("Home Assistant isn't set up. Add HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN to .env.")
        host = httpx.URL(self.url).host
        if not is_lan_host(host):
            raise DeviceError("Home Assistant must be on your home network.")
        return httpx.AsyncClient(base_url=self.url, headers={"Authorization": f"Bearer {self.token}"}, timeout=10.0, transport=self._transport)

    async def entities(self) -> list[dict[str, Any]]:
        try:
            async with self._client() as client:
                resp = await client.get("/api/states")
            if resp.status_code == 401:
                raise DeviceError("Home Assistant refused the token. Make a new long-lived token and update .env.")
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise DeviceError(f"I couldn't reach Home Assistant: {type(exc).__name__}.") from exc
        return [{"entity": s["entity_id"], "name": (s.get("attributes") or {}).get("friendly_name") or s["entity_id"],
                 "domain": s["entity_id"].split(".", 1)[0], "state": s.get("state")}
                for s in resp.json() if s["entity_id"].split(".", 1)[0] in _DOMAINS]

    async def capabilities(self, device: DeviceRecord) -> list[Capability]:
        domain = str(device.config.get("entity", "")).split(".", 1)[0]
        return [Capability(name, name.replace("_", " "), phrases, params, risky=(name == "unlock"))
                for name, _svc, phrases, params, _key in _DOMAINS.get(domain, [])]

    async def execute(self, device: DeviceRecord, capability: str, args: dict[str, Any]) -> str:
        entity = str(device.config.get("entity", ""))
        domain = entity.split(".", 1)[0]
        row = next((r for r in _DOMAINS.get(domain, []) if r[0] == capability), None)
        if row is None:
            raise DeviceError(f"{device.name} can't “{capability.replace('_', ' ')}”.")
        _name, service, _phrases, params, key = row
        data: dict[str, Any] = {"entity_id": entity}
        for pname, spec in params.items():
            if args.get(pname) is None:
                raise DeviceError(f"I need {pname} for that.")
            value = coerce(args[pname], spec, pname)
            data[key] = value / 100 if key == "volume_level" else value
        try:
            async with self._client() as client:
                resp = await client.post(f"/api/services/{domain}/{service}", json=data)
            if resp.status_code == 401:
                raise DeviceError("Home Assistant refused the token.")
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise DeviceError(f"Home Assistant couldn't do that: {type(exc).__name__}.") from exc
        return f"Done: {capability.replace('_', ' ')} on {device.name}."

    async def state(self, device: DeviceRecord) -> dict[str, Any]:
        try:
            async with self._client() as client:
                resp = await client.get(f"/api/states/{device.config.get('entity')}")
            return {"online": resp.status_code == 200, "state": resp.json().get("state") if resp.status_code == 200 else None}
        except (httpx.HTTPError, DeviceError):
            return {"online": False}


# ── profile_driver ────────────────────────────────────────────────────────────
BUILTIN_FILE = Path(__file__).resolve().parent / "upakaran_profiles.json"   # the built-in profiles, as one list
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


def builtin_profiles() -> dict[str, dict[str, Any]]:
    try:
        listed = json.loads(BUILTIN_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for item in listed:
        try:
            out[item["id"]] = validate_profile(item)
        except (KeyError, TypeError, DeviceError):
            continue
    return out


def load_profiles(extra_dirs: list[Path] | None = None) -> dict[str, dict[str, Any]]:
    """Built-in profiles plus any the user approved (kosh/devices/profiles). Bad files are skipped, never trusted."""
    profiles = builtin_profiles()
    for folder in extra_dirs or []:
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

