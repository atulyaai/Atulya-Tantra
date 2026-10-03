"""Auto brain tier, local vision, lockdown, daily briefing, Piper voice, wake gate, voice commands."""
import asyncio
import datetime as dt
import json

import pytest

from atulya.agent.intent_router import route_intent


def run(coro):
    return asyncio.run(coro)


# ── brain ────────────────────────────────────────────────────────────────

def test_brain_auto_follows_free_ram(monkeypatch):
    from atulya.cognition import brain

    monkeypatch.setenv("ATULYA_BRAIN", "auto")
    monkeypatch.setattr(brain, "recommend_tier", lambda: "balanced")
    assert brain.active_brain() == "balanced"


# ── vision ───────────────────────────────────────────────────────────────

class _Resp:
    def __init__(self, payload):
        self._p = payload

    def read(self):
        return json.dumps(self._p).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_local_vision_describes_through_ollama(monkeypatch):
    import urllib.request

    from atulya import eyes

    seen = {}

    def fake_urlopen(req, timeout=0):
        seen["body"] = json.loads(req.data)
        return _Resp({"response": " A desk with a laptop. "})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert eyes.local_describe(b"\xff\xd8\xff", "what is this?") == "A desk with a laptop."
    assert seen["body"]["model"] == "moondream" and seen["body"]["images"]


def test_describe_scene_prefers_local_then_cloud(monkeypatch):
    from atulya import eyes

    monkeypatch.setattr(eyes, "local_describe", lambda i, q: "")
    monkeypatch.setattr(eyes, "cloud_describe", lambda i, q: "cloud says hi")
    assert eyes.describe_scene(b"x", "") == "cloud says hi"
    monkeypatch.setattr(eyes, "local_describe", lambda i, q: "local says hi")
    assert eyes.describe_scene(b"x", "") == "local says hi"


# ── lockdown ─────────────────────────────────────────────────────────────

def test_lockdown_forces_localhost_and_no_cors(monkeypatch):
    from atulya import lockdown

    monkeypatch.setenv("ATULYA_HOST", "0.0.0.0")
    monkeypatch.delenv("ATULYA_CORS_ORIGINS", raising=False)
    monkeypatch.delenv("ATULYA_LOCKDOWN", raising=False)
    assert lockdown.bind_host() == "0.0.0.0" and lockdown.cors_origins() is None
    monkeypatch.setenv("ATULYA_LOCKDOWN", "on")
    assert lockdown.bind_host() == "127.0.0.1" and lockdown.cors_origins() == []
    monkeypatch.setenv("ATULYA_CORS_ORIGINS", "https://me.example")
    assert lockdown.cors_origins() == ["https://me.example"]


# ── daily briefing ───────────────────────────────────────────────────────

def test_briefing_clock_fires_once_per_day():
    from atulya.ambient.listener import BriefingClock

    clock = BriefingClock("08:00")
    day = dt.date(2026, 10, 4)
    assert not clock.due(dt.datetime.combine(day, dt.time(7, 59)))
    assert clock.due(dt.datetime.combine(day, dt.time(8, 1)))
    assert not clock.due(dt.datetime.combine(day, dt.time(9, 0)))
    assert clock.due(dt.datetime.combine(day + dt.timedelta(days=1), dt.time(8, 0)))


def test_engine_speaks_the_briefing():
    from atulya.ambient.listener import AmbientEngine

    class Client:
        sent = []

        async def chat(self, text):
            self.sent.append(text)
            return {"response_text": "Good morning. It is sunny."}

    class Speaker:
        said = []

        def say(self, text):
            self.said.append(text)

    engine = AmbientEngine(Client(), None, Speaker(), briefing_at="07:00", briefing_location="Delhi")
    run(engine.deliver_briefing())
    assert "Delhi" in Client.sent[0] and Speaker.said == ["Good morning. It is sunny."]


# ── voice commands reach the new tools ───────────────────────────────────

@pytest.mark.parametrize("text,tool,args", [
    ("good morning", "morning_briefing", {}),
    ("give me my briefing", "morning_briefing", {}),
    ("pause the music", "media_control", {"action": "play_pause"}),
    ("next song", "media_control", {"action": "next"}),
    ("volume up", "media_control", {"action": "volume_up"}),
    ("play arijit singh", "play_music", {"query": "arijit singh"}),
])
def test_router_maps_media_and_briefing(text, tool, args):
    routed = route_intent(text)
    assert routed is not None and routed.tool == tool and routed.arguments == args


def test_router_still_prefers_websites_for_play_on_site():
    routed = route_intent("play lofi on youtube")
    assert routed.tool == "open_website"


# ── piper voice ──────────────────────────────────────────────────────────

def test_speaker_picks_piper_when_configured(monkeypatch):
    import shutil

    from atulya.ambient.audio import Speaker

    monkeypatch.setenv("ATULYA_PIPER_MODEL", "voice.onnx")
    monkeypatch.setattr(shutil, "which", lambda name: "/bin/piper" if name == "piper" else None)
    assert Speaker().backend == "piper"
    monkeypatch.delenv("ATULYA_PIPER_MODEL")
    assert Speaker().backend != "piper"


# ── wake-word model gate ─────────────────────────────────────────────────

def test_wake_gate_fires_and_expires():
    np = pytest.importorskip("numpy")
    from atulya.ambient.audio import WakeGate

    now = [100.0]

    class Model:
        score = 0.0

        def predict(self, chunk):
            assert chunk.dtype == np.int16 and len(chunk) == WakeGate.CHUNK
            return {"atulya": self.score}

    model = Model()
    gate = WakeGate(model=model, threshold=0.5, window=10, clock=lambda: now[0])
    frame = np.zeros(WakeGate.CHUNK, dtype="float32")
    assert not gate.feed(frame) and not gate.recent()
    model.score = 0.9
    assert gate.feed(frame) and gate.recent()
    now[0] += 11
    assert not gate.recent()


def test_microphone_holds_back_speech_without_wake_word():
    pytest.importorskip("numpy")
    from atulya.ambient.audio import Microphone, WakeGate

    class Never:
        def predict(self, chunk):
            return {"x": 0.0}

    gate = WakeGate(model=Never())
    assert Microphone(gate=gate).gate is gate
    assert not gate.recent()


# ── speech language, local sign-in ───────────────────────────────────────

def test_pick_language_never_returns_arabic():
    from types import SimpleNamespace

    from yantra.capabilities.voice_pipeline import pick_language

    noisy = SimpleNamespace(language="ar", all_language_probs=[("ar", 0.5), ("hi", 0.3), ("en", 0.1)])
    assert pick_language(noisy) == "hi"
    assert pick_language(SimpleNamespace(language="en", all_language_probs=[])) == "en"
    assert pick_language(SimpleNamespace(language="ar", all_language_probs=None)) in ("en", "hi")


def _client(host="127.0.0.1", headers=None):
    from fastapi.testclient import TestClient

    from drishti.dashboard.app import app

    return TestClient(app, client=(host, 5000), headers=headers or {})


def test_local_signin_only_from_this_computer(monkeypatch):
    monkeypatch.delenv("ATULYA_REQUIRE_LOGIN", raising=False)
    assert _client().get("/api/auth/local").json()["token"]
    assert _client(host="192.168.1.20").get("/api/auth/local").status_code == 403
    assert _client(headers={"X-Forwarded-For": "8.8.8.8"}).get("/api/auth/local").status_code == 403
    monkeypatch.setenv("ATULYA_REQUIRE_LOGIN", "on")
    assert _client().get("/api/auth/local").status_code == 403
