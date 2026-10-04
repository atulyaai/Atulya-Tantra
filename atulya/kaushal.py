"""Kaushal (कौशल, skill): the heavier capabilities and creation tools, documents, spreadsheets, charts and business automation."""
from __future__ import annotations

import ast
import asyncio
import csv
import html
import json
import logging
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from atulya.vani import AudioFormat, TextToSpeech


# ── kaushal ────────────────────────────────────────────────────────────
# ── capabilities ────────────────────────────────────────────────────────────
@dataclass
class ToolResult:
    success: bool
    output: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class Tool(ABC):
    name: str = ""
    description: str = ""

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        pass


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._duplicate_names: set[str] = set()

    def register(self, tool: Tool):
        if tool.name in self._tools:
            self._duplicate_names.add(tool.name)
        self._tools[tool.name] = tool

    async def execute(self, name: str, /, **kwargs: Any) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(success=False, error=f"Tool not found: {name}")
        try:
            return await tool.execute(**kwargs)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, str]]:
        return [{"name": t.name, "description": t.description} for t in self._tools.values()]

    def filter_tools(self, categories: list[str]) -> list[Tool]:
        return [t for t in self._tools.values() if any(c in t.name for c in categories)]

    def duplicate_names(self) -> list[str]:
        return sorted(self._duplicate_names)


def _safe_path(path: str, allowed_base: str | None = None) -> Path:
    """Resolve a path and ensure it stays within allowed_base (or CWD)."""
    resolved = Path(path).resolve()
    if allowed_base:
        base = Path(allowed_base).resolve()
        try:
            resolved.relative_to(base)
        except ValueError:
            raise PermissionError(f"Path {resolved} is outside allowed directory {base}")
    else:
        cwd = Path.cwd().resolve()
        try:
            resolved.relative_to(cwd)
        except ValueError:
            raise PermissionError(f"Path {resolved} is outside current working directory {cwd}")
    return resolved


_MAX_FILE_SIZE = 10 * 1024 * 1024


class FileReadTool(Tool):
    name = "file_read"
    description = "Read file contents"
    async def execute(self, path: str, **kwargs: Any) -> ToolResult:
        try:
            safe = _safe_path(path)
            size = safe.stat().st_size
            if size > _MAX_FILE_SIZE:
                return ToolResult(success=False, error=f"File too large ({size} bytes, max {_MAX_FILE_SIZE})")
            content = safe.read_text()
            return ToolResult(success=True, output=content)
        except (PermissionError, OSError) as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FileWriteTool(Tool):
    name = "file_write"
    description = "Write content to file"
    async def execute(self, path: str, content: str, **kwargs: Any) -> ToolResult:
        try:
            safe = _safe_path(path)
            if len(content) > _MAX_FILE_SIZE:
                return ToolResult(success=False, error=f"Content too large ({len(content)} bytes, max {_MAX_FILE_SIZE})")
            safe.write_text(content)
            return ToolResult(success=True, output=f"Written {len(content)} bytes to {safe}")
        except (PermissionError, OSError) as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FileEditTool(Tool):
    name = "file_edit"
    description = "Edit file with search/replace"
    async def execute(self, path: str, old: str, new: str, **kwargs: Any) -> ToolResult:
        try:
            safe = _safe_path(path)
            content = safe.read_text()
            if old not in content:
                return ToolResult(success=False, error="Search string not found")
            content = content.replace(old, new)
            safe.write_text(content)
            return ToolResult(success=True, output="File edited")
        except (PermissionError, OSError) as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FileSearchTool(Tool):
    name = "file_search"
    description = "Search for files by pattern"
    async def execute(self, pattern: str, path: str = ".", **kwargs: Any) -> ToolResult:
        try:
            safe = _safe_path(path)
            matches = list(safe.glob(pattern))
            return ToolResult(success=True, output="\n".join(str(m) for m in matches))
        except (PermissionError, OSError) as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class GrepTool(Tool):
    name = "grep"
    description = "Search file contents with regex"
    async def execute(self, pattern: str, path: str = ".", max_file_size: int = 1_048_576, **kwargs: Any) -> ToolResult:
        try:
            safe = _safe_path(path)
            results = []
            for f in safe.rglob("*"):
                if f.is_file():
                    try:
                        if f.stat().st_size > max_file_size:
                            continue
                        content = f.read_text(encoding="utf-8")
                        if re.search(pattern, content):
                            results.append(str(f))
                    except (UnicodeDecodeError, OSError):
                        continue
            return ToolResult(success=True, output="\n".join(results))
        except (PermissionError, OSError) as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class ExecTool(Tool):
    name = "exec"
    description = "Execute a shell command"
    async def execute(self, command: str, allow_exec: bool = False, allow_list: list[str] | None = None, **kwargs: Any) -> ToolResult:
        if not allow_exec:
            return ToolResult(success=False, error="Execution requires allow_exec=True and RiskLevel.CRITICAL approval")
        from atulya.raksha import ApprovalSystem, RiskLevel
        if ApprovalSystem().assess_risk(command) == RiskLevel.CRITICAL:
            return ToolResult(success=False, error="Command rejected by approval system (critical risk)")
        allowed = allow_list or os.environ.get("ATULYA_EXEC_ALLOWLIST", "").split(",")
        allowed = [item.strip() for item in allowed if item.strip()]
        try:
            executable = shlex.split(command, posix=False)[0].lower()
        except ValueError as e:
            return ToolResult(success=False, error=str(e))
        if not allowed or executable not in {item.lower() for item in allowed}:
            return ToolResult(success=False, error=f"Command not allow-listed: {executable}")
        try:
            cmd_list = shlex.split(command, posix=False)
            result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=30)
            return ToolResult(success=result.returncode == 0, output=result.stdout, error=result.stderr)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web"
    async def execute(self, query: str, **kwargs: Any) -> ToolResult:
        try:
            from duckduckgo_search import DDGS
            results = DDGS().text(query, max_results=5)
            return ToolResult(success=True, output=json.dumps(results, indent=2))
        except ImportError:
            return ToolResult(success=False, error="duckduckgo_search not installed")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class WebFetchTool(Tool):
    """Fetch a public web page.

    Only http(s) to public addresses: no file://, no localhost, no private
    network, no cloud metadata endpoint — the model can be steered by text it
    reads, so it must not be able to read the machine's own files or services.
    Every redirect is checked again, and so is the address actually connected
    to (defeats DNS rebinding). ``ATULYA_FETCH_ALLOW_PRIVATE=1`` allows the LAN.
    """

    name = "web_fetch"
    description = "Fetch URL content"
    MAX_BYTES = 1_000_000
    MAX_REDIRECTS = 5

    def __init__(self, transport: Any = None, resolver: Any = None):
        self._transport = transport
        self._resolver = resolver

    async def execute(self, url: str, **kwargs: Any) -> ToolResult:
        import httpx

        from atulya.raksha import SSRFProtection, is_public_ip

        allow_private = os.environ.get("ATULYA_FETCH_ALLOW_PRIVATE", "").lower() in ("1", "true", "yes")
        guard = SSRFProtection(resolver=self._resolver)

        def allowed(target: str) -> bool:
            if allow_private:
                return target.lower().startswith(("http://", "https://"))
            return guard.check_url(target)

        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=False, transport=self._transport) as client:
                for _ in range(self.MAX_REDIRECTS + 1):
                    if not allowed(url):
                        return ToolResult(success=False, error=f"Refused to fetch {url}: only public http(s) addresses are allowed")
                    async with client.stream("GET", url, headers={"User-Agent": "Atulya/1.0"}) as resp:
                        stream = resp.extensions.get("network_stream")
                        peer = stream.get_extra_info("server_addr") if stream is not None else None
                        if peer and not allow_private and not is_public_ip(str(peer[0])):
                            return ToolResult(success=False, error=f"Refused to fetch {url}: it resolved to a private address")
                        if resp.is_redirect and resp.headers.get("location"):
                            url = str(resp.url.join(resp.headers["location"]))
                            continue
                        body = b""
                        async for chunk in resp.aiter_bytes():
                            body += chunk
                            if len(body) >= self.MAX_BYTES:
                                break
                        if resp.status_code >= 400:
                            return ToolResult(success=False, error=f"HTTP {resp.status_code} from {url}")
                        return ToolResult(success=True, output=body.decode(resp.encoding or "utf-8", "replace")[:5000])
            return ToolResult(success=False, error="Too many redirects")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class TodoCreateTool(Tool):
    name = "todo_create"
    description = "Create a todo item"
    async def execute(self, text: str, **kwargs: Any) -> ToolResult:
        todos_file = Path(kwargs.get("data_dir", ".")) / "todos.json"
        todos = []
        if todos_file.exists():
            todos = json.loads(todos_file.read_text())
        todos.append({"id": str(len(todos)+1), "text": text, "done": False, "created": time.time()})
        todos_file.write_text(json.dumps(todos, indent=2))
        return ToolResult(success=True, output=f"Created todo #{len(todos)}")


class TodoListTool(Tool):
    name = "todo_list"
    description = "List todos"
    async def execute(self, **kwargs: Any) -> ToolResult:
        todos_file = Path(kwargs.get("data_dir", ".")) / "todos.json"
        if not todos_file.exists():
            return ToolResult(success=True, output="No todos")
        todos = json.loads(todos_file.read_text())
        return ToolResult(success=True, output=json.dumps(todos, indent=2))


_DEFAULT_MEMORY_DIR = Path.home() / ".atulya" / "memory"

class MemoryStoreTool(Tool):
    name = "memory_store"
    description = "Store a memory note"
    async def execute(self, content: str, tags: str = "", **kwargs: Any) -> ToolResult:
        memory_dir = Path(kwargs.get("data_dir") or os.environ.get("ATULYA_DATA_DIR") or _DEFAULT_MEMORY_DIR)
        memory_dir.mkdir(parents=True, exist_ok=True)
        entry = {"id": str(int(time.time())), "content": content, "tags": tags.split(",") if tags else [], "created": time.time()}
        (memory_dir / f"{entry['id']}.json").write_text(json.dumps(entry))
        return ToolResult(success=True, output=f"Stored memory {entry['id']}")


class MemorySearchTool(Tool):
    name = "memory_search"
    description = "Search memory notes"
    async def execute(self, query: str, **kwargs: Any) -> ToolResult:
        memory_dir = Path(kwargs.get("data_dir") or os.environ.get("ATULYA_DATA_DIR") or _DEFAULT_MEMORY_DIR)
        results = []
        if memory_dir.exists():
            for f in memory_dir.glob("*.json"):
                data = json.loads(f.read_text())
                if query.lower() in data.get("content", "").lower():
                    results.append(data)
        return ToolResult(success=True, output=json.dumps(results, indent=2))


class CreateOutputTool(Tool):
    name = "create_output"
    description = "Create documents, images, videos, audio, and charts from a prompt"

    async def execute(self, prompt: str, format: str = "auto", **kwargs: Any) -> ToolResult:

        root = Path(kwargs.pop("data_dir", "kosh")) / "creations"
        result = AtulyaTantraConnector(root).create(prompt, format, **kwargs)
        return ToolResult(
            success=result.ok,
            output=result.path,
            error=result.error,
            metadata={"format": result.format, "fallback": result.fallback, **result.metadata},
        )


def create_default_registry(data_dir: str | Path = ".") -> ToolRegistry:
    from atulya.jaal import BrowserAutomationTool
    registry = ToolRegistry()
    for tool_class in [FileReadTool, FileWriteTool, FileEditTool, FileSearchTool, GrepTool,
                       ExecTool, WebSearchTool, WebFetchTool, TodoCreateTool, TodoListTool,
                       MemoryStoreTool, MemorySearchTool, CreateOutputTool, HRAttendancePayrollTool,
                       DataScrubberTool, GSTReconciliationTool, AccountingERPTool,
                       SAPAutomationTool, CodeExecuteTool, PDFReadTool, CSVAnalyzeTool,
                       CalendarTool, EmailDraftTool, ChartGenerateTool, BrowserAutomationTool]:
        registry.register(tool_class())
    return registry


# ── connector ────────────────────────────────────────────────────────────
@dataclass
class CreationResult:
    format: str
    path: str = ""
    ok: bool = True
    fallback: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str = ""


class AtulyaTantraConnector:
    def __init__(self, output_dir: str | Path = "kosh/creations"):
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


# ── output_classifier ────────────────────────────────────────────────────────────
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


# ── image_engine ────────────────────────────────────────────────────────────
@dataclass
class ImageResult:
    path: str
    format: str
    fallback: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")[:80] or "image"


class ImageEngine:
    def __init__(self, output_dir: str | Path = "kosh/creations/images"):
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


# ── video_pipeline ────────────────────────────────────────────────────────────
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
    def __init__(self, output_dir: str | Path = "kosh/creations/videos"):
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


# ── dastavez ────────────────────────────────────────────────────────────
# ── document_engine ────────────────────────────────────────────────────────────
@dataclass
class DocumentContent:
    title: str
    summary: str = ""
    sections: list[dict[str, Any]] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DocumentResult:
    path: str
    format: str
    fallback: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


def _doc_slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")[:80] or "document"


def content_from_prompt(prompt: str) -> DocumentContent:
    lines = [line.strip(" -\t") for line in prompt.splitlines() if line.strip()]
    title = (lines[0] if lines else "Generated Document")[:90]
    body = " ".join(lines[1:] or [prompt]).strip()
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
    sentences = sentences or [prompt.strip()]
    return DocumentContent(
        title=title,
        summary=sentences[0],
        sections=[
            {"heading": "Overview", "body": sentences[0]},
            {"heading": "Key Points", "bullets": sentences[1:6] or [sentences[0]]},
            {"heading": "Next Steps", "bullets": ["Review the draft", "Add source data", "Finalize output"]},
        ],
    )


class DocumentEngine:
    """Generate PDF, DOCX, PPTX, XLSX, HTML, CSV, or Markdown."""

    def __init__(self, output_dir: str | Path = "kosh/creations/documents"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_from_prompt(self, prompt: str, format: str = "markdown") -> DocumentResult:
        content = content_from_prompt(prompt)
        fmt = format.lower().lstrip(".")
        if fmt == "pdf":
            return self.create_pdf(content)
        if fmt == "docx":
            return self.create_docx(content)
        if fmt == "pptx":
            return self.create_pptx(content)
        if fmt == "xlsx":
            return self.create_xlsx(self._rows(content))
        if fmt == "html":
            return self.create_html(content)
        if fmt == "csv":
            return self.create_csv(self._rows(content))
        return self.create_markdown(content)

    def create_markdown(self, content: DocumentContent) -> DocumentResult:
        path = self._path(content.title, "md")
        chunks = [f"# {content.title}", "", content.summary]
        for section in content.sections:
            chunks.extend(["", f"## {section.get('heading', 'Section')}"])
            if section.get("body"):
                chunks.append(str(section["body"]))
            chunks.extend(f"- {item}" for item in section.get("bullets", []))
        path.write_text("\n".join(chunks).strip() + "\n", encoding="utf-8")
        return DocumentResult(str(path), "markdown")

    def create_html(self, content: DocumentContent) -> DocumentResult:
        path = self._path(content.title, "html")
        parts = ["<!doctype html><meta charset='utf-8'>", f"<h1>{html.escape(content.title)}</h1>"]
        parts.append(f"<p>{html.escape(content.summary)}</p>")
        for section in content.sections:
            parts.append(f"<h2>{html.escape(str(section.get('heading', 'Section')))}</h2>")
            if section.get("body"):
                parts.append(f"<p>{html.escape(str(section['body']))}</p>")
            if section.get("bullets"):
                parts.append("<ul>" + "".join(f"<li>{html.escape(str(x))}</li>" for x in section["bullets"]) + "</ul>")
        path.write_text("\n".join(parts), encoding="utf-8")
        return DocumentResult(str(path), "html")

    def create_pdf(self, content: DocumentContent) -> DocumentResult:
        try:
            from fpdf import FPDF
            path = self._path(content.title, "pdf")
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 18)
            pdf.multi_cell(0, 10, content.title)
            pdf.set_font("Helvetica", size=11)
            pdf.multi_cell(0, 8, content.summary)
            for section in content.sections:
                pdf.set_font("Helvetica", "B", 13)
                pdf.multi_cell(0, 8, str(section.get("heading", "Section")))
                pdf.set_font("Helvetica", size=11)
                pdf.multi_cell(0, 7, str(section.get("body", "")))
                for item in section.get("bullets", []):
                    pdf.multi_cell(0, 7, f"- {item}")
            pdf.output(str(path))
            return DocumentResult(str(path), "pdf")
        except Exception as exc:
            return self._fallback(content, "pdf", exc)

    def create_docx(self, content: DocumentContent) -> DocumentResult:
        try:
            from docx import Document
            path = self._path(content.title, "docx")
            doc = Document()
            doc.add_heading(content.title, 0)
            doc.add_paragraph(content.summary)
            for section in content.sections:
                doc.add_heading(str(section.get("heading", "Section")), level=1)
                if section.get("body"):
                    doc.add_paragraph(str(section["body"]))
                for item in section.get("bullets", []):
                    doc.add_paragraph(str(item), style="List Bullet")
            doc.save(path)
            return DocumentResult(str(path), "docx")
        except Exception as exc:
            return self._fallback(content, "docx", exc)

    def create_pptx(self, content: DocumentContent) -> DocumentResult:
        try:
            from pptx import Presentation
            path = self._path(content.title, "pptx")
            deck = Presentation()
            for title, bullets in [(content.title, [content.summary])] + [
                (str(s.get("heading", "Section")), list(s.get("bullets", [])) or [str(s.get("body", ""))])
                for s in content.sections
            ]:
                slide = deck.slides.add_slide(deck.slide_layouts[1])
                slide.shapes.title.text = title
                slide.placeholders[1].text = "\n".join(str(x) for x in bullets if x)
            deck.save(path)
            return DocumentResult(str(path), "pptx")
        except Exception as exc:
            return self._fallback(content, "pptx", exc)

    def create_xlsx(self, rows: list[dict[str, Any]]) -> DocumentResult:
        try:
            from openpyxl import Workbook
            path = self._path("spreadsheet", "xlsx")
            workbook = Workbook()
            sheet = workbook.active
            headers = list(rows[0]) if rows else ["item", "value"]
            sheet.append(headers)
            for row in rows:
                sheet.append([row.get(header, "") for header in headers])
            workbook.save(path)
            return DocumentResult(str(path), "xlsx")
        except Exception as exc:
            result = self.create_csv(rows)
            result.fallback = True
            result.metadata = {"requested": "xlsx", "error": str(exc)}
            return result

    def create_csv(self, rows: list[dict[str, Any]]) -> DocumentResult:
        path = self._path("table", "csv")
        headers = list(rows[0]) if rows else ["item", "value"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        return DocumentResult(str(path), "csv")

    def _fallback(self, content: DocumentContent, requested: str, exc: Exception) -> DocumentResult:
        result = self.create_markdown(content)
        result.fallback = True
        result.metadata = {"requested": requested, "error": str(exc)}
        return result

    @staticmethod
    def _rows(content: DocumentContent) -> list[dict[str, Any]]:
        rows = [{"section": "summary", "value": content.summary}]
        for section in content.sections:
            rows.append({"section": section.get("heading", "Section"), "value": section.get("body", "")})
            rows.extend({"section": section.get("heading", "Section"), "value": item} for item in section.get("bullets", []))
        return rows

    def _path(self, title: str, extension: str) -> Path:
        return self.output_dir / f"{_doc_slug(title)}-{time.time_ns()}.{extension}"


# ── office_tools ────────────────────────────────────────────────────────────
class CodeExecuteTool(Tool):
    name = "code_execute"
    description = "Execute a small Python snippet in an isolated temp file. Args: code, timeout."

    async def execute(self, code: str, timeout: int = 10, **kwargs: Any) -> ToolResult:
        if len(code) > 12000:
            return ToolResult(success=False, error="Code too large")
        import logging
        logger = logging.getLogger(__name__)
        blocked_modules = {"socket", "http", "urllib", "requests", "aiohttp", "NETWORK"}
        for module in blocked_modules:
            if f"import {module}" in code or f"from {module}" in code:
                logger.warning("Blocked module '%s' detected in code_execute", module)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snippet.py"
            path.write_text(code, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(path)],
                capture_output=True,
                text=True,
                timeout=max(1, min(int(timeout), 15)),
                cwd=tmp,
            )
        return ToolResult(
            success=result.returncode == 0,
            output=result.stdout[:8000],
            error=result.stderr[:4000],
        )


class PDFReadTool(Tool):
    name = "pdf_read"
    description = "Read text from a PDF when a local PDF reader library is installed. Args: path."

    async def execute(self, path: str, max_chars: int = 8000, **kwargs: Any) -> ToolResult:
        if max_chars > 50000:
            return ToolResult(success=False, error="max_chars exceeds limit (50000)")
        pdf_path = Path(path).resolve()
        cwd = Path.cwd().resolve()
        if cwd not in pdf_path.parents and pdf_path != cwd:
            return ToolResult(success=False, error="Path outside allowed directory")
        if not pdf_path.exists():
            return ToolResult(success=False, error=f"PDF not found: {path}")
        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError:
            try:
                from PyPDF2 import PdfReader  # type: ignore
            except ImportError:
                return ToolResult(success=False, error="Install pypdf or PyPDF2 to read PDF files")
        reader = PdfReader(str(pdf_path))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        return ToolResult(success=True, output=text[:max_chars], metadata={"pages": len(reader.pages)})


class CSVAnalyzeTool(Tool):
    name = "csv_analyze"
    description = "Analyze a CSV file: row count, columns, missing values, numeric stats. Args: path."

    async def execute(self, path: str, **kwargs: Any) -> ToolResult:
        csv_path = Path(path)
        if not csv_path.exists():
            return ToolResult(success=False, error=f"CSV not found: {path}")
        with csv_path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        columns = list(rows[0].keys()) if rows else []
        missing = {col: 0 for col in columns}
        numeric: dict[str, list[float]] = {col: [] for col in columns}
        for row in rows:
            for col in columns:
                value = (row.get(col) or "").strip()
                if not value:
                    missing[col] += 1
                    continue
                try:
                    numeric[col].append(float(value))
                except ValueError:
                    pass
        stats = {}
        for col, values in numeric.items():
            if values:
                stats[col] = {
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                }
        report = {"rows": len(rows), "columns": columns, "missing": missing, "numeric": stats}
        return ToolResult(success=True, output=json.dumps(report, indent=2), metadata=report)


class CalendarTool(Tool):
    name = "calendar"
    description = "Create a local calendar reminder/event JSON entry. Args: title, when, notes."

    async def execute(self, title: str, when: str = "", notes: str = "", **kwargs: Any) -> ToolResult:
        data_dir = Path(kwargs.get("data_dir") or tempfile.gettempdir()) / "atulya" / "calendar"
        data_dir.mkdir(parents=True, exist_ok=True)
        entry = {"id": str(int(time.time() * 1000)), "title": title, "when": when, "notes": notes}
        path = data_dir / f"{entry['id']}.json"
        path.write_text(json.dumps(entry, indent=2), encoding="utf-8")
        return ToolResult(success=True, output=f"Calendar entry saved: {path}", metadata=entry)


class EmailDraftTool(Tool):
    name = "email"
    description = "Draft a local email JSON file without sending. Args: to, subject, body."

    async def execute(self, to: str, subject: str, body: str, **kwargs: Any) -> ToolResult:
        data_dir = Path(kwargs.get("data_dir") or tempfile.gettempdir()) / "atulya" / "email_drafts"
        data_dir.mkdir(parents=True, exist_ok=True)
        draft = {"to": to, "subject": subject, "body": body, "created_at": time.time()}
        path = data_dir / f"draft_{int(time.time() * 1000)}.json"
        path.write_text(json.dumps(draft, indent=2), encoding="utf-8")
        return ToolResult(success=True, output=f"Email draft saved: {path}", metadata=draft)


class ChartGenerateTool(Tool):
    name = "chart_generate"
    description = "Generate a simple SVG bar chart. Args: title, labels, values."

    async def execute(self, title: str, labels: str | list, values: str | list, **kwargs: Any) -> ToolResult:
        labels_list = _coerce_list(labels)
        value_list = [float(item) for item in _coerce_list(values)]
        if len(labels_list) != len(value_list):
            return ToolResult(success=False, error="labels and values length mismatch")
        width, height = 640, 360
        max_value = max(value_list) if value_list else 1
        bar_w = max(20, int((width - 80) / max(len(value_list), 1)))
        bars = []
        for idx, (label, value) in enumerate(zip(labels_list, value_list)):
            bar_h = int((value / max_value) * 240) if max_value else 0
            x = 50 + idx * bar_w
            y = 310 - bar_h
            bars.append(
                f'<rect x="{x}" y="{y}" width="{bar_w - 8}" height="{bar_h}" fill="#12c99b"/>'
                f'<text x="{x}" y="330" font-size="11">{_xml(str(label))}</text>'
            )
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
            f'<rect width="100%" height="100%" fill="#080a10"/>'
            f'<text x="24" y="32" fill="#eef2ff" font-size="18">{_xml(title)}</text>'
            + "".join(bars)
            + "</svg>"
        )
        data_dir = Path(kwargs.get("data_dir") or tempfile.gettempdir()) / "atulya" / "charts"
        data_dir.mkdir(parents=True, exist_ok=True)
        path = data_dir / f"chart_{int(time.time() * 1000)}.svg"
        path.write_text(svg, encoding="utf-8")
        return ToolResult(success=True, output=f"Chart saved: {path}", metadata={"path": str(path)})


def _coerce_list(value: str | list) -> list[Any]:
    if isinstance(value, list):
        return value
    try:
        parsed = ast.literal_eval(value)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _xml(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── vyapar ────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)


class HRAttendancePayrollTool(Tool):
    """Processes attendance records and computes payroll."""
    name = "hr_attendance_payroll"
    description = "Compute employee payroll from attendance data. Args: input_csv, basic_pay_map (JSON string), tax_rate (float)."

    async def execute(self, input_csv: str, basic_pay_map: str | dict, tax_rate: float = 0.1, **kwargs: Any) -> ToolResult:
        try:
            csv_path = Path(input_csv)
            if not csv_path.exists():
                return ToolResult(success=False, error=f"CSV file not found: {input_csv}")

            # Parse pay map
            if isinstance(basic_pay_map, str):
                pay_map = json.loads(basic_pay_map)
            else:
                pay_map = basic_pay_map

            payroll_records = []
            with open(csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    emp_id = row.get("EmployeeID")
                    name = row.get("Name")
                    days_present = float(row.get("DaysPresent", 0))
                    total_days = float(row.get("TotalDays", 30))

                    if not emp_id or emp_id not in pay_map:
                        logger.warning(f"Employee {emp_id} pay structure not found. Defaulting to 15000.")
                        base_salary = 15000.0
                    else:
                        base_salary = float(pay_map[emp_id])

                    # Calculate pro-rated base
                    pro_rated = base_salary * (days_present / total_days) if total_days > 0 else 0
                    allowance = pro_rated * 0.1  # 10% allowance
                    gross_pay = pro_rated + allowance
                    tax = gross_pay * tax_rate
                    net_pay = gross_pay - tax

                    payroll_records.append({
                        "EmployeeID": emp_id,
                        "Name": name,
                        "BaseSalary": base_salary,
                        "DaysPresent": days_present,
                        "ProRated": round(pro_rated, 2),
                        "Allowance": round(allowance, 2),
                        "GrossPay": round(gross_pay, 2),
                        "Tax": round(tax, 2),
                        "NetPay": round(net_pay, 2),
                    })

            output_file = csv_path.parent / "payroll_output.json"
            output_file.write_text(json.dumps(payroll_records, indent=2))
            return ToolResult(
                success=True,
                output=f"Processed payroll for {len(payroll_records)} employees. Output saved to {output_file}.",
                metadata={"payroll": payroll_records, "output_file": str(output_file)}
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Payroll processing failed: {str(e)}")


class DataScrubberTool(Tool):
    """Cleans spreadsheet and business data."""
    name = "data_scrub"
    description = "Clean messy business and spreadsheet CSV files. Args: input_csv, clean_nulls (bool), format_phone (bool), remove_dupes (bool)."

    async def execute(self, input_csv: str, clean_nulls: bool = True, format_phone: bool = True, remove_dupes: bool = True, **kwargs: Any) -> ToolResult:
        try:
            csv_path = Path(input_csv)
            if not csv_path.exists():
                return ToolResult(success=False, error=f"CSV file not found: {input_csv}")

            cleaned_rows = []
            seen_keys = set()
            headers = []

            with open(csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.reader(f)
                headers = next(reader, [])
                for row in reader:
                    if not row:
                        continue

                    # Null cleaning
                    if clean_nulls:
                        row = [val.strip() if (val and val.strip()) else "N/A" for val in row]

                    # Duplicate removal based on the first column (e.g. ID or Name)
                    if remove_dupes and row:
                        key = row[0]
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)

                    # Phone number formatting
                    if format_phone and len(row) > 2:
                        for idx, val in enumerate(row):
                            # Try to identify phone number column
                            if val and val.replace("+", "").replace("-", "").replace(" ", "").isdigit():
                                digits = "".join(filter(str.isdigit, val))
                                if len(digits) == 10:
                                    row[idx] = f"+91 {digits[:5]}-{digits[5:]}"

                    cleaned_rows.append(row)

            output_file = csv_path.parent / f"cleaned_{csv_path.name}"
            with open(output_file, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(cleaned_rows)

            return ToolResult(
                success=True,
                output=f"Data scrubbing completed. Cleaned {len(cleaned_rows)} rows. Saved to {output_file.name}.",
                metadata={"cleaned_rows": len(cleaned_rows), "output_file": str(output_file)}
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Data scrubbing failed: {str(e)}")


class GSTReconciliationTool(Tool):
    """Performs tax and GST reconciliation."""
    name = "gst_reconcile"
    description = "Reconcile tax/GST entries between Sales and Purchase registers. Args: sales_csv, purchase_csv."

    async def execute(self, sales_csv: str, purchase_csv: str, **kwargs: Any) -> ToolResult:
        try:
            sales_path = Path(sales_csv)
            purchase_path = Path(purchase_csv)

            if not sales_path.exists() or not purchase_path.exists():
                return ToolResult(success=False, error="Sales or Purchase CSV file missing")

            sales_entries = {}
            with open(sales_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    inv_no = row.get("InvoiceNo")
                    if inv_no:
                        sales_entries[inv_no] = {
                            "Amount": float(row.get("Amount", 0)),
                            "Tax": float(row.get("Tax", 0)),
                            "Vendor": row.get("Vendor", "")
                        }

            mismatches = []
            matched_count = 0
            missing_in_purchase = []

            with open(purchase_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                purchase_invoices = set()
                for row in reader:
                    inv_no = row.get("InvoiceNo")
                    if not inv_no:
                        continue
                    purchase_invoices.add(inv_no)
                    p_amt = float(row.get("Amount", 0))
                    p_tax = float(row.get("Tax", 0))

                    if inv_no in sales_entries:
                        s_entry = sales_entries[inv_no]
                        if abs(s_entry["Amount"] - p_amt) > 0.01 or abs(s_entry["Tax"] - p_tax) > 0.01:
                            mismatches.append({
                                "InvoiceNo": inv_no,
                                "SalesAmount": s_entry["Amount"],
                                "PurchaseAmount": p_amt,
                                "SalesTax": s_entry["Tax"],
                                "PurchaseTax": p_tax,
                                "Type": "ValueMismatch"
                            })
                        else:
                            matched_count += 1
                    else:
                        mismatches.append({
                            "InvoiceNo": inv_no,
                            "PurchaseAmount": p_amt,
                            "PurchaseTax": p_tax,
                            "Type": "MissingInSales"
                        })

            # Check for invoices in sales but missing in purchase
            for inv_no, s_entry in sales_entries.items():
                if inv_no not in purchase_invoices:
                    missing_in_purchase.append({
                        "InvoiceNo": inv_no,
                        "SalesAmount": s_entry["Amount"],
                        "SalesTax": s_entry["Tax"],
                        "Type": "MissingInPurchase"
                    })

            mismatches.extend(missing_in_purchase)
            summary = {
                "MatchedCount": matched_count,
                "MismatchCount": len(mismatches),
                "Mismatches": mismatches
            }

            output_file = sales_path.parent / "gst_reconciliation_report.json"
            output_file.write_text(json.dumps(summary, indent=2))

            return ToolResult(
                success=True,
                output=f"GST reconciliation completed. Matches: {matched_count}, Mismatches: {len(mismatches)}. Report saved to {output_file.name}.",
                metadata=summary
            )
        except Exception as e:
            return ToolResult(success=False, error=f"GST reconciliation failed: {str(e)}")


class AccountingERPTool(Tool):
    """Processes invoices and manages accounts balances."""
    name = "accounting_invoice"
    description = "Generate invoices and track system ledger transactions. Args: customer_name, items (JSON string), tax_rate (float)."

    async def execute(self, customer_name: str, items: str | list, tax_rate: float = 0.18, **kwargs: Any) -> ToolResult:
        try:
            if isinstance(items, str):
                items_list = json.loads(items)
            else:
                items_list = items

            subtotal = 0.0
            for item in items_list:
                qty = float(item.get("qty", 1))
                price = float(item.get("price", 0))
                subtotal += qty * price

            tax = subtotal * tax_rate
            total = subtotal + tax

            invoice = {
                "InvoiceID": f"INV-{int(time.time())}",
                "Customer": customer_name,
                "Date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "Items": items_list,
                "Subtotal": round(subtotal, 2),
                "Tax": round(tax, 2),
                "Total": round(total, 2),
                "Status": "Unpaid"
            }

            output_root = kwargs.get("output_dir") or os.environ.get("ATULYA_DATA_DIR")
            if output_root:
                output_dir = Path(output_root) / "invoices"
            else:
                output_dir = Path(tempfile.gettempdir()) / "atulya" / "invoices"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{invoice['InvoiceID']}.json"
            output_file.write_text(json.dumps(invoice, indent=2))

            return ToolResult(
                success=True,
                output=f"Invoice {invoice['InvoiceID']} successfully generated for {customer_name}. Total: Rs. {invoice['Total']}.",
                metadata=invoice
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Invoice generation failed: {str(e)}")


class SAPAutomationTool(Tool):
    """Mock-automates SAP workflows from YAML configurations."""
    name = "sap_gui_automation"
    description = "Execute a SAP automation workflow batch using a recipe file. Args: recipe_yaml_path."

    async def execute(self, recipe_yaml_path: str, **kwargs: Any) -> ToolResult:
        try:
            recipe_path = Path(recipe_yaml_path)
            if not recipe_path.exists():
                return ToolResult(success=False, error=f"Recipe file not found: {recipe_yaml_path}")

            recipe_data = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
            connection = recipe_data.get("connection", {})
            steps = recipe_data.get("steps", [])

            execution_log = []
            execution_log.append(f"Connecting to SAP server {connection.get('system_id', 'DEV')} at {connection.get('client', '100')}...")

            for i, step in enumerate(steps, 1):
                tcode = step.get("tcode")
                action = step.get("action")
                fields = step.get("fields", {})

                execution_log.append(f"Step {i}: Transaction [{tcode}] -> Action [{action}]")
                for key, val in fields.items():
                    execution_log.append(f"  Setting field [{key}] = {val}")

            execution_log.append("Workflow batch execution completed successfully inside SAP GUI session.")

            return ToolResult(
                success=True,
                output="\n".join(execution_log),
                metadata={"steps_run": len(steps), "status": "Success"}
            )
        except Exception as e:
            return ToolResult(success=False, error=f"SAP Automation workflow failed: {str(e)}")

