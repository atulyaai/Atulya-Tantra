"""Missing speech packages must fail with a clear error, not a decoder crash (bug pass 2026-11-12).

Before: a missing PyAV/Piper package surfaced as a confusing failure ("Could not read that
recording." / "channels not specified") instead of "speech package missing".
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from tools.plugins.voice.light import PiperSpeech, VoskSpeech
from tools.plugins.voice.providers import VoiceError


def _install_none_for(*names: str):
    real = importlib.util.find_spec

    def fake(name, *args, **kwargs):
        if name in names:
            return None
        return real(name, *args, **kwargs)

    return fake


def test_missing_av_package_is_reported_clearly(monkeypatch: pytest.MonkeyPatch, project_temp_dir: Path) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", _install_none_for("av"))
    models = project_temp_dir / "models"
    (models / "voice" / "vosk" / "vosk-model-small-en-in-0.4").mkdir(parents=True, exist_ok=True)
    speech = VoskSpeech(models)
    assert speech.ready
    with pytest.raises(VoiceError, match="av"):
        speech.transcribe(b"\x00\x00\x00\x00", content_type="audio/wav")


def test_missing_piper_package_is_reported_clearly(monkeypatch: pytest.MonkeyPatch, project_temp_dir: Path) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", _install_none_for("piper"))
    models = project_temp_dir / "models"
    (models / "voice" / "piper").mkdir(parents=True, exist_ok=True)
    (models / "voice" / "piper" / "en_US-ryan-medium.onnx").write_bytes(b"fake")
    speech = PiperSpeech(models)
    assert speech.ready
    with pytest.raises(VoiceError, match="piper"):
        speech.synthesize("Hello Atulya", language="en")
