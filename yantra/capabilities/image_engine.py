"""Fast SVG, image, and chart generation helpers."""
from __future__ import annotations

import html
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ImageResult:
    path: str
    format: str
    fallback: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")[:80] or "image"


class ImageEngine:
    def __init__(self, output_dir: str | Path = "assets/creations/images"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, prompt: str, format: str = "svg") -> ImageResult:
        fmt = format.lower().lstrip(".")
        return self.create_bitmap(prompt, fmt) if fmt in {"png", "jpg", "jpeg"} else self.create_svg(prompt)

    def create_svg(self, prompt: str, width: int = 1280, height: int = 720) -> ImageResult:
        title = (prompt.strip().splitlines() or ["Generated Visual"])[0][:80]
        path = self.output_dir / f"{_slug(title)}-{time.time_ns()}.svg"
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
<rect width="100%" height="100%" fill="#111827"/><rect x="64" y="64" width="{width - 128}" height="{height - 128}" rx="16" fill="#f8fafc"/>
<text x="104" y="170" font-family="Arial" font-size="52" font-weight="700" fill="#111827">{html.escape(title)}</text>
<foreignObject x="104" y="220" width="{width - 208}" height="{height - 300}"><div xmlns="http://www.w3.org/1999/xhtml" style="font:28px Arial;line-height:1.4;color:#334155">{html.escape(prompt[:300])}</div></foreignObject>
</svg>"""
        path.write_text(svg, encoding="utf-8")
        return ImageResult(str(path), "svg")

    def create_bitmap(self, prompt: str, format: str = "png") -> ImageResult:
        try:
            from PIL import Image, ImageDraw
            title = (prompt.strip().splitlines() or ["Generated Visual"])[0][:80]
            path = self.output_dir / f"{_slug(title)}-{time.time_ns()}.{format}"
            image = Image.new("RGB", (1280, 720), "#f8fafc")
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, 1280, 96), fill="#111827")
            draw.text((64, 36), title, fill="white")
            draw.multiline_text((64, 150), prompt[:500], fill="#1f2937", spacing=8)
            image.save(path)
            return ImageResult(str(path), format)
        except Exception as exc:
            result = self.create_svg(prompt)
            result.fallback = True
            result.metadata = {"requested": format, "error": str(exc)}
            return result

    def create_chart(self, data: list[dict[str, Any]], title: str = "Chart") -> ImageResult:
        try:
            import matplotlib.pyplot as plt
            path = self.output_dir / f"{_slug(title)}-{time.time_ns()}.png"
            labels = [str(row.get("label", index + 1)) for index, row in enumerate(data)]
            values = [float(row.get("value", 0)) for row in data]
            figure, axes = plt.subplots(figsize=(10, 5.625))
            axes.bar(labels, values, color="#0ea5e9")
            axes.set_title(title)
            figure.tight_layout()
            figure.savefig(path)
            plt.close(figure)
            return ImageResult(str(path), "png")
        except Exception as exc:
            path = self.output_dir / f"{_slug(title)}-{time.time_ns()}.json"
            path.write_text(json.dumps({"title": title, "data": data}, indent=2), encoding="utf-8")
            return ImageResult(str(path), "json", True, {"requested": "chart", "error": str(exc)})
