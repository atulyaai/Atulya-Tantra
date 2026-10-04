"""Android Debug Bridge: control any Android phone, tablet, Android TV or Fire TV over the network.

Needs the ``adb`` tool (Android platform-tools) and, on the device, Developer options > Wireless debugging (phone) or
Network debugging (TV / Fire TV). No raw shell is exposed: only the fixed actions below, with every argument checked.
There is no way to "ring" a phone with ADB; that needs a companion app.
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any

from atulya.devices.base import Capability, DeviceError, DeviceRecord, Driver, is_lan_host

KEYS = {"home": 3, "back": 4, "power": 26, "volume_up": 24, "volume_down": 25, "mute": 164, "play_pause": 85, "next": 87,
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
        caps = [Capability(k, k.replace("_", " "), _PHRASES.get(k, []), repeat=k in ("volume_up", "volume_down")) for k in KEYS]
        caps += [
            Capability("launch_app", "Open an app by name (YouTube, Netflix, Spotify …)", ["open", "launch", "start"], {"app": {"type": "string"}}),
            Capability("open_url", "Open a web link on the device", ["open link"], {"url": {"type": "string", "max_length": 500}}),
            Capability("battery", "Battery level", ["battery"]),
            Capability("screenshot", "Take a screenshot and save it", ["screenshot", "screen shot"]),
            Capability("type_text", "Type text on the device", ["type"], {"text": {"type": "string", "max_length": 120}}, risky=True),
        ]
        return caps

    async def execute(self, device: DeviceRecord, capability: str, args: dict[str, Any]) -> str:
        if capability in KEYS:
            times = max(1, min(int(args.get("times") or 1), 20)) if capability.startswith("volume") else 1
            for _ in range(times):
                await self._shell(device, "input", "keyevent", str(KEYS[capability]))
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
