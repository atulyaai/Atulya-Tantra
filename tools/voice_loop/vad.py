"""End-of-speech detection with Silero VAD (ONNX, via onnxruntime; no torch)."""
from __future__ import annotations

import io
import wave
from pathlib import Path
from typing import Callable

import numpy as np

RATE = 16000
CHUNK = 512  # Silero v4 at 16 kHz: one probability per 32 ms
MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "voice" / "wake" / "silero_vad.onnx"


class SileroVAD:
    """Speech probability for each 512-sample float32 chunk; keeps the recurrent state between calls."""

    def __init__(self, model_path: Path = MODEL_PATH) -> None:
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self._session = ort.InferenceSession(str(model_path), options, providers=["CPUExecutionProvider"])
        self.reset()

    def reset(self) -> None:
        self._h = np.zeros((2, 1, 64), dtype=np.float32)
        self._c = np.zeros((2, 1, 64), dtype=np.float32)

    def __call__(self, chunk: np.ndarray) -> float:
        out, self._h, self._c = self._session.run(None, {
            "input": chunk.reshape(1, -1).astype(np.float32), "sr": np.array(RATE, dtype=np.int64),
            "h": self._h, "c": self._c})
        return float(out[0][0])


class Endpointer:
    """Collects one utterance. feed(int16 frame) returns True once it is complete:
    `silence_ms` of silence after speech, `max_ms` in total, or `no_speech_ms` without any speech."""

    def __init__(self, probability: Callable[[np.ndarray], float], *, silence_ms: int = 600, max_ms: int = 8000,
                 no_speech_ms: int = 5000, threshold: float = 0.5) -> None:
        self.probability = probability
        self.silence_ms, self.max_ms, self.no_speech_ms = silence_ms, max_ms, no_speech_ms
        self.threshold = threshold
        self.reset()

    def reset(self) -> None:
        self._frames: list[np.ndarray] = []
        self._pending = np.zeros(0, dtype=np.float32)
        self.heard_speech = False
        self._silence_ms = 0.0
        self._total_ms = 0.0
        if hasattr(self.probability, "reset"):
            self.probability.reset()

    def feed(self, frame: np.ndarray) -> bool:
        frame = np.asarray(frame, dtype=np.int16).reshape(-1)
        self._frames.append(frame)
        self._total_ms += len(frame) * 1000 / RATE
        self._pending = np.concatenate([self._pending, frame.astype(np.float32) / 32768.0])
        while len(self._pending) >= CHUNK:
            chunk, self._pending = self._pending[:CHUNK], self._pending[CHUNK:]
            if self.probability(chunk) >= self.threshold:
                self.heard_speech = True
                self._silence_ms = 0.0
            elif self.heard_speech:
                self._silence_ms += CHUNK * 1000 / RATE
        if self.heard_speech and self._silence_ms >= self.silence_ms:
            return True
        if self._total_ms >= self.max_ms:
            return True
        return not self.heard_speech and self._total_ms >= self.no_speech_ms

    def wav(self) -> bytes:
        """The utterance as 16 kHz mono PCM16 WAV (the format LocalVoice reads without a temp file)."""
        out = io.BytesIO()
        with wave.open(out, "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(RATE)
            writer.writeframes(np.concatenate(self._frames).astype("<i2").tobytes() if self._frames else b"")
        return out.getvalue()
