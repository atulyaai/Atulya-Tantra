"""Senses: camera motion/person events, Home Assistant sensors, the "someone at
the door" reflex, and the senses API."""
from __future__ import annotations

import asyncio
import importlib.util

import pytest

np = pytest.importorskip("numpy")

from atulya.events import EventBus

HAS_CV2 = importlib.util.find_spec("cv2") is not None


def blank(value: int = 0) -> np.ndarray:
    return np.full((120, 160, 3), value, dtype=np.uint8)


def with_block(value: int = 255) -> np.ndarray:
    frame = blank()
    frame[20:100, 40:120] = value  # a big bright shape appears
    return frame


class ListSource:
    def __init__(self, frames):
        self.frames = list(frames)
        self.closed = False

    def read(self):
        return self.frames.pop(0) if self.frames else None

    def close(self):
        self.closed = True


class StubDetector:
    kind = "stub"

    def __init__(self, counts):
        self.counts = list(counts)

    def detect(self, frame):
        return self.counts.pop(0) if self.counts else 0


def recorder():
    bus = EventBus()
    seen: list[tuple[str, dict]] = []
    bus.subscribe("*", lambda e: seen.append((e.type, e.payload)))
    return bus, seen


# ── camera pipeline ───────────────────────────────────────────────────────

class TestCamera:
    def test_motion_detector_ignores_still_scenes(self):
        from atulya.indriya import MotionDetector

        det = MotionDetector()
        assert det.update(blank()) == (False, 0.0)  # learns the background
        assert det.update(blank())[0] is False
        moving, level = det.update(with_block())
        assert moving and level > 0.1

    def test_person_needs_consecutive_frames_then_cooldown(self, tmp_path):
        from atulya.indriya import CameraWatcher

        bus, seen = recorder()
        frames = [blank(), with_block(), blank(), with_block(), blank(), with_block(), blank(), with_block()]
        watcher = CameraWatcher("front_door", ListSource(frames), bus, detector=StubDetector([1, 1, 1, 1, 1, 1, 1]),
                                snapshot_dir=tmp_path, person_cooldown=100, motion_cooldown=0)
        raised = [asyncio.run(watcher.step(now=float(i))) for i in range(len(frames))]
        persons = [i for i, r in enumerate(raised) if "vision.person" in r]
        assert persons == [2]  # first seen at frame 1, confirmed at frame 2, then cooling down
        payload = next(p for t, p in seen if t == "vision.person")
        assert payload["camera"] == "front door" and payload["count"] == 1
        assert watcher.status()["last_person"] == 7.0  # still seen, just not re-announced

    def test_no_detector_means_motion_only(self, tmp_path):
        from atulya.indriya import CameraWatcher

        bus, seen = recorder()
        watcher = CameraWatcher("desk", ListSource([blank(), with_block()]), bus, detector=None, snapshot_dir=tmp_path)
        asyncio.run(watcher.step())
        assert asyncio.run(watcher.step()) == ["vision.motion"]
        assert watcher.status()["detector"] == "motion only"

    def test_offline_camera_is_reported_not_fatal(self, tmp_path):
        from atulya.indriya import CameraWatcher

        class Broken:
            def read(self):
                raise ConnectionError("stream dropped")

            def close(self):
                pass

        watcher = CameraWatcher("porch", Broken(), EventBus(), snapshot_dir=tmp_path)
        assert asyncio.run(watcher.step()) == []
        assert watcher.status()["error"] == "stream dropped"
        watcher.source = ListSource([])
        asyncio.run(watcher.step())
        assert "offline" in watcher.status()["error"]

    def test_credentials_are_masked(self):
        from atulya.indriya import mask_source

        assert mask_source("rtsp://admin:secret@10.0.0.5/stream") == "rtsp://***@10.0.0.5/stream"

    def test_picks_the_right_source(self, monkeypatch):
        from atulya.indriya import SnapshotSource, open_source

        monkeypatch.setenv("HOME_ASSISTANT_URL", "http://ha.local:8123")
        monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "t")
        ha = open_source("ha:camera.front_door")
        assert isinstance(ha, SnapshotSource) and ha.url.endswith("/api/camera_proxy/camera.front_door")
        assert ha.headers == {"Authorization": "Bearer t"}
        assert isinstance(open_source("http://cam.local/snapshot.jpg"), SnapshotSource)

    @pytest.mark.skipif(not HAS_CV2, reason="OpenCV not installed")
    def test_real_opencv_detector_and_snapshot(self, tmp_path):
        from atulya.indriya import CameraWatcher, PersonDetector

        det = PersonDetector()
        assert det.kind in ("hog", "haar") and det.detect(blank()) == 0
        watcher = CameraWatcher("gate", ListSource([]), EventBus(), snapshot_dir=tmp_path)
        name = watcher._save_snapshot(with_block(), 1.0)
        assert name.endswith(".jpg") and (tmp_path / name).exists()


# ── Home Assistant sensors ────────────────────────────────────────────────

class FakeBridge:
    def __init__(self, polls, configured=True):
        self.polls = list(polls)
        self.configured = configured

    async def states(self):
        return self.polls.pop(0) if self.polls else []


def entity(entity_id, state, **attrs):
    return {"entity_id": entity_id, "state": state, "attributes": attrs}


class TestHomeSensors:
    def test_changes_become_events(self):
        from atulya.indriya import HomeSensorWatcher

        before = [entity("binary_sensor.front_door_person", "off", device_class="occupancy",
                         friendly_name="Front Door Person"),
                  entity("event.front_door_doorbell", "2026-09-26T10:00:00", friendly_name="Front Door Doorbell"),
                  entity("binary_sensor.hall_motion", "off", device_class="motion", friendly_name="Hall Motion"),
                  entity("sensor.temperature", "21")]
        after = [entity("binary_sensor.front_door_person", "on", device_class="occupancy",
                        friendly_name="Front Door Person"),
                 entity("event.front_door_doorbell", "2026-09-26T10:05:00", friendly_name="Front Door Doorbell"),
                 entity("binary_sensor.hall_motion", "on", device_class="motion", friendly_name="Hall Motion"),
                 entity("sensor.temperature", "22")]
        bus, seen = recorder()
        watcher = HomeSensorWatcher(FakeBridge([before, after]), bus, watch=set())
        assert asyncio.run(watcher.poll()) == []  # first poll only learns the current states
        asyncio.run(watcher.poll())
        types = [t for t, _ in seen]
        assert "vision.person" in types and "doorbell.pressed" in types and "vision.motion" in types
        assert next(p for t, p in seen if t == "doorbell.pressed")["camera"] == "front door"
        assert watcher.watching == 3  # the temperature sensor isn't watched

    def test_explicit_watch_list(self):
        from atulya.indriya import HomeSensorWatcher

        bus, seen = recorder()
        polls = [[entity("switch.kettle", "off")], [entity("switch.kettle", "on")]]
        watcher = HomeSensorWatcher(FakeBridge(polls), bus, watch={"switch.kettle"})
        asyncio.run(watcher.poll())
        asyncio.run(watcher.poll())
        assert seen[0][0] == "home.sensor" and seen[0][1]["state"] == "on"

    def test_place_names(self):
        from atulya.indriya import place_name

        assert place_name("binary_sensor.front_door_person") == "front door"
        assert place_name("x", "Back Garden Motion Sensor") == "back garden"


# ── the reflex ────────────────────────────────────────────────────────────

def test_someone_at_the_door_rule(tmp_path):
    from atulya.buddhi.triggers import TriggerEngine

    bus, seen = recorder()
    engine = TriggerEngine(rules_file=tmp_path / "t.json", events=bus)
    engine.start()

    async def run():
        await bus.emit("vision.person", {"camera": "front door", "count": 1})
        await bus.emit("vision.person", {"camera": "desk", "count": 1})  # not a door
        await engine.drain()

    asyncio.run(run())
    notes = [p["message"] for t, p in seen if t == "notification"]
    assert notes == ["Someone is at the front door."]


# ── the hub and the question "is anyone at the door?" ─────────────────────

class TestSensesHub:
    def make(self, tmp_path, frames=None):
        from atulya.indriya import Senses

        bus, seen = recorder()
        senses = Senses(bus, config_file=tmp_path / "senses.json", detector_factory=lambda: StubDetector([1] * 10),
                        source_factory=lambda s: ListSource(frames or []), home_bridge=FakeBridge([]))
        return senses, seen

    def test_add_describe_remove(self, tmp_path):
        senses, _ = self.make(tmp_path)

        async def run():
            status = await senses.add_camera("Front Door", "rtsp://me:pw@cam/stream")
            watcher = senses.cameras["front_door"]
            watcher.source = ListSource([blank(), with_block(), with_block()])
            for _ in range(3):
                await watcher.step()
            answer = senses.describe()
            removed = await senses.remove_camera("front_door")
            return status, answer, removed

        status, answer, removed = asyncio.run(run())
        assert status["source"] == "rtsp://***@cam/stream" and status["camera"] == "front door"
        assert answer == "The front door camera saw someone just now."
        assert removed and senses.configured_cameras() == []

    def test_env_cameras_and_broken_camera(self, tmp_path, monkeypatch):
        from atulya.indriya import Senses

        monkeypatch.setenv("ATULYA_CAMERAS", "porch=rtsp://x, bad")

        def explode(source):
            raise RuntimeError("OpenCV not installed")

        senses = Senses(EventBus(), config_file=tmp_path / "s.json", detector_factory=lambda: None,
                        source_factory=explode, home_bridge=FakeBridge([], configured=False))
        asyncio.run(senses.start())
        cams = senses.status()["cameras"]
        assert [c["name"] for c in cams] == ["porch"] and "OpenCV not installed" in cams[0]["error"]
        assert "isn't running" in senses.describe()

    def test_kernel_answers_is_anyone_at_the_door(self, tmp_path):
        from atulya.buddhi.kernel import CognitiveKernel
        from atulya.buddhi.planner import Planner, RoutineStore
        from atulya.buddhi.profile import ProfileStore
        from atulya import indriya as senses_mod

        senses, _ = self.make(tmp_path)
        previous = senses_mod._CURRENT
        senses_mod._CURRENT = senses
        try:
            kernel = CognitiveKernel(llm=None, events=EventBus(), planner=Planner(RoutineStore(tmp_path / "r.json")),
                                     profiles=ProfileStore(tmp_path / "p"))
            kernel._llm = object()  # never consulted: the question is routed directly
            r = asyncio.run(kernel.handle("is anyone at the door?"))
        finally:
            senses_mod._CURRENT = previous
        assert r.text.startswith("No cameras are set up yet")


# ── routes ────────────────────────────────────────────────────────────────

class TestSensesApi:
    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        from atulya.sevak import helpers
        from atulya.sevak.app import app
        from atulya.indriya import Senses

        monkeypatch.setattr(helpers, "ADMIN_TOKEN", "test_token")
        app.state.senses = Senses(EventBus(), config_file=tmp_path / "senses.json", detector_factory=lambda: None,
                                  source_factory=lambda s: ListSource([]), home_bridge=FakeBridge([]))
        yield TestClient(app)
        del app.state.senses

    def test_cameras_snapshot_and_heartbeat(self, client, tmp_path):
        h = {"X-Atulya-Token": "test_token"}
        assert client.get("/api/senses").status_code == 401
        assert client.post("/api/senses/cameras", json={"name": "", "source": "0"}, headers=h).status_code == 400
        cam = client.post("/api/senses/cameras", json={"name": "garage", "source": "0"}, headers=h).json()["camera"]
        assert cam["name"] == "garage"
        status = client.get("/api/senses", headers=h).json()
        assert [c["name"] for c in status["cameras"]] == ["garage"] and "opencv" in status
        assert client.get("/api/senses/cameras/garage/snapshot?token=test_token").status_code == 404
        assert client.get("/api/senses/cameras/garage/snapshot?token=wrong").status_code == 401
        beat = client.post("/api/senses/heartbeat", json={"device": "kitchen-pi", "wake_word": "hey atulya"},
                           headers=h).json()
        assert beat["listener"]["user"] == "admin"
        listeners = client.get("/api/senses", headers=h).json()["listeners"]
        assert listeners[0]["device"] == "kitchen-pi" and listeners[0]["online"]
        assert client.delete("/api/senses/cameras/garage", headers=h).json()["ok"]
        assert client.delete("/api/senses/cameras/garage", headers=h).status_code == 404
