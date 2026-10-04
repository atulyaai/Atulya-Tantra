"""Always-listening app: speech segmentation, wake word, conversation flow,
the server round trip, device sign-in and autostart files."""
from __future__ import annotations

import asyncio
import io
import wave
from pathlib import Path

import httpx
import pytest

np = pytest.importorskip("numpy")

from atulya.shruti.listener import (
    FRAME_SAMPLES,
    SAMPLE_RATE,
    AmbientEngine,
    AmbientSession,
    AtulyaClient,
    AuthError,
    Segmenter,
    WakeMatcher,
    speakable,
)


def frames(signal: np.ndarray):
    for i in range(0, len(signal) - FRAME_SAMPLES + 1, FRAME_SAMPLES):
        yield signal[i:i + FRAME_SAMPLES]


def tone(seconds: float, amp: float = 0.3) -> np.ndarray:
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    return (amp * np.sin(2 * np.pi * 220 * t)).astype("float32")


def quiet(seconds: float) -> np.ndarray:
    rng = np.random.default_rng(0)
    return (rng.normal(0, 0.002, int(seconds * SAMPLE_RATE))).astype("float32")


# ── hearing ───────────────────────────────────────────────────────────────

class TestSegmenter:
    def test_one_sentence_becomes_one_utterance(self):
        seg = Segmenter()
        audio = np.concatenate([quiet(1.0), tone(1.2), quiet(1.2)])
        out = [u for u in (seg.feed(f) for f in frames(audio)) if u is not None]
        assert len(out) == 1
        assert 1.2 <= len(out[0]) / SAMPLE_RATE <= 2.4  # speech + pre-roll + trailing pause

    def test_clicks_and_silence_are_ignored(self):
        seg = Segmenter()
        audio = np.concatenate([quiet(1.0), tone(0.15), quiet(1.5)])
        assert [u for u in (seg.feed(f) for f in frames(audio)) if u is not None] == []

    def test_adapts_to_a_noisy_room(self):
        seg = Segmenter()
        rng = np.random.default_rng(1)
        hum = rng.normal(0, 0.02, SAMPLE_RATE * 3).astype("float32")  # fan noise above the minimum level
        assert [u for u in (seg.feed(f) for f in frames(hum)) if u is not None] == []
        assert seg.threshold > seg.min_rms


class TestWakeWord:
    @pytest.mark.parametrize("text, rest", [
        ("Hey Atulya, turn on the kitchen light.", "turn on the kitchen light"),
        ("atulya what time is it", "what time is it"),
        ("A tulia, what time is it?", "what time is it"),   # how speech-to-text may spell it
        ("Um, hey Atoolya lights off", "lights off"),
        ("Atulya.", ""),
    ])
    def test_wakes(self, text, rest):
        assert WakeMatcher().match(text) == (True, rest)

    @pytest.mark.parametrize("text", ["Actually, I think so", "turn on the kitchen light", "", "hey there"])
    def test_does_not_wake(self, text):
        assert WakeMatcher().match(text)[0] is False

    def test_custom_wake_word(self):
        assert WakeMatcher(["jarvis"]).match("Jarvis, lights on") == (True, "lights on")


class TestSession:
    def test_wake_word_then_command(self):
        s = AmbientSession()
        assert s.on_utterance("Atulya", now=0) == ("prompt", "Yes?")
        assert s.on_utterance("turn on the kitchen light", now=3) == ("send", "turn on the kitchen light")
        assert s.on_utterance("and the bedroom light", now=4) == ("ignore", "")  # back to needing the wake word

    def test_listening_window_expires(self):
        s = AmbientSession(listen_window=5)
        s.on_utterance("Atulya", now=0)
        assert s.on_utterance("turn on the light", now=10) == ("ignore", "")

    def test_confirmation_needs_no_wake_word(self):
        s = AmbientSession()
        assert s.on_utterance("hey atulya unlock the front door", now=0) == ("send", "unlock the front door")
        s.on_reply({"needs_approval": True}, now=1)
        assert s.on_utterance("yes", now=5) == ("send", "yes")
        s.on_reply({"needs_approval": False}, now=6)
        assert s.on_utterance("yes", now=7) == ("ignore", "")

    def test_follow_up_window(self):
        s = AmbientSession(follow_up=8)
        s.on_utterance("hey atulya what's the weather in delhi", now=0)
        s.on_reply({}, now=1)
        assert s.on_utterance("and tomorrow", now=5) == ("send", "and tomorrow")


def test_speakable_strips_chat_formatting():
    assert speakable("Guests are coming — all 3 steps done.\n- **Kitchen Light** turned on.\n2. Done") == (
        "Guests are coming — all 3 steps done. Kitchen Light turned on. Done.")


# ── the engine ────────────────────────────────────────────────────────────

class FakeClient:
    def __init__(self, replies=None, fail: Exception | None = None):
        self.replies = list(replies or [])
        self.sent: list[str] = []
        self.fail = fail
        self.beats: list[dict] = []

    async def chat(self, text):
        self.sent.append(text)
        if self.fail:
            raise self.fail
        return self.replies.pop(0) if self.replies else {"response_text": "Done."}

    async def heartbeat(self, info):
        self.beats.append(info)


class FakeSpeaker:
    def __init__(self):
        self.said: list[str] = []

    def say(self, text):
        self.said.append(text)


class FakeSTT:
    def __init__(self, texts):
        self.texts = list(texts)

    async def transcribe(self, audio):
        return self.texts.pop(0)


class TestEngine:
    def test_conversation_with_confirmation(self):
        client = FakeClient([
            {"response_text": "Just to confirm — should I unlock the front door?", "needs_approval": True},
            {"response_text": "Front Door is now unlocked."},
        ])
        speaker = FakeSpeaker()
        engine = AmbientEngine(client, FakeSTT(["Hey Atulya, unlock the front door", "Yes"]), speaker)

        async def run():
            await engine.handle_utterance(np.zeros(10))
            await engine.handle_utterance(np.zeros(10))

        asyncio.run(run())
        assert client.sent == ["unlock the front door", "Yes"]
        assert speaker.said == ["Just to confirm — should I unlock the front door?", "Front Door is now unlocked."]
        assert engine.last_heard is not None and engine.status == "listening"

    def test_bare_wake_word_answers_yes(self):
        speaker = FakeSpeaker()
        engine = AmbientEngine(FakeClient(), None, speaker)
        assert asyncio.run(engine.handle_text("Atulya")) == ""
        assert speaker.said == ["Yes?"]

    def test_sign_in_problem_is_spoken(self):
        speaker = FakeSpeaker()
        engine = AmbientEngine(FakeClient(fail=AuthError("no")), None, speaker)
        asyncio.run(engine.handle_text("hey atulya lights on"))
        assert engine.needs_sign_in and "sign this device in" in speaker.said[0]

    def test_server_down_is_spoken(self):
        speaker = FakeSpeaker()
        engine = AmbientEngine(FakeClient(fail=httpx.ConnectError("down")), None, speaker)
        asyncio.run(engine.handle_text("hey atulya lights on"))
        assert speaker.said == ["I can't reach Atulya right now."]

    def test_notifications_spoken_unless_muted_or_routine(self):
        speaker = FakeSpeaker()
        engine = AmbientEngine(FakeClient(), None, speaker)
        asyncio.run(engine.on_notification({"title": "Reminder alerts", "desc": "Reminder: call mom", "type": "info"}))
        asyncio.run(engine.on_notification({"title": "x", "desc": "Saved", "type": "success"}))
        engine.toggle_mute()
        asyncio.run(engine.on_notification({"title": "Door", "desc": "Someone is at the front door."}))
        assert speaker.said == ["Reminder: call mom."]
        assert engine.status == "muted" and not engine.accepts_audio()

    def test_only_listens_for_stop_while_speaking(self):
        engine = AmbientEngine(FakeClient(), FakeSTT(["what time is it"]), FakeSpeaker())
        engine.speaking = True
        assert engine.accepts_audio()  # open for barge-in...
        asyncio.run(engine.handle_utterance(b""))
        assert engine.client.sent == []  # ...but nothing is sent while it talks


# ── against the real server ──────────────────────────────────────────────

class TestServerRoundTrip:
    @pytest.fixture
    def app(self, monkeypatch, tmp_path):
        from atulya.sevak import helpers
        from atulya.sevak.app import app
        from atulya.events import EventBus
        from atulya.drishti import Senses

        monkeypatch.setattr(helpers, "ADMIN_TOKEN", "test_token")
        monkeypatch.delenv("HOME_ASSISTANT_URL", raising=False)
        app.state.senses = Senses(EventBus(), config_file=tmp_path / "senses.json")
        yield app
        del app.state.senses

    def client(self, app, token="test_token"):
        return AtulyaClient("http://atulya.test", token, device="kitchen-pi", transport=httpx.ASGITransport(app=app))

    def test_command_heartbeat_and_device_token(self, app):
        async def run():
            c = self.client(app)
            reply = await c.chat("turn on the kitchen light")
            minted = await c._post("/api/senses/device-token", json={"device": "kitchen-pi"})
            device = self.client(app, token=minted["token"])
            await device.heartbeat({"state": "listening", "wake_word": "hey atulya"})
            status = await device._post("/api/senses/device-token", json={})  # the device token works
            return reply, minted, status

        reply, minted, status = asyncio.run(run())
        assert reply["response_text"] == "Kitchen Light turned on." and "audio_base64" not in reply
        assert minted["expires_in"] == 90 * 86400 and status["token"]
        listener = app.state.senses.status()["listeners"][0]
        assert listener["device"] == "kitchen-pi" and listener["user"] == "admin" and listener["online"]

    def test_client_cannot_claim_a_pre_authorized_source(self, app):
        async def run():
            c = self.client(app)
            return await c._post("/api/voice/chat", json={"prompt": "unlock the front door", "source": "automation",
                                                          "tts": False})

        assert asyncio.run(run())["needs_approval"] is True

    def test_bad_token_raises_auth_error(self, app):
        with pytest.raises(AuthError):
            asyncio.run(self.client(app, token="nope").chat("hello"))


# ── audio helpers, CLI config and autostart ───────────────────────────────

def test_wav_encoding():
    from atulya.shruti.audio import to_wav

    data = to_wav(tone(0.5))
    with wave.open(io.BytesIO(data)) as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (16000, 1, 2)
        assert wav.getnframes() == 8000


def test_print_speaker(capsys):
    from atulya.shruti.audio import Speaker

    Speaker(backend="print").say("Hello there.")
    assert "Atulya: Hello there." in capsys.readouterr().out


class TestCli:
    def test_options_precedence_and_saved_token_is_private(self, tmp_path, monkeypatch):
        from atulya.shruti import cli

        monkeypatch.setenv("ATULYA_AMBIENT_CONFIG", str(tmp_path / "ambient.json"))
        monkeypatch.setenv("ATULYA_URL", "http://env:8000")
        path = cli.save_config({"url": "http://saved:8000", "token": "abc", "wake": "jarvis"})
        args = cli.build_parser().parse_args(["--device", "den"])
        opts = cli.resolve(args, cli.load_config())
        import os
        assert (opts["url"], opts["token"], opts["device"], opts["wake"]) == ("http://env:8000", "abc", "den", "jarvis")
        if os.name == "posix":
            assert oct(path.stat().st_mode & 0o777) == "0o600"

    def test_refuses_to_start_without_sign_in(self, tmp_path, monkeypatch, capsys):
        from atulya.shruti import cli

        monkeypatch.setenv("ATULYA_AMBIENT_CONFIG", str(tmp_path / "none.json"))
        monkeypatch.delenv("ATULYA_TOKEN", raising=False)
        assert cli.main([]) == 1
        assert "--login" in capsys.readouterr().out


class TestAutostart:
    def test_windows(self, tmp_path):
        from atulya.shruti.autostart import autostart_entry

        path, content = autostart_entry("Windows", r"C:\Python312\python.exe", tmp_path)
        assert path.name == "Atulya Listener.bat" and "Startup" in str(path)
        assert r'"C:\Python312\pythonw.exe" -m atulya.shruti' in content

    def test_macos(self, tmp_path):
        from atulya.shruti.autostart import autostart_entry

        path, content = autostart_entry("Darwin", "/usr/bin/python3", tmp_path, args=["--wake", "a&b"])
        assert path.name == "ai.atulya.listener.plist" and "<string>a&amp;b</string>" in content
        assert "<key>RunAtLoad</key>" in content

    def test_linux_desktop_and_systemd(self, tmp_path):
        from atulya.shruti.autostart import install, uninstall

        path, _hint = install(system="Linux", python="/usr/bin/python3", home=tmp_path)
        assert path == tmp_path / ".config/autostart/atulya-listener.desktop"
        assert "Exec=/usr/bin/python3 -m atulya.shruti" in path.read_text()
        spath, hint = install(system="Linux", python="/usr/bin/python3", home=tmp_path, mode="systemd")
        assert "--no-tray" in spath.read_text() and "systemctl --user enable" in hint
        assert uninstall(system="Linux", python="/usr/bin/python3", home=tmp_path)
        assert not Path(path).exists()


@pytest.mark.skipif(not __import__("importlib").util.find_spec("PIL"), reason="Pillow not installed")
def test_tray_icon_colours():
    from atulya.shruti.tray import icon_image

    img = icon_image("muted", size=32)
    assert img.size == (32, 32) and img.getpixel((16, 10))[:3] == (120, 120, 130)


class TestHindiAndBargeIn:
    def test_hindi_wake_word_and_command(self):
        from atulya.shruti.listener import WakeMatcher

        woke, rest = WakeMatcher().match("हे अतुल्य बत्ती जलाओ")
        assert woke and "बत्ती" in rest

    def test_hinglish_wake(self):
        from atulya.shruti.listener import WakeMatcher

        assert WakeMatcher().match("suno atulya play music")[0]

    def test_normalize_keeps_devanagari_marks(self):
        from atulya.shruti.listener import _normalize

        assert _normalize("अतुल्य!") == "अतुल्य"

    def test_stop_word_interrupts_speech(self):
        import asyncio

        from atulya.shruti.listener import AmbientEngine

        class Speaker(FakeSpeaker):
            stopped = False

            def stop(self):
                self.stopped = True

        speaker = Speaker()
        engine = AmbientEngine(FakeClient(), FakeSTT(["stop", "tell me a story"]), speaker)
        engine.speaking = True
        assert engine.accepts_audio()  # mic stays open to hear "stop"
        asyncio.run(engine.handle_utterance(b""))
        assert speaker.stopped
        speaker.stopped = False
        asyncio.run(engine.handle_utterance(b""))  # not a stop word: ignored as echo
        assert not speaker.stopped and engine.client.sent == []
