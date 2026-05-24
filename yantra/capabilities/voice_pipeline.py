"""Voice Pipeline — TTS/STT for Hindi, English, Sanskrit. Free-first, CPU-based."""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


class AudioFormat(Enum):
    MP3 = "mp3"
    WAV = "wav"
    OGG = "ogg"


class VoiceGender(Enum):
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


@dataclass
class VoiceProfile:
    name: str
    gender: VoiceGender = VoiceGender.NEUTRAL
    language: str = "en"
    accent: str = ""
    speed: float = 1.0
    pitch: float = 1.0
    provider: str = ""
    voice_id: str = ""


@dataclass
class TTSResult:
    id: str
    audio_base64: str | None = None
    local_path: str | None = None
    duration: float = 0.0
    format: AudioFormat = AudioFormat.MP3
    cost: float = 0.0
    provider: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class STTResult:
    id: str
    text: str
    language: str = "en"
    confidence: float = 0.0
    duration: float = 0.0
    words: list[dict[str, Any]] = field(default_factory=list)
    provider: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class TextToSpeech:
    """TTS with edge-tts (free, Microsoft voices for Hindi/English/Sanskrit)."""

    VOICES = {
        "en_male": {"voice": "en-US-GuyNeural", "language": "en"},
        "en_female": {"voice": "en-US-JennyNeural", "language": "en"},
        "hi_male": {"voice": "hi-IN-MadhurNeural", "language": "hi"},
        "hi_female": {"voice": "hi-IN-SwaraNeural", "language": "hi"},
        "sa_male": {"voice": "sa-IN-Neural", "language": "sa"},
        "sa_female": {"voice": "sa-IN-Neural", "language": "sa"},
    }

    def __init__(self, output_dir: str | Path = "assets/audio"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._history: list[TTSResult] = []

    async def synthesize(
        self, text: str, voice: str = "en_male", speed: float = 1.0,
        format: AudioFormat = AudioFormat.MP3, save: bool = True,
    ) -> TTSResult:
        """Synthesize speech using edge-tts (free, no API key needed)."""
        try:
            import edge_tts
            voice_config = self.VOICES.get(voice, self.VOICES["en_male"])
            tts_voice = voice_config["voice"]
            rate = f"{int((speed - 1) * 100)}%"

            communicate = edge_tts.Communicate(text, tts_voice, rate=rate)
            audio_bytes = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]

            audio_b64 = base64.b64encode(audio_bytes).decode()
            result_id = hashlib.sha256(text.encode()).hexdigest()[:16]
            result = TTSResult(
                id=result_id, audio_base64=audio_b64, format=format,
                cost=0.0, provider="edge-tts",
                metadata={"voice": voice, "language": voice_config["language"]},
            )
            if save:
                result.local_path = self._save_audio(result)
            self._history.append(result)
            return result
        except ImportError:
            # Fallback: return text as-is with metadata
            return TTSResult(
                id=f"fallback_{hash(text)}", provider="fallback",
                metadata={"text": text, "voice": voice, "note": "edge-tts not installed"},
            )

    async def synthesize_streaming(
        self, text: str, voice: str = "en_male", speed: float = 1.0,
    ) -> AsyncIterator[bytes]:
        """Stream audio chunks."""
        import edge_tts
        voice_config = self.VOICES.get(voice, self.VOICES["en_male"])
        communicate = edge_tts.Communicate(text, voice_config["voice"], rate=f"{int((speed-1)*100)}%")
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    def _save_audio(self, result: TTSResult) -> str:
        if not result.audio_base64:
            return ""
        ext = result.format.value
        filepath = self.output_dir / f"{result.id}.{ext}"
        filepath.write_bytes(base64.b64decode(result.audio_base64))
        return str(filepath)

    def get_history(self, limit: int = 20) -> list[TTSResult]:
        return self._history[-limit:]

    def get_stats(self) -> dict[str, Any]:
        return {"total_synthesized": len(self._history), "total_cost": 0.0}


class SpeechToText:
    """STT using local whisper or OpenAI API."""

    def __init__(self, output_dir: str | Path = "assets/audio/transcripts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._history: list[STTResult] = []

    async def transcribe(
        self, audio_path: str | None = None, audio_base64: str | None = None,
        language: str = "en", model: str = "base",
    ) -> STTResult:
        """Transcribe audio to text."""
        if audio_base64 and not audio_path:
            audio_path = self._save_temp_audio(audio_base64)
        if not audio_path:
            return STTResult(id="error", text="", error="No audio provided")

        stt_result = STTResult(id="error", text="", error="Transcription failed")
        # Try local whisper first (free, CPU-based)
        try:
            import whisper
            whisp_model = whisper.load_model(model)
            result = whisp_model.transcribe(audio_path, language=language, word_timestamps=True)
            words = []
            for segment in result.get("segments", []):
                for word in segment.get("words", []):
                    words.append({"word": word.get("word", ""), "start": word.get("start", 0), "end": word.get("end", 0)})
            stt_result = STTResult(
                id=hashlib.sha256(result["text"].encode()).hexdigest()[:16],
                text=result["text"], language=language,
                confidence=result.get("confidence", 0.9), words=words, provider="whisper",
            )
        except ImportError:
            # Fallback: OpenAI API
            stt_result = await self._transcribe_openai(audio_path, language)

        self._history.append(stt_result)
        return stt_result

    async def _transcribe_openai(self, audio_path: str, language: str) -> STTResult:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
            with open(audio_path, "rb") as f:
                response = await client.audio.transcriptions.create(model="whisper-1", file=f, language=language)
            return STTResult(
                id=hashlib.sha256(response.text.encode()).hexdigest()[:16],
                text=response.text, language=language, provider="openai",
                metadata={"cost": 0.006},
            )
        except Exception as e:
            return STTResult(id="error", text="", provider="none", error=str(e), metadata={"error": "No STT available"})

    def _save_temp_audio(self, audio_base64: str) -> str:
        import tempfile
        audio_bytes = base64.b64decode(audio_base64)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            return f.name

    def get_stats(self) -> dict[str, Any]:
        return {"total_transcribed": len(self._history)}


class VoicePipeline:
    """Combined TTS/STT for full voice conversations."""

    def __init__(self, tts_dir: str = "assets/audio/tts", stt_dir: str = "assets/audio/stt"):
        self.tts = TextToSpeech(tts_dir)
        self.stt = SpeechToText(stt_dir)
        self._conversation: list[dict[str, Any]] = []

    async def voice_chat(
        self, audio_input: str | None = None, audio_base64: str | None = None,
        response_voice: str = "en_male", language: str = "en",
    ) -> dict[str, Any]:
        """Full voice chat: STT -> process -> TTS."""
        stt = await self.stt.transcribe(audio_path=audio_input, audio_base64=audio_base64, language=language)
        self._conversation.append({"role": "user", "text": stt.text, "timestamp": time.time()})
        # Process response (would call LLM in production)
        response_text = f"You said: {stt.text}"
        tts = await self.tts.synthesize(response_text, voice=response_voice)
        self._conversation.append({"role": "assistant", "text": response_text, "audio": tts.local_path, "timestamp": time.time()})
        return {"transcription": stt, "response_text": response_text, "response_audio": tts}

    def get_stats(self) -> dict[str, Any]:
        return {"tts": self.tts.get_stats(), "stt": self.stt.get_stats(), "turns": len(self._conversation)}
