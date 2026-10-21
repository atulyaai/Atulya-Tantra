"""The local voice stack is installed and its models are on disk (Step V).

Set ATULYA_SKIP_VOICE_DEPS=1 on machines without the voice models (CI).
"""
import importlib
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("ATULYA_SKIP_VOICE_DEPS") == "1",
                                reason="voice dependencies skipped by ATULYA_SKIP_VOICE_DEPS=1")

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"


@pytest.mark.parametrize("module", ["faster_whisper", "av", "sherpa_onnx", "onnxruntime", "openwakeword", "sounddevice"])
def test_voice_module_imports(module):
    importlib.import_module(module)


def test_bundled_silero_vad_present():
    import faster_whisper
    assets = Path(faster_whisper.__file__).parent / "assets"
    assert any(assets.glob("silero*.onnx"))


def test_local_stt_and_tts_ready():
    from tools.plugins.voice.local import LocalVoice
    from tools.plugins.voice.tts import LocalSupertonicTTS
    assert LocalVoice(MODELS_DIR).ready
    assert LocalSupertonicTTS(MODELS_DIR).ready
