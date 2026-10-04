"""Classify creation prompts into output formats."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Classification:
    format: str
    confidence: float
    matched_terms: list[str]


class OutputTypeClassifier:
    """Heuristic prompt classifier for creation requests."""

    KEYWORDS = {
        "video": ("video", "youtube", "reel", "voiceover", "narration"),
        "pptx": ("ppt", "pptx", "slides", "presentation", "deck"),
        "xlsx": ("xlsx", "excel", "spreadsheet", "workbook"),
        "docx": ("docx", "word document", "letter", "proposal"),
        "pdf": ("pdf", "report", "invoice", "whitepaper", "ebook"),
        "image": ("image", "poster", "thumbnail", "banner", "infographic"),
        "chart": ("chart", "graph", "plot", "visualization"),
        "audio": ("audio", "tts", "speech", "mp3", "voice"),
        "html": ("html", "web page"),
        "markdown": ("markdown", "readme", "notes"),
    }
    ALIASES = {
        "document": "pdf",
        "slides": "pptx",
        "presentation": "pptx",
        "spreadsheet": "xlsx",
        "picture": "image",
        "voice": "audio",
    }

    def normalize(self, format_name: str | None) -> str:
        value = (format_name or "auto").strip().lower().lstrip(".")
        return self.ALIASES.get(value, value)

    def detect(self, prompt: str, default: str = "markdown") -> Classification:
        text = " ".join(prompt.lower().split())
        best_format = default
        best_terms: list[str] = []
        for format_name, terms in self.KEYWORDS.items():
            matched = [term for term in terms if term in text]
            if len(matched) > len(best_terms):
                best_format, best_terms = format_name, matched
        confidence = min(0.95, 0.35 + 0.15 * len(best_terms)) if best_terms else 0.25
        return Classification(best_format, confidence, best_terms)
