"""Senses — what Atulya perceives on its own, as events on the bus.

* cameras (``camera.CameraWatcher``): motion and people, from webcams, RTSP
  streams, snapshot URLs or Home Assistant camera entities;
* Home Assistant sensors (``home_sensors.HomeSensorWatcher``): doorbells,
  people, motion, doors, smoke…;
* always-listening devices (``atulya.shruti``) check in with a heartbeat so the
  UI can show which rooms Atulya can hear.

Cameras come from ``ATULYA_CAMERAS`` ("front_door=rtsp://…, desk=0") and from
the ones added in the web UI (``ATULYA_SENSES_FILE``, default
kosh/agent/senses.json). Home Assistant sensors are watched whenever Home
Assistant is configured, unless ``ATULYA_WATCH_HOME=false``.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Callable

from atulya.indriya.camera import CameraWatcher, default_person_detector, mask_source, open_source, spoken_name
from atulya.indriya.home_sensors import HomeSensorWatcher

logger = logging.getLogger(__name__)

LISTENER_STALE_SECONDS = 120
_CURRENT: "Senses | None" = None


def current_senses() -> "Senses | None":
    return _CURRENT


def _env_cameras() -> list[dict[str, Any]]:
    cams = []
    for item in os.environ.get("ATULYA_CAMERAS", "").split(","):
        if "=" in item:
            name, source = item.split("=", 1)
            if name.strip() and source.strip():
                cams.append({"name": name.strip(), "source": source.strip(), "enabled": True, "from_env": True})
    return cams


def _ago(ts: float | None, now: float) -> str:
    if not ts:
        return ""
    minutes = int((now - ts) // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    return f"{hours} hour{'s' if hours != 1 else ''} ago"


class Senses:
    def __init__(
        self,
        events: Any,
        config_file: str | Path | None = None,
        detector_factory: Callable[[], Any] = default_person_detector,
        source_factory: Callable[[str], Any] = open_source,
        home_bridge: Any = None,
    ):
        self.events = events
        self.config_file = Path(config_file or os.environ.get("ATULYA_SENSES_FILE", "kosh/agent/senses.json"))
        self._detector_factory = detector_factory
        self._source_factory = source_factory
        self._home_bridge = home_bridge
        self._detector: Any = None
        self._detector_ready = False
        self.cameras: dict[str, CameraWatcher] = {}
        self.camera_errors: dict[str, str] = {}
        self.home: HomeSensorWatcher | None = None
        self.listeners: dict[str, dict[str, Any]] = {}

    # ── configuration ──────────────────────────────────────────────────────
    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.config_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if not isinstance(data.get("cameras"), list):
            data["cameras"] = []
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def configured_cameras(self) -> list[dict[str, Any]]:
        saved = [c for c in self._load()["cameras"] if isinstance(c, dict) and c.get("name")]
        names = {c["name"] for c in saved}
        return saved + [c for c in _env_cameras() if c["name"] not in names]

    # ── lifecycle ──────────────────────────────────────────────────────────
    async def start(self) -> None:
        global _CURRENT
        _CURRENT = self
        for cam in self.configured_cameras():
            if cam.get("enabled", True):
                self._start_camera(str(cam["name"]), str(cam["source"]))
        bridge = self._home_bridge
        if bridge is None:
            from atulya.yantra.capabilities.home_assistant import HomeAssistantBridge

            bridge = HomeAssistantBridge()
        if bridge.configured and os.environ.get("ATULYA_WATCH_HOME", "true").lower() not in ("0", "false", "no"):
            self.home = HomeSensorWatcher(bridge, self.events)
            self.home.start()

    async def stop(self) -> None:
        global _CURRENT
        for watcher in list(self.cameras.values()):
            await watcher.stop()
        self.cameras.clear()
        if self.home is not None:
            await self.home.stop()
            self.home = None
        if _CURRENT is self:
            _CURRENT = None

    def _person_detector(self) -> Any:
        if not self._detector_ready:
            self._detector = self._detector_factory()
            self._detector_ready = True
        return self._detector

    def _start_camera(self, name: str, source: str) -> None:
        try:
            watcher = CameraWatcher(name, self._source_factory(source), self.events, source_label=source,
                                    detector=self._person_detector())
        except Exception as exc:  # noqa: BLE001 - e.g. OpenCV not installed
            self.camera_errors[name] = f"can't open camera: {exc}"[:200]
            logger.warning("camera %s not started: %s", name, exc)
            return
        self.camera_errors.pop(name, None)
        self.cameras[name] = watcher
        watcher.start()

    async def add_camera(self, name: str, source: str) -> dict[str, Any]:
        name = re.sub(r"[^A-Za-z0-9 _-]", "", name or "").strip().replace(" ", "_").lower()
        if not name or not str(source or "").strip():
            raise ValueError("a camera needs a name and a source (webcam number, stream URL or snapshot URL)")
        await self.remove_camera(name, persist=False)
        data = self._load()
        data["cameras"] = [c for c in data["cameras"] if c.get("name") != name]
        data["cameras"].append({"name": name, "source": str(source).strip(), "enabled": True})
        self._save(data)
        self._start_camera(name, str(source).strip())
        return self.camera_status(name)

    async def remove_camera(self, name: str, persist: bool = True) -> bool:
        watcher = self.cameras.pop(name, None)
        if watcher is not None:
            await watcher.stop()
        self.camera_errors.pop(name, None)
        if not persist:
            return watcher is not None
        data = self._load()
        kept = [c for c in data["cameras"] if c.get("name") != name]
        removed = len(kept) != len(data["cameras"])
        if removed:
            data["cameras"] = kept
            self._save(data)
        return removed or watcher is not None

    # ── always-listening devices ───────────────────────────────────────────
    def heartbeat(self, listener: dict[str, Any], user: str = "") -> dict[str, Any]:
        device = re.sub(r"[^\w .-]", "", str(listener.get("device") or "listener"))[:60] or "listener"
        entry = {
            "device": device, "user": user, "state": str(listener.get("state") or "listening")[:30],
            "wake_word": str(listener.get("wake_word") or "")[:40], "stt": str(listener.get("stt") or "")[:40],
            "muted": bool(listener.get("muted", False)), "last_seen": time.time(),
            "last_heard": listener.get("last_heard"),
        }
        self.listeners[device] = entry
        return entry

    # ── views ──────────────────────────────────────────────────────────────
    def camera_status(self, name: str) -> dict[str, Any]:
        if name in self.cameras:
            return self.cameras[name].status()
        source = next((c["source"] for c in self.configured_cameras() if c["name"] == name), "")
        return {"name": name, "camera": spoken_name(name), "source": mask_source(source), "running": False,
                "error": self.camera_errors.get(name, "disabled"), "detector": "", "frames": 0}

    def status(self) -> dict[str, Any]:
        now = time.time()
        names = [c["name"] for c in self.configured_cameras()]
        names += [n for n in self.cameras if n not in names]
        try:
            import cv2  # noqa: F401

            opencv = True
        except ImportError:
            opencv = False
        return {
            "cameras": [self.camera_status(n) for n in names],
            "home": self.home.status() if self.home else None,
            "listeners": [{**entry, "online": now - entry["last_seen"] < LISTENER_STALE_SECONDS}
                          for entry in sorted(self.listeners.values(), key=lambda e: e["device"])],
            "opencv": opencv,
        }

    def describe(self, now: float | None = None) -> str:
        """A spoken answer to "is anyone at the door?"."""
        now = time.time() if now is None else now
        lines = []
        for name in [c["name"] for c in self.configured_cameras()] or list(self.cameras):
            st = self.camera_status(name)
            label = f"The {st['camera']} camera"
            if not st.get("running"):
                lines.append(f"{label} isn't running ({st.get('error') or 'off'}).")
            elif st.get("last_person") and now - st["last_person"] < 3600:
                lines.append(f"{label} saw someone {_ago(st['last_person'], now)}.")
            elif st.get("last_motion") and now - st["last_motion"] < 3600:
                lines.append(f"{label} saw movement {_ago(st['last_motion'], now)}, but no one I could make out.")
            else:
                lines.append(f"{label} hasn't seen anyone in the last hour.")
        if self.home is not None:
            person = next((e for e in self.home.recent if e.get("type") in ("vision.person", "doorbell.pressed")
                           and now - float(e.get("at") or 0) < 3600), None)
            if person:
                what = "The doorbell rang" if person["type"] == "doorbell.pressed" else f"{person['name']} saw someone"
                lines.append(f"{what} {_ago(person.get('at'), now)} ({person['camera']}).")
        return "\n".join(lines) if lines else "No cameras are set up yet. Add one under Admin → Senses."
