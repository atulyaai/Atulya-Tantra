"""Optional local Supertonic 3 speech output through sherpa-onnx."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import os
import re
import threading
import wave
from pathlib import Path

from .providers import VoiceError


TTS_MODEL_FOLDER = "sherpa-onnx-supertonic-3-tts-int8-2026-05-11"
TTS_MODEL_FILE_SHA256 = {
    "duration_predictor.int8.onnx": "c3eb91414d5ff8a7a239b7fe9e34e7e2bf8a8140d8375ffb14718b1c639325db",
    "text_encoder.int8.onnx": "c7befd5ea8c3119769e8a6c1486c4edc6a3bc8365c67621c881bbb774b9902ff",
    "vector_estimator.int8.onnx": "20cd86fa5c6effedfda0e7cffe5b0569ca401c440a0c3a1d72bf39286c0db3fd",
    "vocoder.int8.onnx": "e923d60f53f95eb1ce235f1dc33ec56d9c057823c96fa6f8acf98f32b0da6152",
    "tts.json": "42078d3aef1cd43ab43021f3c54f47d2d75ceb4e75f627f118890128b06a0d09",
    "unicode_indexer.bin": "8402ca48e5189a8950138580b0fff64db6f072f24ac07cd54ba8b2fbb9883b30",
    "voice.bin": "67d5209b0ee8ce6c74105ffbe12fe6a7628aea3b4ba2fcb308a4a67938a93ce8",
}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def model_assets_ready(models_dir: Path) -> bool:
    model_dir = models_dir / "voice" / "tts" / "supertonic-3-int8" / TTS_MODEL_FOLDER
    return all(
        (model_dir / filename).is_file() and _file_sha256(model_dir / filename) == digest
        for filename, digest in TTS_MODEL_FILE_SHA256.items()
    )


_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]+")


def voice_num_steps() -> int:
    """Owner-selected spoken-answer quality; read-aloud retains the engine default."""
    try:
        return max(1, min(16, int(os.environ.get("ATULYA_VOICE_TTS_STEPS", "8"))))
    except ValueError:
        return 8


def speakable(text: str) -> str:
    """Drop emoji and markdown symbols so the voice never reads them out."""
    text = _EMOJI.sub("", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # [label](url) -> label
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_`#>|~]+", "", text)
    text = text.replace(" ", " ").replace(" ", " ").replace("×", " times ")
    return re.sub(r"\s+", " ", text).strip()


class LocalSupertonicTTS:
    """Create bilingual local speech on demand; no audio leaves the device."""

    def __init__(self, models_dir: Path, *, speaker_id: int = 0, num_threads: int = 2) -> None:
        self.model_dir = models_dir / "voice" / "tts" / "supertonic-3-int8" / TTS_MODEL_FOLDER
        self.speaker_id = max(0, min(9, int(speaker_id)))
        self.num_threads = max(1, min(8, int(num_threads)))
        # Flow-matching steps: 8 is the reference quality; 2 is ~2x faster on a 4-core CPU (LOG.md M1-0).
        try:
            self.num_steps = max(1, min(16, int(os.environ.get("ATULYA_TTS_STEPS", "8"))))
        except ValueError:
            self.num_steps = 8
        self._engine = None
        self._lock = threading.Lock()
        self.last_used = 0.0
        self._generate_lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return importlib.util.find_spec("sherpa_onnx") is not None and model_assets_ready(self.model_dir.parents[3])

    def _get_engine(self):
        if not self.ready:
            raise VoiceError("Local speech output needs its runtime and model. Restart Atulya to repair voice setup.")
        if self._engine is None:
            with self._lock:
                if self._engine is None:
                    try:
                        import sherpa_onnx

                        config = sherpa_onnx.OfflineTtsConfig(
                            model=sherpa_onnx.OfflineTtsModelConfig(
                                supertonic=sherpa_onnx.OfflineTtsSupertonicModelConfig(
                                    duration_predictor=str(self.model_dir / "duration_predictor.int8.onnx"),
                                    text_encoder=str(self.model_dir / "text_encoder.int8.onnx"),
                                    vector_estimator=str(self.model_dir / "vector_estimator.int8.onnx"),
                                    vocoder=str(self.model_dir / "vocoder.int8.onnx"),
                                    tts_json=str(self.model_dir / "tts.json"),
                                    unicode_indexer=str(self.model_dir / "unicode_indexer.bin"),
                                    voice_style=str(self.model_dir / "voice.bin"),
                                ),
                                num_threads=self.num_threads,
                                debug=False,
                                provider="cpu",
                            )
                        )
                        self._engine = sherpa_onnx.OfflineTts(config)
                    except Exception as exc:
                        raise VoiceError("Local speech model could not be loaded.") from exc
        return self._engine

    def unload_if_idle(self, idle_seconds: float) -> bool:
        """Free the speech model's RAM when unused for a while; it reloads on demand."""
        import time

        with self._lock, self._generate_lock:
            if self._engine is not None and time.monotonic() - self.last_used > idle_seconds:
                self._engine = None
                return True
        return False

    def synthesize(self, text: str, *, language: str = "auto", speaker_id: int | None = None,
                   num_steps: int | None = None) -> bytes:
        import time

        self.last_used = time.monotonic()
        clean = speakable(text)
        if not clean or len(clean) > 1000:
            raise VoiceError("Speech text must contain 1 to 1000 characters.")
        language_code = language.strip().lower()
        if language_code in {"", "auto"}:
            language_code = "hi" if re.search(r"[\u0900-\u097f]", clean) else "en"
        if language_code not in {"en", "hi"}:
            raise VoiceError("Local speech output currently supports English and Hindi.")
        try:
            import numpy as np
            import sherpa_onnx

            generation = sherpa_onnx.GenerationConfig()
            generation.sid = self.speaker_id if speaker_id is None else max(0, min(9, int(speaker_id)))
            generation.num_steps = self.num_steps if num_steps is None else max(1, min(16, int(num_steps)))
            generation.speed = 1.0
            generation.extra["lang"] = language_code
            engine = self._get_engine()
            # One generation at a time: the engine is not documented as thread-safe,
            # and sentence-pipelined playback sends several requests back to back.
            with self._generate_lock:
                audio = engine.generate(clean, generation)
            output = io.BytesIO()
            with wave.open(output, "wb") as writer:
                writer.setnchannels(1)
                writer.setsampwidth(2)
                writer.setframerate(audio.sample_rate)
                pcm = (np.clip(np.asarray(audio.samples, dtype=np.float32), -1.0, 1.0) * 32767).astype("<i2").tobytes()
                writer.writeframes(pcm)
            return output.getvalue()
        except VoiceError:
            raise
        except Exception as exc:
            raise VoiceError("Local speech synthesis failed.") from exc
