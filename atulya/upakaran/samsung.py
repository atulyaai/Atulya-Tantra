"""Samsung Smart TVs (Tizen, 2016 and newer; many 2014-2015 models too) over their built-in remote-control websocket.

Nothing to install on the TV. The first command makes the TV show "Allow Atulya?" on screen; after you accept, it
hands back a token that is stored with the device, so later commands need no prompt. A TV that is fully off cannot
hear this: pair it with a Wake-on-LAN device for "turn on". Old plasma sets without Smart Hub have no network
control at all (they need an infrared blaster).
"""
from __future__ import annotations

import asyncio
import base64
import json
import re
import ssl
from typing import Any

from atulya.upakaran.base import Capability, DeviceError, DeviceRecord, Driver, is_lan_host

_KEY = re.compile(r"^KEY_[A-Z0-9_]{1,24}$")
NAME = "Atulya"

# capability -> (Samsung key, phrases, repeats)
KEYS: dict[str, tuple[str, list[str], bool]] = {
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
                for n, (key, phrases, rep) in KEYS.items()]
        caps.append(Capability("send_key", "Press any remote key, e.g. KEY_HDMI", params={"key": {"type": "string", "max_length": 28}}))
        return caps

    def _url(self, device: DeviceRecord) -> tuple[str, ssl.SSLContext | None]:
        if not is_lan_host(device.address):
            raise DeviceError(f"{device.address} is not on your home network, so I won't connect to it.")
        port = int(device.config.get("port") or 8002)
        tls = bool(device.config.get("tls", port == 8002))
        name = base64.b64encode(NAME.encode()).decode()
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
        elif capability in KEYS:
            key = KEYS[capability][0]
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
                    raise DeviceError(f"{device.name} refused. On the TV, allow “{NAME}” (Settings > General > External Device Manager > Device Connection Manager).")
        except asyncio.TimeoutError as exc:
            raise DeviceError(f"{device.name} didn't answer. If a message appeared on the TV, choose Allow, then ask again.") from exc
