"""Camera perception — continuous watching that turns frames into events.

A ``CameraWatcher`` reads frames from a webcam, an RTSP/HTTP stream or a
snapshot URL (most IP cameras and doorbells offer one), and publishes:

  vision.motion   {"camera": "front door", "level": 0.07}
  vision.person   {"camera": "front door", "count": 1, "snapshot": "…jpg"}

Motion detection is plain frame differencing on a small grey image, so it
costs almost nothing. The (heavier) person detector only runs while something
is moving, and a person must be seen in consecutive frames before an event is
raised, which filters out one-frame false alarms. Frames never leave the
machine; the latest snapshots are kept locally and pruned.

Person detection uses OpenCV (``pip install opencv-python-headless``): its
built-in HOG people detector, or a Haar cascade on OpenCV builds without HOG.
Without OpenCV, cameras still report motion if frames come from a snapshot
URL decoded elsewhere — but reading streams needs OpenCV too."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Protocol

# ── camera ────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

SNAPSHOTS_KEPT = 20


def spoken_name(name: str) -> str:
    """'front_door' -> 'front door' (what rules match and notifications say)."""
    return " ".join(re.sub(r"[_\-]+", " ", name or "camera").split()).lower()


def mask_source(source: str) -> str:
    """Hide credentials in a camera URL (rtsp://user:pass@host -> rtsp://***@host)."""
    return re.sub(r"(?<=://)[^/@\s]+@", "***@", str(source))


# ── detection ─────────────────────────────────────────────────────────────
def _to_small_gray(frame: Any, width: int = 160) -> Any:
    import numpy as np

    arr = np.asarray(frame)
    if arr.ndim == 3:
        arr = arr[..., :3].mean(axis=2)
    step = max(1, arr.shape[1] // width)
    return arr[::step, ::step].astype("float32")


class MotionDetector:
    """Running-average background subtraction on a downscaled grey frame."""

    def __init__(self, threshold: float = 25.0, min_area: float = 0.01, learning_rate: float = 0.2):
        self.threshold = threshold
        self.min_area = min_area
        self.learning_rate = learning_rate
        self._background = None

    def update(self, frame: Any) -> tuple[bool, float]:
        gray = _to_small_gray(frame)
        if self._background is None or self._background.shape != gray.shape:
            self._background = gray
            return False, 0.0
        changed = float((abs(gray - self._background) > self.threshold).mean())
        self._background = (1 - self.learning_rate) * self._background + self.learning_rate * gray
        return changed >= self.min_area, changed


class PersonDetector:
    """OpenCV people detector (HOG, or a Haar cascade fallback)."""

    def __init__(self):
        import cv2

        self._cv2 = cv2
        self.kind = ""
        if hasattr(cv2, "HOGDescriptor") and hasattr(cv2, "HOGDescriptor_getDefaultPeopleDetector"):
            self._hog = cv2.HOGDescriptor()
            self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            self.kind = "hog"
        else:
            cascades = getattr(getattr(cv2, "data", None), "haarcascades", "")
            path = os.path.join(cascades, "haarcascade_fullbody.xml")
            self._cascade = cv2.CascadeClassifier(path)
            if self._cascade.empty():
                raise RuntimeError("no OpenCV person detector available")
            self.kind = "haar"

    def detect(self, frame: Any) -> int:
        cv2 = self._cv2
        h, w = frame.shape[:2]
        scale = 480.0 / w if w > 480 else 1.0
        small = cv2.resize(frame, (int(w * scale), int(h * scale))) if scale != 1.0 else frame
        if self.kind == "hog":
            boxes, weights = self._hog.detectMultiScale(small, winStride=(8, 8), padding=(8, 8), scale=1.05)
            return int(sum(1 for wt in (weights.ravel() if len(weights) else []) if wt > 0.5))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY) if small.ndim == 3 else small
        return len(self._cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3))


def default_person_detector() -> PersonDetector | None:
    try:
        return PersonDetector()
    except Exception as exc:  # noqa: BLE001 - OpenCV missing or without detectors: motion only
        logger.info("person detection unavailable (%s); cameras will report motion only", exc)
        return None


# ── frame sources ─────────────────────────────────────────────────────────
class FrameSource(Protocol):
    def read(self) -> Any: ...

    def close(self) -> None: ...


class OpenCVSource:
    """A webcam index ("0"), a video file or an RTSP/HTTP stream."""

    def __init__(self, source: str):
        import cv2

        self._cv2 = cv2
        self._source = int(source) if str(source).isdigit() else source
        self._cap = None

    def read(self) -> Any:
        if self._cap is None or not self._cap.isOpened():
            self._cap = self._cv2.VideoCapture(self._source)
        ok, frame = self._cap.read()
        if not ok:
            self.close()  # reconnect next time (streams drop)
            return None
        return frame

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class SnapshotSource:
    """A URL that returns one JPEG per request (IP cameras, doorbells, Home Assistant)."""

    def __init__(self, url: str, headers: dict[str, str] | None = None, timeout: float = 8.0):
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout

    def read(self) -> Any:
        import cv2
        import httpx
        import numpy as np

        resp = httpx.get(self.url, headers=self.headers, timeout=self.timeout)
        resp.raise_for_status()
        return cv2.imdecode(np.frombuffer(resp.content, dtype=np.uint8), cv2.IMREAD_COLOR)

    def close(self) -> None:
        pass


def open_source(source: str) -> FrameSource:
    """Pick a frame source for a configured camera string."""
    s = str(source).strip()
    if s.startswith("ha:"):  # a Home Assistant camera entity: ha:camera.front_door
        url = os.environ.get("HOME_ASSISTANT_URL", "").rstrip("/")
        token = os.environ.get("HOME_ASSISTANT_TOKEN", "")
        return SnapshotSource(f"{url}/api/camera_proxy/{s[3:]}", {"Authorization": f"Bearer {token}"})
    if s.startswith(("http://", "https://")) and re.search(r"\.(jpe?g|png)(\?|$)|snapshot|image|camera_proxy", s, re.I):
        return SnapshotSource(s)
    return OpenCVSource(s)


# ── the watcher ───────────────────────────────────────────────────────────
class CameraWatcher:
    def __init__(
        self,
        name: str,
        source: FrameSource,
        events: Any,
        *,
        source_label: str = "",
        detector: Any = None,
        motion: MotionDetector | None = None,
        interval: float = 0.5,
        person_frames: int = 2,
        person_cooldown: float = 30.0,
        motion_cooldown: float = 60.0,
        snapshot_dir: str | Path | None = None,
    ):
        self.name = name
        self.camera = spoken_name(name)
        self.source = source
        self.source_label = mask_source(source_label)
        self.events = events
        self.detector = detector
        self.motion = motion or MotionDetector()
        self.interval = interval
        self.person_frames = max(1, person_frames)
        self.person_cooldown = person_cooldown
        self.motion_cooldown = motion_cooldown
        self.snapshot_dir = Path(snapshot_dir or os.environ.get("ATULYA_SNAPSHOT_DIR", "data/agent/snapshots"))
        self._streak = 0
        self._last_emit: dict[str, float] = {}
        self._task: asyncio.Task | None = None
        self.frames = 0
        self.error = ""
        self.last_motion: float | None = None
        self.last_person: float | None = None
        self.last_snapshot: str = ""

    # One frame through the pipeline; returns the events it raised.
    async def step(self, now: float | None = None) -> list[str]:
        now = time.time() if now is None else now
        try:
            frame = await asyncio.to_thread(self.source.read)
        except Exception as exc:  # noqa: BLE001 - a flaky camera must not kill the watcher
            self.error = str(exc)[:200]
            return []
        if frame is None:
            self.error = "no frame (camera offline?)"
            return []
        self.error = ""
        self.frames += 1
        moving, level = self.motion.update(frame)
        raised: list[str] = []
        if not moving:
            self._streak = 0
            return raised
        self.last_motion = now
        if self._ready("vision.motion", now, self.motion_cooldown):
            await self._emit("vision.motion", {"camera": self.camera, "level": round(level, 3)})
            raised.append("vision.motion")
        if self.detector is None:
            return raised
        try:
            people = await asyncio.to_thread(self.detector.detect, frame)
        except Exception as exc:  # noqa: BLE001
            self.error = f"detector: {exc}"[:200]
            return raised
        self._streak = self._streak + 1 if people else 0
        if people and self._streak >= self.person_frames:
            self.last_person = now
            if self._ready("vision.person", now, self.person_cooldown):
                snapshot = await asyncio.to_thread(self._save_snapshot, frame, now)
                await self._emit("vision.person", {"camera": self.camera, "count": int(people), "snapshot": snapshot})
                raised.append("vision.person")
        return raised

    async def run(self) -> None:
        while True:
            await self.step()
            await asyncio.sleep(self.interval)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        task = self._task
        try:
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    current = asyncio.current_task()
                    if current is not None and current.cancelling():
                        raise
                except Exception:
                    logger.exception("Camera watcher task failed during shutdown")
        finally:
            self._task = None
            await asyncio.to_thread(self.source.close)

    def status(self) -> dict[str, Any]:
        return {
            "name": self.name, "camera": self.camera, "source": self.source_label,
            "running": self._task is not None and not self._task.done(),
            "detector": getattr(self.detector, "kind", "") or "motion only",
            "frames": self.frames, "error": self.error, "last_motion": self.last_motion,
            "last_person": self.last_person, "snapshot": bool(self.last_snapshot),
        }

    def _ready(self, kind: str, now: float, cooldown: float) -> bool:
        if now - self._last_emit.get(kind, -1e18) < cooldown:
            return False
        self._last_emit[kind] = now
        return True

    async def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        try:
            await self.events.emit(event_type, payload)
        except Exception as exc:  # noqa: BLE001
            logger.debug("camera event failed: %s", exc)

    def _save_snapshot(self, frame: Any, now: float) -> str:
        try:
            import cv2
        except ImportError:
            return ""
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^a-z0-9_-]", "_", self.name.lower())
        path = self.snapshot_dir / f"{safe}-{int(now * 1000)}.jpg"
        if not cv2.imwrite(str(path), frame):
            return ""
        for old in sorted(self.snapshot_dir.glob(f"{safe}-*.jpg"))[:-SNAPSHOTS_KEPT]:
            old.unlink(missing_ok=True)
        self.last_snapshot = str(path)
        return path.name


# ── eyes ────────────────────────────────────────────────────────────
MAX_IMAGE_BYTES = 6 * 1024 * 1024
_ocr = None


def decode_image(data: str) -> bytes:
    """Accept a data URL or bare base64; reject anything that isn't a sane image."""
    raw = re.sub(r"^data:image/[\w.+-]+;base64,", "", (data or "").strip())
    try:
        blob = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("Image is not valid base64") from exc
    if not blob or len(blob) > MAX_IMAGE_BYTES:
        raise ValueError("Image is empty or too large")
    if not (blob[:3] == b"\xff\xd8\xff" or blob[:8] == b"\x89PNG\r\n\x1a\n" or blob[8:12] == b"WEBP"):
        raise ValueError("Only JPEG, PNG or WebP images are supported")
    return blob


def read_text(image: bytes) -> str:
    """OCR on this machine. Empty string when nothing is readable or OCR isn't installed."""
    global _ocr
    try:
        if _ocr is None:
            from rapidocr_onnxruntime import RapidOCR

            _ocr = RapidOCR()
        result, _ = _ocr(image)
    except ImportError:
        logger.info("rapidocr_onnxruntime not installed; skipping OCR")
        return ""
    except Exception as exc:
        logger.warning("OCR failed: %s", exc)
        return ""
    return "\n".join(item[1] for item in (result or []) if float(item[2]) >= 0.5)


def local_describe(image: bytes, question: str) -> str:
    """Scene description through a local Ollama vision model (moondream, llava…). Empty if unavailable."""
    host = os.environ.get("ATULYA_OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    model = os.environ.get("ATULYA_OLLAMA_VISION_MODEL", "moondream")
    body = {"model": model, "stream": False,
            "prompt": question or "Describe what you see in one or two sentences.",
            "images": [base64.b64encode(image).decode()]}
    req = urllib.request.Request(f"{host}/api/generate", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return str(json.loads(resp.read()).get("response", "")).strip()
    except Exception as exc:  # noqa: BLE001 - not installed / not running is normal
        logger.debug("Local vision unavailable: %s", exc)
        return ""


def describe_scene(image: bytes, question: str) -> str:
    """Local vision model first (private, free); Gemini only if configured and local gave nothing."""
    return local_describe(image, question) or cloud_describe(image, question)


def cloud_describe(image: bytes, question: str) -> str:
    """Scene description via Gemini (free tier). Empty string when not configured."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return ""
    model = os.environ.get("ATULYA_VISION_MODEL", "gemini-2.0-flash")
    mime = "image/png" if image[:4] == b"\x89PNG" else "image/webp" if image[8:12] == b"WEBP" else "image/jpeg"
    body = {"contents": [{"parts": [
        {"text": question or "Describe what you see in one or two sentences."},
        {"inline_data": {"mime_type": mime, "data": base64.b64encode(image).decode()}},
    ]}]}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as exc:
        logger.warning("Cloud vision failed: %s", exc)
        return ""


async def look(image_data: str, question: str = "") -> dict[str, Any]:
    image = decode_image(image_data)
    text, description = await asyncio.gather(
        asyncio.to_thread(read_text, image),
        asyncio.to_thread(describe_scene, image, question),
    )
    return {"text": text, "description": description, "can_describe": bool(description or os.environ.get("GEMINI_API_KEY"))}


def as_context(seen: dict[str, Any]) -> str:
    """What the camera saw, phrased for the brain."""
    parts = []
    if seen.get("description"):
        parts.append(f"The camera shows: {seen['description']}")
    if seen.get("text"):
        parts.append(f"Text visible in the picture:\n{seen['text']}")
    if not parts:
        parts.append("The user shared a picture, but no text was readable in it"
                     + ("" if seen.get("can_describe") else " and scene description is not set up (run `ollama pull moondream` or set GEMINI_API_KEY)")
                     + ". Say so honestly rather than guessing what it shows.")
    return "[What I see]\n" + "\n".join(parts) + "\n\n"


# ── home_sensors ────────────────────────────────────────────────────────────
_WATCHED_CLASSES = {"motion", "occupancy", "presence", "door", "opening", "window", "garage_door",
                    "smoke", "gas", "moisture", "carbon_monoxide", "sound", "vibration"}
_PERSON_CLASSES = {"occupancy", "presence"}
_NOISE_WORDS = {"doorbell", "person", "people", "motion", "occupancy", "presence", "sensor", "detected", "detection",
                "ding", "ring", "button", "pressed", "press", "camera", "cam", "event", "binary", "visitor"}


def place_name(entity_id: str, friendly_name: str = "") -> str:
    """'Front Door Doorbell' / binary_sensor.front_door_person -> 'front door'."""
    base = friendly_name or entity_id.split(".", 1)[-1]
    words = [w for w in re.split(r"[\s_\-]+", base.lower()) if w and w not in _NOISE_WORDS]
    return " ".join(words) or "home"


def is_doorbell(entity_id: str, attributes: dict[str, Any]) -> bool:
    text = f"{entity_id} {attributes.get('friendly_name', '')}".lower()
    return attributes.get("device_class") == "doorbell" or "doorbell" in text or re.search(r"\bding\b|_ding\b", text) is not None


def classify(entity_id: str, state: str, previous: str, attributes: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Events for one state change (empty if it's not interesting)."""
    if state == previous or state in ("unavailable", "unknown"):
        return []
    name = str(attributes.get("friendly_name") or entity_id)
    place = place_name(entity_id, str(attributes.get("friendly_name") or ""))
    device_class = str(attributes.get("device_class") or "")
    base = {"camera": place, "entity": entity_id, "name": name, "source": "home_assistant"}
    events: list[tuple[str, dict[str, Any]]] = [
        ("home.sensor", {**base, "state": state, "previous": previous, "device_class": device_class})]
    domain = entity_id.split(".", 1)[0]
    turned_on = state == "on"
    if is_doorbell(entity_id, attributes) and (turned_on or domain == "event"):
        events.append(("doorbell.pressed", base))
    elif turned_on and (device_class in _PERSON_CLASSES or re.search(r"person|people|visitor", entity_id)):
        events.append(("vision.person", {**base, "count": 1}))
    elif turned_on and device_class == "motion":
        events.append(("vision.motion", base))
    return events


def _watched(entity: dict[str, Any], explicit: set[str]) -> bool:
    entity_id = str(entity.get("entity_id", ""))
    if explicit:
        return entity_id in explicit
    attrs = entity.get("attributes") or {}
    if is_doorbell(entity_id, attrs):
        return True
    return entity_id.startswith("binary_sensor.") and attrs.get("device_class") in _WATCHED_CLASSES


class HomeSensorWatcher:
    def __init__(self, bridge: Any, events: Any, interval: float = 5.0, watch: set[str] | None = None):
        self.bridge = bridge
        self.events = events
        self.interval = interval
        env = os.environ.get("HOME_ASSISTANT_WATCH", "")
        self.explicit = watch if watch is not None else {e.strip() for e in env.split(",") if e.strip()}
        self._states: dict[str, str] = {}
        self._task: asyncio.Task | None = None
        self.error = ""
        self.watching = 0
        self.recent: list[dict[str, Any]] = []

    async def poll(self) -> list[tuple[str, dict[str, Any]]]:
        """One poll; returns the events raised. The first poll only learns states."""
        try:
            states = await self.bridge.states()
        except Exception as exc:  # noqa: BLE001 - Home Assistant restarting etc.
            self.error = str(exc)[:200]
            return []
        self.error = ""
        first = not self._states
        raised: list[tuple[str, dict[str, Any]]] = []
        watched = [s for s in states if _watched(s, self.explicit)]
        self.watching = len(watched)
        for entity in watched:
            entity_id = str(entity.get("entity_id"))
            state = str(entity.get("state", ""))
            previous = self._states.get(entity_id)
            self._states[entity_id] = state
            if first or previous is None:
                continue
            for event_type, payload in classify(entity_id, state, previous, entity.get("attributes") or {}):
                raised.append((event_type, payload))
                try:
                    await self.events.emit(event_type, payload)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("sensor event failed: %s", exc)
        if raised:
            now = time.time()
            self.recent = ([{"type": t, **p, "at": now} for t, p in raised] + self.recent)[:20]
        return raised

    async def run(self) -> None:
        while True:
            await self.poll()
            await asyncio.sleep(self.interval)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        task = self._task
        try:
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    current = asyncio.current_task()
                    if current is not None and current.cancelling():
                        raise
                except Exception:
                    logger.exception("Home sensor watcher task failed during shutdown")
        finally:
            self._task = None

    def status(self) -> dict[str, Any]:
        return {"running": self._task is not None and not self._task.done(), "watching": self.watching,
                "explicit": sorted(self.explicit), "error": self.error, "recent": self.recent[:10]}


# ── vision ────────────────────────────────────────────────────────────
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
        self.config_file = Path(config_file or os.environ.get("ATULYA_SENSES_FILE", "data/agent/senses.json"))
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
            from atulya.devices import HomeAssistantBridge

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

