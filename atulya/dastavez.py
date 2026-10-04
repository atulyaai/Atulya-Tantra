"""Document generation with optional rich renderers and safe fallbacks."""
from __future__ import annotations

import ast
import csv
import html
import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from atulya.kaushal import Tool, ToolResult


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


def _slug(value: str) -> str:
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
        return self.output_dir / f"{_slug(title)}-{time.time_ns()}.{extension}"


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

