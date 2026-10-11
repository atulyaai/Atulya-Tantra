"""Local bilingual speech synthesis behavior, without loading model weights."""
from __future__ import annotations

import asyncio
import io
import sys
import types
import wave
from pathlib import Path

import httpx
import pytest
from conftest import authenticate_test_admin

import atulya.server as server
from atulya.settings import Settings
from tools.plugins.voice.providers import VoiceError
from tools.plugins.voice.tts import LocalSupertonicTTS, model_assets_ready


def test_tts_recognizes_hindi_and_encodes_wav(monkeypatch: pytest.MonkeyPatch, project_temp_dir: Path) -> None:
    observed = {}

    class GenerationConfig:
        sid = 0
        num_steps = 0
        speed = 0.0
        extra: dict[str, str] = {}

    class FakeEngine:
        def generate(self, text, config):
            observed["text"] = text
            observed["language"] = config.extra["lang"]
            return types.SimpleNamespace(sample_rate=16000, samples=[0.0, 0.25, -0.25])

    monkeypatch.setitem(sys.modules, "sherpa_onnx", types.SimpleNamespace(GenerationConfig=GenerationConfig))
    speech = LocalSupertonicTTS(project_temp_dir)
    speech._get_engine = lambda: FakeEngine()

    payload = speech.synthesize("नमस्ते", language="auto")
    with wave.open(io.BytesIO(payload), "rb") as source:
        assert (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getnframes()) == (
            1, 2, 16000, 3
        )
    assert observed == {"text": "नमस्ते", "language": "hi"}


def test_tts_rejects_unsupported_language_and_invalid_archive(project_temp_dir: Path) -> None:
    speech = LocalSupertonicTTS(project_temp_dir)
    with pytest.raises(VoiceError, match="supports English and Hindi"):
        speech.synthesize("Bonjour", language="fr")
    assert not model_assets_ready(project_temp_dir / "models")


def test_synthesis_api_serves_local_wav(
    project_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeSpeech:
        ready = True

        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def synthesize(self, text: str, *, language: str, speaker_id: int | None) -> bytes:
            assert text == "Hello Atulya"
            assert language == "en"
            assert speaker_id is None
            return b"RIFF-test-wav"

    monkeypatch.setattr(server, "LocalSupertonicTTS", FakeSpeech)
    settings = Settings(
        assistant_name="Atulya", host="127.0.0.1", port=8501,
        data_dir=project_temp_dir / "data", models_dir=project_temp_dir / "models",
        model_provider="", model_name="", model_base_url="", model_api_key="",
    )
    app = server.create_app(settings)

    async def fetch() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            authenticate_test_admin(client, app)
            return await client.post(
                "/api/voice/synthesize", json={"text": "Hello Atulya", "language": "en"}
            )

    response = asyncio.run(fetch())
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.content == b"RIFF-test-wav"
