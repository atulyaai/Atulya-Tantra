import asyncio
import io
import wave

import httpx
from conftest import authenticate_test_admin

from tools.plugins.voice.cache import CachedSpeech


def _wav():
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 100)
    return out.getvalue()


class Backend:
    speaker_id = 0
    num_steps = 4
    ready = True

    def __init__(self):
        self.calls = []

    def synthesize(self, text, **kwargs):
        self.calls.append((text, kwargs))
        return _wav()


def test_ack_cache_hit_survives_restart_and_keeps_voice_and_language_separate(project_temp_dir):
    backend = Backend()
    speech = CachedSpeech(backend, project_temp_dir)
    original = speech.synthesize("Checking the weather.", language="en")
    assert len(backend.calls) == 1 and backend.calls[0][1]["num_steps"] == 8
    assert CachedSpeech(backend, project_temp_dir).synthesize("Checking the weather. ") == original
    assert len(backend.calls) == 1
    assert speech.cached_audio("Checking the weather.", speaker_id=1) is None
    assert speech.cached_audio("Checking the weather.", language="hi") is None
    speech.synthesize("Checking the weather.", speaker_id=1)
    assert len(backend.calls) == 2
    assert backend.num_steps == 4  # cache generation must not mutate concurrent answer configuration


def test_personal_answers_are_never_cached_and_corrupt_ack_is_regenerated(project_temp_dir):
    backend = Backend()
    speech = CachedSpeech(backend, project_temp_dir)
    for _ in range(2):
        speech.synthesize("Your appointment with Alice is tomorrow.")
    assert not list(project_temp_dir.glob("*.wav"))
    path = speech._path("Yes?", "auto", None)
    path.write_bytes(b"broken")
    assert speech.synthesize("Yes?") == _wav()
    assert len(backend.calls) == 3
    assert speech.cached_audio("Yes?") == _wav()


def test_cache_failure_does_not_prevent_speech(project_temp_dir):
    blocked = project_temp_dir / "file"
    blocked.write_text("not a directory")
    speech = CachedSpeech(Backend(), blocked / "cache")
    assert speech.synthesize("Yes?") == _wav()


def test_cached_synthesis_api_works_without_loading_engine(project_temp_dir, monkeypatch):
    from atulya import server
    from atulya.settings import Settings

    backend = Backend()
    speech = CachedSpeech(backend, project_temp_dir / "cache")
    speech.synthesize("Checking the weather.")
    backend.ready = False
    monkeypatch.setattr(server, "LocalSupertonicTTS", lambda *a, **k: speech)
    app = server.create_app(Settings(assistant_name="Atulya", host="127.0.0.1", port=8501,
                                    data_dir=project_temp_dir / "data", models_dir=project_temp_dir / "models",
                                    model_provider="", model_name="", model_base_url="", model_api_key=""))

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            authenticate_test_admin(client, app)
            response = await client.post("/api/voice/synthesize", json={"text": "Checking the weather."})
            assert response.status_code == 200 and response.content == _wav()
            missing = await client.post("/api/voice/synthesize", json={"text": "Uncached answer."})
            assert missing.status_code == 503

    asyncio.run(run())
    assert len(backend.calls) == 1


def test_voice_answer_quality_does_not_change_read_aloud_or_acknowledgements(project_temp_dir, monkeypatch):
    from atulya import server
    from atulya.settings import Settings
    from tools.plugins.voice.tts import LocalSupertonicTTS, voice_num_steps

    monkeypatch.delenv("ATULYA_VOICE_TTS_STEPS", raising=False)
    monkeypatch.delenv("ATULYA_TTS_STEPS", raising=False)
    assert voice_num_steps() == 8 and LocalSupertonicTTS(project_temp_dir).num_steps == 8
    monkeypatch.setenv("ATULYA_VOICE_TTS_STEPS", "4")  # explicit overrides apply only to voice mode
    backend = Backend()
    backend.num_steps = 8
    speech = CachedSpeech(backend, project_temp_dir / "cache")
    monkeypatch.setattr(server, "LocalSupertonicTTS", lambda *a, **k: speech)
    app = server.create_app(Settings(assistant_name="Atulya", host="127.0.0.1", port=8501,
                                    data_dir=project_temp_dir / "data", models_dir=project_temp_dir / "models",
                                    model_provider="", model_name="", model_base_url="", model_api_key=""))

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            authenticate_test_admin(client, app)
            for body in ({"text": "An ordinary answer."}, {"text": "An ordinary answer.", "mode": "voice"},
                         {"text": "Checking the weather.", "mode": "voice"}):
                assert (await client.post("/api/voice/synthesize", json=body)).status_code == 200

    asyncio.run(run())
    assert "num_steps" not in backend.calls[0][1]  # regular read-aloud uses the untouched reference default
    assert backend.calls[1][1]["num_steps"] == 4
    assert backend.calls[2][1]["num_steps"] == 8
    assert backend.num_steps == 8
