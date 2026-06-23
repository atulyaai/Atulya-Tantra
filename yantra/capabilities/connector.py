"""Universal non-model creation connector."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from yantra.capabilities.document_engine import DocumentEngine
from yantra.capabilities.image_engine import ImageEngine
from yantra.capabilities.output_classifier import OutputTypeClassifier
from yantra.capabilities.video_pipeline import VideoGenerator
from yantra.capabilities.voice_pipeline import AudioFormat, TextToSpeech


@dataclass
class CreationResult:
    format: str
    path: str = ""
    ok: bool = True
    fallback: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str = ""


class AtulyaTantraConnector:
    def __init__(self, output_dir: str | Path = "assets/creations"):
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        self.classifier = OutputTypeClassifier()
        self.documents = DocumentEngine(root / "documents")
        self.images = ImageEngine(root / "images")
        self.video = VideoGenerator(root / "videos")
        self.tts = TextToSpeech(root / "audio")

    def create(self, prompt: str, format: str = "auto", **kwargs: Any) -> CreationResult:
        fmt = self.classifier.normalize(format)
        classification = self.classifier.detect(prompt) if fmt == "auto" else None
        fmt = classification.format if classification else fmt
        try:
            if fmt in {"pdf", "docx", "pptx", "xlsx", "csv", "html", "markdown", "md"}:
                result = self.documents.create_from_prompt(prompt, "markdown" if fmt == "md" else fmt)
                return CreationResult(result.format, result.path, fallback=result.fallback, metadata=result.metadata)
            if fmt in {"image", "svg", "png", "jpg", "jpeg"}:
                result = self.images.generate(prompt, "svg" if fmt == "image" else fmt)
                return CreationResult(result.format, result.path, fallback=result.fallback, metadata=result.metadata)
            if fmt == "chart":
                result = self.images.create_chart(kwargs.get("data") or [{"label": "A", "value": 1}, {"label": "B", "value": 2}], prompt[:80])
                return CreationResult(result.format, result.path, fallback=result.fallback, metadata=result.metadata)
            if fmt == "video":
                result = self.video.generate(prompt, int(kwargs.get("duration_minutes", 10)), bool(kwargs.get("render", False)), str(kwargs.get("style", "educational")))
                return CreationResult("mp4" if result.rendered else "video_manifest", result.path, metadata=result.metadata)
            if fmt == "audio":
                result = asyncio.run(self.tts.synthesize(prompt, voice=str(kwargs.get("voice", "en_male")), speed=float(kwargs.get("speed", 1.0)), format=AudioFormat.MP3))
                return CreationResult("audio", result.local_path or "", fallback=result.provider == "fallback", metadata=result.metadata)
            result = self.documents.create_from_prompt(prompt, "markdown")
            return CreationResult(result.format, result.path, metadata={"classification": classification.__dict__ if classification else None})
        except Exception as exc:
            return CreationResult(fmt, ok=False, error=str(exc))

    def create_multi(self, prompt: str, formats: list[str]) -> list[CreationResult]:
        return [self.create(prompt, item) for item in formats]
