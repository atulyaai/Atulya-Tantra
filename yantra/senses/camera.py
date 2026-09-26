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
URL decoded elsewhere — but reading streams needs OpenCV too.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Protocol

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
        self.snapshot_dir = Path(snapshot_dir or os.environ.get("ATULYA_SNAPSHOT_DIR", "assets/agent/snapshots"))
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
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
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
