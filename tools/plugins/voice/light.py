"""Light, open-source voice for small servers: Vosk (speech recognition) + Piper (speech output).

Both run on 1-2 CPU cores without a GPU (Vosk ~2.7 s, Piper ~1.9 s per sentence on the atulvij.com
server), load on demand and unload when idle. Selected with ATULYA_VOICE_BACKEND=light.

Models (downloaded by tools/bootstrap.py into models/voice/):
  vosk/vosk-model-small-en-in-0.4, vosk/vosk-model-small-hi-0.22
  piper/en_US-ryan-medium.onnx(.json), piper/hi_IN-pratham-medium.onnx(.json)
"""
from __future__ import annotations

import io
import json
import re
import threading
import time
import wave
from pathlib import Path

from .providers import VoiceError

VOSK_MODELS = {"en": "vosk-model-small-en-in-0.4", "hi": "vosk-model-small-hi-0.22"}
PIPER_VOICES = {"en": "en_US-ryan-medium", "hi": "hi_IN-pratham-medium"}
PIPER_FEMALE = {"en": "en_US-amy-medium", "hi": "hi_IN-priyamvada-medium"}
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def _pcm16k(audio: bytes) -> bytes:
    import av

    container = av.open(io.BytesIO(audio))
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    pcm = bytearray()
    for frame in container.decode(audio=0):
        for chunk in resampler.resample(frame):
            pcm += bytes(chunk.planes[0])[: chunk.samples * 2]
    for chunk in resampler.resample(None):
        pcm += bytes(chunk.planes[0])[: chunk.samples * 2]
    container.close()
    return bytes(pcm)


class VoskSpeech:
    """Speech-to-text with the same interface as LocalVoice (ready / transcribe / unload_if_idle)."""

    def __init__(self, models_dir: Path) -> None:
        self.root = models_dir / "voice" / "vosk"
        self._models: dict[str, object] = {}
        self._lock = threading.Lock()
        self.last_used = 0.0

    @property
    def ready(self) -> bool:
        return (self.root / VOSK_MODELS["en"]).is_dir()

    def _model(self, language: str):
        language = language if language in VOSK_MODELS and (self.root / VOSK_MODELS[language]).is_dir() else "en"
        with self._lock:
            if language not in self._models:
                from vosk import Model, SetLogLevel

                SetLogLevel(-1)
                self._models[language] = Model(str(self.root / VOSK_MODELS[language]))
            return self._models[language]

    def transcribe(self, audio: bytes, *, content_type: str = "", language: str = "") -> str:
        from vosk import KaldiRecognizer

        self.last_used = time.monotonic()
        if not self.ready:
            raise VoiceError("Speech recognition models are not installed on this server.")
        try:
            pcm = _pcm16k(audio)
        except Exception as exc:
            raise VoiceError("Could not read that recording.") from exc
        code = (language or "en").split("-")[0].lower()
        recognizer = KaldiRecognizer(self._model("hi" if code == "hi" else "en"), 16000)
        recognizer.AcceptWaveform(pcm)
        return json.loads(recognizer.FinalResult()).get("text", "").strip()

    def _get_stt(self):  # preload hook used by the server
        return self._model("en")

    def unload_if_idle(self, idle_seconds: float) -> bool:
        with self._lock:
            if self._models and time.monotonic() - self.last_used > idle_seconds:
                self._models.clear()
                return True
        return False


class PiperSpeech:
    """Text-to-speech with the same interface as LocalSupertonicTTS (ready / synthesize / unload_if_idle)."""

    def __init__(self, models_dir: Path) -> None:
        self.root = models_dir / "voice" / "piper"
        self._voices: dict[str, object] = {}
        self._lock = threading.Lock()
        self.last_used = 0.0

    @property
    def ready(self) -> bool:
        return (self.root / f"{PIPER_VOICES['en']}.onnx").is_file()

    def _voice(self, language: str, gender: str = "male"):
        table = PIPER_FEMALE if gender == "female" else PIPER_VOICES
        name = table.get(language, "")
        if not (self.root / f"{name}.onnx").is_file():
            name = PIPER_VOICES.get(language, "") if (self.root / f"{PIPER_VOICES.get(language, '')}.onnx").is_file() else PIPER_VOICES["en"]
        with self._lock:
            if name not in self._voices:
                from piper import PiperVoice

                self._voices[name] = PiperVoice.load(str(self.root / f"{name}.onnx"))
            return self._voices[name]

    def synthesize(self, text: str, *, language: str = "auto", speaker_id: int | None = None,
                   voice: str = "male") -> bytes:
        from .tts import speakable

        self.last_used = time.monotonic()
        clean = speakable(text)
        if not clean or len(clean) > 1000:
            raise VoiceError("Speech text must contain 1 to 1000 characters.")
        if not self.ready:
            raise VoiceError("Speech output voices are not installed on this server.")
        code = "hi" if (language.lower().startswith("hi") or _DEVANAGARI.search(clean)) else "en"
        buffer = io.BytesIO()
        try:
            with wave.open(buffer, "wb") as output:
                self._voice(code, voice).synthesize_wav(clean, output)
        except Exception as exc:
            raise VoiceError("Speech synthesis failed.") from exc
        return buffer.getvalue()

    def _get_engine(self):  # preload hook used by the server
        return self._voice("en")

    def unload_if_idle(self, idle_seconds: float) -> bool:
        with self._lock:
            if self._voices and time.monotonic() - self.last_used > idle_seconds:
                self._voices.clear()
                return True
        return False
