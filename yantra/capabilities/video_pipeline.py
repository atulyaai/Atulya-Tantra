"""Slideshow video planning with optional MoviePy rendering."""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from yantra.capabilities.image_engine import ImageEngine


@dataclass
class VideoScene:
    title: str
    narration: str
    duration: float
    visual_path: str = ""


@dataclass
class VideoResult:
    path: str
    duration_minutes: float
    rendered: bool = False
    scenes: list[VideoScene] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class VideoGenerator:
    def __init__(self, output_dir: str | Path = "assets/creations/videos"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.images = ImageEngine(self.output_dir / "frames")

    def generate(self, prompt: str, duration_minutes: int = 10, render: bool = False, style: str = "educational") -> VideoResult:
        scenes = self._plan_scenes(prompt, duration_minutes)
        for scene in scenes:
            scene.visual_path = self.images.create_svg(f"{scene.title}\n{scene.narration}").path
        if render:
            rendered = self._render(scenes)
            if rendered:
                return VideoResult(rendered, duration_minutes, True, scenes, {"style": style})
        path = self.output_dir / f"video-plan-{time.time_ns()}.json"
        path.write_text(json.dumps({"prompt": prompt, "style": style, "duration_minutes": duration_minutes, "scenes": [asdict(s) for s in scenes]}, indent=2), encoding="utf-8")
        return VideoResult(str(path), duration_minutes, False, scenes, {"style": style, "note": "manifest fallback"})

    @staticmethod
    def _plan_scenes(prompt: str, duration_minutes: int) -> list[VideoScene]:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", prompt) if s.strip()] or [prompt.strip() or "Generated video"]
        count = max(3, min(30, duration_minutes * 3))
        return [VideoScene(sentences[0][:64] if i == 0 else f"Scene {i + 1}", sentences[i % len(sentences)], duration_minutes * 60 / count) for i in range(count)]

    def _render(self, scenes: list[VideoScene]) -> str:
        try:
            from moviepy.editor import ImageClip, concatenate_videoclips
            clips = [ImageClip(scene.visual_path).set_duration(scene.duration) for scene in scenes]
            video = concatenate_videoclips(clips, method="compose")
            path = self.output_dir / f"video-{time.time_ns()}.mp4"
            video.write_videofile(str(path), fps=24, codec="libx264", preset="ultrafast", audio=False)
            return str(path)
        except Exception:
            return ""
