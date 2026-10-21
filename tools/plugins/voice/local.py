"""Local, on-device speech recognition."""
from __future__ import annotations

import importlib.util
import io
import os
import tempfile
import wave
import threading
from pathlib import Path
from importlib.metadata import PackageNotFoundError, version

from .providers import VoiceError

_PROFILE_LANGUAGES = {
    "english": "en", "hindi": "hi", "marathi": "mr", "bengali": "bn", "gujarati": "gu",
    "punjabi": "pa", "tamil": "ta", "telugu": "te", "kannada": "kn", "malayalam": "ml",
    "urdu": "ur", "nepali": "ne", "spanish": "es", "french": "fr", "german": "de",
    "portuguese": "pt", "italian": "it", "russian": "ru", "arabic": "ar", "turkish": "tr",
    "japanese": "ja", "korean": "ko", "chinese": "zh", "indonesian": "id",
    "auto": None, "hinglish": None,
}


def _pcm16_mono_16k(audio: bytes):
    """16 kHz mono PCM16 WAV → float32 samples, skipping the temp file and decoder. Else None."""
    try:
        with wave.open(io.BytesIO(audio)) as wav:
            if wav.getframerate() != 16000 or wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                return None
            frames = wav.readframes(wav.getnframes())
    except (wave.Error, EOFError, ValueError):
        return None
    if len(frames) % 2:
        frames = frames[:-1]  # truncated upload: drop the half sample instead of failing
    import numpy as np

    return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0


class LocalVoice:
    """Lazy CPU speech recognition backed by faster-whisper."""

    def __init__(
        self,
        models_dir: Path,
        *,
        stt_model: str = "base",
        beam_size: int | None = None,
    ) -> None:
        self.models_dir = models_dir
        self.stt_model_name = stt_model
        self.english_model_name = os.environ.get("ATULYA_STT_MODEL_EN", "tiny.en").strip() or "tiny.en"
        # Beam 1 is ~40% faster than 3 on CPU with the same transcript on short commands (LOG.md M1-1).
        if beam_size is None:
            try:
                beam_size = int(os.environ.get("ATULYA_STT_BEAM", "1"))
            except ValueError:
                beam_size = 1
        self.beam_size = max(1, min(5, beam_size))
        self._models: dict[str, object] = {}
        self._last_used: dict[str, float] = {}
        self._stt_lock = threading.Lock()
        self.last_used = 0.0

    @property
    def ready(self) -> bool:
        if importlib.util.find_spec("faster_whisper") is None:
            return False
        if not self._pyav_supported():
            return False
        return all(self._local_model(name) is not None for name in {self.stt_model_name, self.english_model_name})

    def _local_model(self, name: str) -> Path | None:
        direct = Path(name)
        if direct.is_dir() and (direct / "model.bin").is_file():
            return direct
        cache = self.models_dir / "voice" / "stt" / "whisper"
        repository = cache / f"models--Systran--faster-whisper-{name}"
        # Follow the active revision; a partially downloaded or obsolete snapshot is not ready.
        try:
            revision = (repository / "refs" / "main").read_text(encoding="utf-8").strip()
        except OSError:
            return None
        snapshot = repository / "snapshots" / revision
        return snapshot if (snapshot / "model.bin").is_file() and (snapshot / "config.json").is_file() else None

    @staticmethod
    def _pyav_supported() -> bool:
        """faster-whisper 1.2.x passes an option removed in PyAV 19."""
        try:
            return int(version("av").split(".", 1)[0]) < 19
        except (PackageNotFoundError, ValueError):
            return False

    def _get_stt(self, model_name: str | None = None):
        if not self._pyav_supported():
            raise VoiceError("Local speech recognition needs a compatible audio decoder. Restart with start.bat to repair voice setup.")
        model_name = model_name or self.stt_model_name
        with self._stt_lock:
            if model_name not in self._models:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as exc:
                    raise VoiceError("Voice packages are missing. Restart with start.bat or start.sh to install them.") from exc
                try:
                    self._models[model_name] = WhisperModel(
                        str(self._local_model(model_name) or model_name),
                        device="cpu",
                        compute_type="int8",
                        download_root=str(self.models_dir / "voice" / "stt" / "whisper"),
                    )
                except Exception as exc:
                    raise VoiceError(f"Could not load the local speech recognition model: {exc}") from exc
            import time
            self._last_used[model_name] = time.monotonic()
            return self._models[model_name]

    def unload_if_idle(self, idle_seconds: float) -> bool:
        """Free the Whisper model's RAM when unused for a while; it reloads on demand."""
        import time

        with self._stt_lock:
            expired = [name for name in self._models
                       if time.monotonic() - self._last_used.get(name, 0) > idle_seconds]
            for name in expired:
                del self._models[name]
                self._last_used.pop(name, None)
            return bool(expired)

    def transcribe(self, audio: bytes, *, content_type: str, language: str) -> str:
        import time

        self.last_used = time.monotonic()
        if not audio:
            raise VoiceError("No audio was received. Try speaking again.")
        suffixes = {
            "audio/webm": ".webm",
            "audio/ogg": ".ogg",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/mp4": ".mp4",
            "audio/mpeg": ".mp3",
        }
        suffix = suffixes.get(content_type.split(";", 1)[0].strip().lower(), ".webm")
        temp_path: Path | None = None
        try:
            source = _pcm16_mono_16k(audio) if suffix == ".wav" else None
            if source is None:
                with tempfile.NamedTemporaryFile(prefix="atulya-voice-", suffix=suffix, delete=False) as temp_file:
                    temp_file.write(audio)
                    temp_path = Path(temp_file.name)
                source = str(temp_path)
            language_code = language.strip().replace("_", "-").split("-", 1)[0].lower() or None
            language_code = _PROFILE_LANGUAGES.get(language_code, language_code)
            model = self._get_stt(self.english_model_name if language_code == "en" else self.stt_model_name)
            segments, _ = model.transcribe(
                source,
                language=language_code,
                beam_size=self.beam_size,
                vad_filter=True,
                condition_on_previous_text=False,
            )
            transcript = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
            if not transcript:
                raise VoiceError("No speech was recognized. Try again or type your message.")
            return transcript
        except VoiceError:
            raise
        except Exception as exc:
            raise VoiceError(f"Local speech recognition failed: {exc}") from exc
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
