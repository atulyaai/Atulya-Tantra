"""Wake word detection with openWakeWord (ONNX backend; tflite is Linux-only)."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

WAKE_DIR = Path(__file__).resolve().parents[2] / "models" / "voice" / "wake"


def default_model() -> str:
    """ATULYA_WAKE_MODEL (a name in models/voice/wake or a path), else atulya.onnx once trained, else
    the interim hey_jarvis model (CC BY-NC-SA: personal testing only, never shipped as the default)."""
    chosen = os.environ.get("ATULYA_WAKE_MODEL", "").strip()
    if chosen:
        path = Path(chosen)
        return str(path if path.suffix else WAKE_DIR / f"{chosen}.onnx")
    custom = WAKE_DIR / "atulya.onnx"
    return str(custom if custom.is_file() else WAKE_DIR / "hey_jarvis_v0.1.onnx")


def _openwakeword_model(path: str):
    from openwakeword.model import Model

    return Model(wakeword_models=[path], inference_framework="onnx",
                 melspec_model_path=str(WAKE_DIR / "melspectrogram.onnx"),
                 embedding_model_path=str(WAKE_DIR / "embedding_model.onnx"))


class WakeDetector:
    """feed(80 ms int16 frame at 16 kHz) -> the score when it reaches the threshold, else None."""

    def __init__(self, model: str | None = None, *, threshold: float = 0.5, model_factory=_openwakeword_model) -> None:
        self.model_path = model or default_model()
        self.threshold = threshold
        self._model = model_factory(self.model_path)

    def feed(self, frame: np.ndarray) -> float | None:
        scores = self._model.predict(np.asarray(frame, dtype=np.int16).reshape(-1))
        score = max(scores.values()) if scores else 0.0
        return float(score) if score >= self.threshold else None

    def reset(self) -> None:
        """Clear the model's audio history, e.g. after our own speech, so it cannot re-trigger."""
        reset = getattr(self._model, "reset", None)
        if reset is not None:
            reset()
