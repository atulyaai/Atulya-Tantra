"""The device hub: your devices, how to drive them, and how to understand "turn the TV down a bit".

Nothing here knows about brands. Devices carry their own capabilities (from their driver or profile), and
``resolve`` matches words to those capabilities, so a new device that brings a profile is understood immediately.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from atulya.raksha import vault
from atulya.upakaran.adb import AdbDriver
from atulya.upakaran.base import Capability, DeviceError, DeviceRecord, Driver
from atulya.upakaran.discovery import Candidate
from atulya.upakaran.ha import HomeAssistantDriver
from atulya.upakaran.profile_driver import ProfileDriver, load_profiles
from atulya.upakaran.samsung import SamsungDriver
from atulya.upakaran.wol import WolDriver

_NUM = re.compile(r"\b(\d{1,3})\b")
_FILLER = {"the", "a", "my", "please", "to", "it", "now", "on", "in", "up", "down", "off", "of", "and", "for", "turn", "switch", "set",
           "can", "you", "could", "just", "hey", "atulya", "make", "get", "me", "bit", "little", "times", "time", "by", "at", "percent", "%", "is", "this", "that"}
_KIND_WORDS = {"tv": ("tv", "television", "telly"), "phone": ("phone", "mobile"), "light": ("light", "lamp", "lights", "bulb"),
               "speaker": ("speaker",), "pc": ("pc", "computer", "laptop"), "fan": ("fan",), "thermostat": ("ac", "thermostat", "heating")}


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9ऀ-ॿ%]+", text.lower())


def _has_phrase(text: str, phrase: str) -> bool:
    return bool(phrase) and re.search(rf"(?<![a-z0-9]){re.escape(phrase.lower())}(?![a-z0-9])", text) is not None


class DeviceHub:
    def __init__(self, path: str | Path | None = None, profiles: dict[str, dict[str, Any]] | None = None, drivers: dict[str, Driver] | None = None):
        root = Path(os.environ.get("ATULYA_DEVICES_DIR", "data/devices"))
        self.path = Path(path) if path else root / "fabric.json"
        self.profile_dir = self.path.parent / "profiles"
        self.profiles = profiles if profiles is not None else load_profiles([self.profile_dir])
        self.drivers: dict[str, Driver] = drivers or {
            "profile": ProfileDriver(self.profiles), "adb": AdbDriver(), "wol": WolDriver(), "samsung": SamsungDriver(), "homeassistant": HomeAssistantDriver()}
        self.devices: dict[str, DeviceRecord] = {}
        self.last_candidates: dict[str, Candidate] = {}
        self.last_order: list[str] = []
        self._load()

    # ── storage ──────────────────────────────────────────────────────────────────────────────
    def _load(self) -> None:
        if not self.path.exists():
            return
        data = json.loads(vault.read_text(self.path))
        for d in data.get("devices", []):
            caps = [Capability(**c) for c in d.pop("capabilities", [])]
            self.devices[d["id"]] = DeviceRecord(**d, capabilities=caps)

    def _save(self) -> None:
        vault.write_text(self.path, json.dumps({"devices": [asdict(d) for d in self.devices.values()]}, indent=2))

    # ── managing devices ─────────────────────────────────────────────────────────────────────
    async def add(self, name: str, driver: str, address: str = "", config: dict[str, Any] | None = None, kind: str = "",
                  room: str = "", aliases: list[str] | None = None) -> DeviceRecord:
        if driver not in self.drivers:
            raise DeviceError(f"I don't know how to talk to “{driver}” devices.")
        name = " ".join(name.split())[:60]
        if not name:
            raise DeviceError("What should I call it?")
        config = dict(config or {})
        if driver == "profile":
            profile = self.profiles.get(str(config.get("profile")))
            if profile is None:
                raise DeviceError(f"I don't have a profile called “{config.get('profile')}”.")
            kind = kind or profile.get("kind", "device")
        dev = DeviceRecord(id=uuid.uuid4().hex[:8], name=name, kind=kind or "device", driver=driver, address=address, config=config,
                           aliases=[a.lower() for a in (aliases or [])], room=room)
        dev.capabilities = await self.drivers[driver].capabilities(dev)
        for old in [d for d in self.devices.values() if d.name.lower() == name.lower()]:
            del self.devices[old.id]             # same name = replace, not duplicate
        self.devices[dev.id] = dev
        self._save()
        return dev

    async def add_candidate(self, candidate_id: str, name: str = "", room: str = "") -> DeviceRecord:
        c = self.last_candidates.get(candidate_id)
        if c is None:
            raise DeviceError("I don't remember that one. Say “scan for devices” again.")
        if c.driver == "unknown":
            raise DeviceError("I can see it but don't know how to control it yet. Say “learn this device” and I'll try to work it out.")
        return await self.add(name or c.label, c.driver, c.host, c.config, c.kind, room)

    def remove(self, ref: str) -> str:
        dev = self.find(ref)
        if dev is None:
            raise DeviceError(f"I don't have a device called “{ref}”.")
        del self.devices[dev.id]
        self._save()
        return dev.name

    def find(self, ref: str) -> DeviceRecord | None:
        ref_l = ref.strip().lower()
        if ref_l in self.devices:
            return self.devices[ref_l]
        for d in self.devices.values():
            if ref_l == d.name.lower() or ref_l in d.aliases:
                return d
        partial = [d for d in self.devices.values() if ref_l and (ref_l in d.name.lower() or d.name.lower() in ref_l)]
        return partial[0] if len(partial) == 1 else None

    # ── doing things ─────────────────────────────────────────────────────────────────────────
    async def act(self, ref: str, capability: str, args: dict[str, Any] | None = None) -> str:
        dev = self.find(ref)
        if dev is None:
            raise DeviceError(f"I don't have a device called “{ref}”. I know: {', '.join(d.name for d in self.devices.values()) or 'none yet'}.")
        if dev.cap(capability) is None:
            options = ", ".join(c.name for c in dev.capabilities[:25])
            raise DeviceError(f"{dev.name} can't “{capability.replace('_', ' ')}”. It can: {options}.")
        before = dict(dev.config)
        result = await self.drivers[dev.driver].execute(dev, capability, args or {})
        if dev.config != before:   # e.g. a TV handed back its pairing token
            self._save()
        return result

    def is_risky(self, ref: str, capability: str) -> bool:
        dev = self.find(ref)
        cap = dev.cap(capability) if dev else None
        return bool(cap and cap.risky)

    # ── understanding speech ─────────────────────────────────────────────────────────────────
    def resolve(self, text: str) -> tuple[DeviceRecord, str, dict[str, Any]] | None:
        """Match a sentence to (device, capability, args). Returns None unless it is clear: the brain handles the rest."""
        t = " ".join(text.lower().split())
        if not self.devices or not t:
            return None
        device, alias = self._match_device(t)
        if device is None:
            return None
        rest = t.replace(alias, " ", 1) if alias else t
        best: tuple[int, Capability, str] | None = None
        for cap in device.capabilities:
            for phrase in [*cap.phrases, cap.name.replace("_", " ")]:
                if _has_phrase(rest, phrase) and (best is None or len(phrase) > best[0]):
                    best = (len(phrase), cap, phrase)
        if best is None:
            return None
        _, cap, phrase = best
        args: dict[str, Any] = {}
        left = rest.replace(phrase, " ", 1)
        if cap.repeat and (m := _NUM.search(left)):
            args["times"] = int(m.group(1))
            left = _NUM.sub(" ", left, count=1)
        if cap.params:
            pname, spec = next(iter(cap.params.items()))
            if spec.get("type") in ("integer", "number"):
                m = _NUM.search(left)
                if not m:
                    return None
                args[pname] = int(m.group(1))
                left = _NUM.sub(" ", left, count=1)
            else:
                words = [w for w in _words(left) if w not in {"the", "my", "please"}]
                while words and words[-1] in {"on", "in"}:       # "open youtube on" (the device's name was removed)
                    words.pop()
                if not words:
                    return None
                args[pname] = " ".join(words)
                left = ""
        leftover = [w for w in _words(left) if w not in _FILLER]
        if leftover:                               # unexplained words: not clearly a device command
            return None
        return device, cap.name, args

    def _match_device(self, t: str) -> tuple[DeviceRecord | None, str]:
        best: tuple[int, DeviceRecord, str] | None = None
        for d in self.devices.values():
            names = [d.name.lower(), *d.aliases]
            if d.room:
                names += [f"{d.room.lower()} {k}" for k in _KIND_WORDS.get(d.kind, (d.kind,))]
            for n in names:
                if _has_phrase(t, n) and (best is None or len(n) > best[0]):
                    best = (len(n), d, n)
        if best:
            return best[1], best[2]
        for kind, words in _KIND_WORDS.items():          # "the tv" works when there is exactly one TV
            of_kind = [d for d in self.devices.values() if d.kind == kind]
            for w in words:
                if len(of_kind) == 1 and _has_phrase(t, w):
                    return of_kind[0], w
        return None, ""

    def reload_profiles(self) -> None:
        """Pick up profiles you have approved (the driver shares this dict, so it sees them too)."""
        self.profiles.update(load_profiles([self.profile_dir]))

    @property
    def proposals_dir(self) -> Path:
        return self.path.parent / "proposals"

    def describe(self) -> list[dict[str, Any]]:
        return [{"id": d.id, "name": d.name, "kind": d.kind, "room": d.room, "driver": d.driver, "address": d.address,
                 "can": [c.name for c in d.capabilities]} for d in self.devices.values()]


_HUB: DeviceHub | None = None


def get_hub() -> DeviceHub:
    global _HUB
    if _HUB is None:
        _HUB = DeviceHub()
    return _HUB

