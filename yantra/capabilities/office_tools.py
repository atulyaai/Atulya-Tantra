"""Free, local office/data tools for Jarvis workflows."""
from __future__ import annotations

import ast
import csv
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from yantra.capabilities import Tool, ToolResult


class CodeExecuteTool(Tool):
    name = "code_execute"
    description = "Execute a small Python snippet in an isolated temp file. Args: code, timeout."

    async def execute(self, code: str, timeout: int = 10, **kwargs: Any) -> ToolResult:
        if len(code) > 12000:
            return ToolResult(success=False, error="Code too large")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snippet.py"
            path.write_text(code, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(path)],
                capture_output=True,
                text=True,
                timeout=max(1, min(int(timeout), 30)),
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
        pdf_path = Path(path)
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
