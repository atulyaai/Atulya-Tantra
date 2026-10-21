"""LocalVoice passes 16 kHz mono PCM16 WAV as an array (no temp file); other audio goes via a file (M1-1)."""
import io
import wave
from types import SimpleNamespace

import numpy as np

from tools.plugins.voice.local import LocalVoice


class _StubModel:
    def __init__(self):
        self.calls = []

    def transcribe(self, source, **kwargs):
        self.calls.append((source, kwargs))
        return iter([SimpleNamespace(text=" hello ")]), None


def _wav(rate=16000, channels=1):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes((np.ones(rate // 10 * channels, dtype="<i2") * 1000).tobytes())
    return buffer.getvalue()


def _voice(tmp_path, monkeypatch, **kwargs):
    voice = LocalVoice(tmp_path, **kwargs)
    stub = _StubModel()
    monkeypatch.setattr(voice, "_get_stt", lambda model_name=None: stub)
    return voice, stub


def test_16k_wav_goes_as_array(tmp_path, monkeypatch):
    voice, stub = _voice(tmp_path, monkeypatch)
    assert voice.transcribe(_wav(), content_type="audio/wav", language="en") == "hello"
    source, kwargs = stub.calls[0]
    assert isinstance(source, np.ndarray) and source.dtype == np.float32
    assert abs(float(source[0]) - 1000 / 32768) < 1e-6
    assert kwargs["beam_size"] == 1 and kwargs["language"] == "en"


def test_other_audio_goes_as_file(tmp_path, monkeypatch):
    voice, stub = _voice(tmp_path, monkeypatch, beam_size=3)
    voice.transcribe(b"webm-bytes", content_type="audio/webm;codecs=opus", language="en-IN")
    voice.transcribe(_wav(rate=44100), content_type="audio/wav", language="en")
    sources = [call[0] for call in stub.calls]
    assert all(isinstance(source, str) for source in sources)
    assert sources[0].endswith(".webm") and sources[1].endswith(".wav")
    assert stub.calls[0][1]["beam_size"] == 3


def test_tts_steps_from_env(tmp_path, monkeypatch):
    from tools.plugins.voice.tts import LocalSupertonicTTS
    assert LocalSupertonicTTS(tmp_path).num_steps == 8
    monkeypatch.setenv("ATULYA_TTS_STEPS", "2")
    assert LocalSupertonicTTS(tmp_path).num_steps == 2
    monkeypatch.setenv("ATULYA_TTS_STEPS", "x")
    assert LocalSupertonicTTS(tmp_path).num_steps == 8


def test_beam_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ATULYA_STT_BEAM", "4")
    assert LocalVoice(tmp_path).beam_size == 4
    monkeypatch.setenv("ATULYA_STT_BEAM", "junk")
    assert LocalVoice(tmp_path).beam_size == 1


def test_truncated_wav_does_not_crash(tmp_path, monkeypatch):
    voice, stub = _voice(tmp_path, monkeypatch)
    assert voice.transcribe(_wav()[:-1], content_type="audio/wav", language="en") == "hello"
    assert len(stub.calls) == 1


def test_model_by_language_and_independent_idle_unload(tmp_path, monkeypatch):
    import sys
    import time

    loaded = []

    def model(name, **kwargs):
        loaded.append(name)
        return _StubModel()

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=model))
    monkeypatch.setattr(LocalVoice, "_pyav_supported", staticmethod(lambda: True))
    voice = LocalVoice(tmp_path)
    for language in ("en", "en-IN", "english", "hi", "auto", "", "marathi"):
        assert voice.transcribe(_wav(), content_type="audio/wav", language=language) == "hello"
    assert loaded == ["tiny.en", "base"]
    assert voice._models["base"].calls[-1][1]["language"] == "mr"
    voice._last_used["tiny.en"] = time.monotonic() - 1000
    assert voice.unload_if_idle(600)
    assert set(voice._models) == {"base"}
    assert not voice.unload_if_idle(600)


def test_ready_requires_both_models_not_just_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(LocalVoice, "_pyav_supported", staticmethod(lambda: True))
    monkeypatch.setattr("tools.plugins.voice.local.importlib.util.find_spec", lambda name: object())
    voice = LocalVoice(tmp_path)

    def cached(name):
        repository = tmp_path / "voice" / "stt" / "whisper" / f"models--Systran--faster-whisper-{name}"
        (repository / "refs").mkdir(parents=True)
        (repository / "refs" / "main").write_text("revision")
        snapshot = repository / "snapshots" / "revision"
        snapshot.mkdir(parents=True)
        (snapshot / "model.bin").touch()
        (snapshot / "config.json").write_text("{}")

    (tmp_path / ".voice-ready").write_text("base\n")
    cached("base")
    assert not voice.ready
    cached("tiny.en")
    assert voice.ready
