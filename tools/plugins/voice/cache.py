"""Disk cache for fixed acknowledgement speech, never personal answer text."""
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import tempfile
import wave
from pathlib import Path

from tools.plugins.brain.engine import _FILLERS, _INTENT_FILLERS
from .tts import LocalSupertonicTTS, TTS_MODEL_FILE_SHA256


ACKNOWLEDGEMENTS = frozenset({"Yes?", *(phrase.strip() for _, phrase in _INTENT_FILLERS),
                             *(phrase.strip() for phrase in _FILLERS.values() if phrase.strip())})
logger = logging.getLogger(__name__)


class CachedSpeech:
    def __init__(self, backend, cache_dir: Path):
        self.backend = backend
        self.cache_dir = cache_dir

    def __getattr__(self, name):
        return getattr(self.backend, name)

    def _path(self, text, language, speaker_id):
        text = text.strip()
        if text not in ACKNOWLEDGEMENTS or language not in {"auto", "", "en", "hi"}:
            return None
        sid = self.backend.speaker_id if speaker_id is None else max(0, min(9, int(speaker_id)))
        key = {"text": text, "language": "en" if language in {"", "auto"} else language,
               "speaker": sid, "steps": 8, "model": TTS_MODEL_FILE_SHA256, "format": 1}
        digest = hashlib.sha1(json.dumps(key, sort_keys=True).encode(), usedforsecurity=False).hexdigest()
        return self.cache_dir / f"{digest}.wav"

    def cached_audio(self, text, *, language="auto", speaker_id=None):
        path = self._path(text, language, speaker_id)
        if path is None:
            return None
        try:
            payload = path.read_bytes()
            with wave.open(io.BytesIO(payload)) as wav:
                if wav.getnframes() <= 0 or wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                    return None
                if len(wav.readframes(wav.getnframes())) != wav.getnframes() * 2:
                    return None
            return payload
        except (OSError, wave.Error, EOFError):
            return None

    def synthesize(self, text, *, language="auto", speaker_id=None, num_steps=None):
        cached = self.cached_audio(text, language=language, speaker_id=speaker_id)
        if cached is not None:
            return cached
        path = self._path(text, language, speaker_id)
        if path is None:
            extra = {"num_steps": num_steps} if num_steps is not None else {}
            return self.backend.synthesize(text, language=language, speaker_id=speaker_id, **extra)
        # Acknowledgements retain reference quality even if answer speech is configured differently.
        payload = self.backend.synthesize(text.strip(), language=language, speaker_id=speaker_id, num_steps=8)
        temporary = None
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=self.cache_dir, suffix=".wav", delete=False) as target:
                temporary = Path(target.name)
                target.write(payload)
            os.replace(temporary, path)
        except OSError:
            logger.info("Acknowledgement cache write failed; returning generated speech")
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
        return payload

    def warm_acknowledgements(self):
        for phrase in sorted(ACKNOWLEDGEMENTS):
            self.synthesize(phrase, language="en")


def cache_speech(backend, cache_dir: Path):
    return CachedSpeech(backend, cache_dir) if isinstance(backend, LocalSupertonicTTS) else backend
