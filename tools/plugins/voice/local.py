"""Local, on-device speech recognition."""
from __future__ import annotations

import importlib.util
import tempfile
import threading
from pathlib import Path
from importlib.metadata import PackageNotFoundError, version

from .providers import VoiceError


class LocalVoice:
    """Lazy CPU speech recognition backed by faster-whisper."""

    def __init__(
        self,
        models_dir: Path,
        *,
        stt_model: str = "base",
    ) -> None:
        self.models_dir = models_dir
        self.stt_model_name = stt_model
        self._stt = None
        self._stt_lock = threading.Lock()

    @property
    def ready(self) -> bool:
        if importlib.util.find_spec("faster_whisper") is None:
            return False
        if not self._pyav_supported():
            return False
        marker = self.models_dir / ".voice-ready"
        try:
            prepared = marker.read_text(encoding="utf-8").splitlines()
        except OSError:
            return False
        if prepared[:1] != [self.stt_model_name]:
            return False
        whisper_dir = self.models_dir / "voice" / "stt" / "whisper"
        return whisper_dir.exists() and any(whisper_dir.rglob("model.bin"))

    @staticmethod
    def _pyav_supported() -> bool:
        """faster-whisper 1.2.x passes an option removed in PyAV 19."""
        try:
            return int(version("av").split(".", 1)[0]) < 19
        except (PackageNotFoundError, ValueError):
            return False

    def _get_stt(self):
        if not self._pyav_supported():
            raise VoiceError("Local speech recognition needs a compatible audio decoder. Restart with start.bat to repair voice setup.")
        if self._stt is None:
            with self._stt_lock:
                if self._stt is None:
                    try:
                        from faster_whisper import WhisperModel
                    except ImportError as exc:
                        raise VoiceError("Voice packages are missing. Restart with start.bat or start.sh to install them.") from exc
                    try:
                        self._stt = WhisperModel(
                            self.stt_model_name,
                            device="cpu",
                            compute_type="int8",
                            download_root=str(self.models_dir / "voice" / "stt" / "whisper"),
                        )
                    except Exception as exc:
                        raise VoiceError(f"Could not load the local speech recognition model: {exc}") from exc
        return self._stt

    def transcribe(self, audio: bytes, *, content_type: str, language: str) -> str:
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
            with tempfile.NamedTemporaryFile(prefix="atulya-voice-", suffix=suffix, delete=False) as temp_file:
                temp_file.write(audio)
                temp_path = Path(temp_file.name)
            model = self._get_stt()
            language_code = language.strip().replace("_", "-").split("-", 1)[0].lower() or None
            segments, _ = model.transcribe(
                str(temp_path),
                language=language_code,
                beam_size=3,
                vad_filter=True,
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
