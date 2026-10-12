"""Document reading: PDF, DOCX, XLSX, CSV, code summarization.

Uses free, offline-capable libraries:
- PDF: pymupdf (fitz) — renders pages, extracts text
- DOCX: python-docx — reads paragraphs, tables
- XLSX: openpyxl — reads sheets, cells
- CSV: built-in csv module
- Code: syntax-aware via tokenize + pygments-style filtering (lightweight)
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import httpx

try:
    import fitz  # pymupdf
except ImportError:
    fitz = None

try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None

try:
    import openpyxl
except ImportError:
    openpyxl = None

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "doc",
    ".xlsx": "xlsx",
    ".xls": "xls",
    ".csv": "csv",
    ".py": "code",
    ".js": "code",
    ".ts": "code",
    ".sh": "code",
}


async def read_document(filepath: str | Path) -> dict:
    """Read a document and return its content structured by type.

    Returns dict with keys: text (full extracted text), pages (for PDF),
    tables (for docx/xlsx), sheets (for xlsx), rows (for csv).
    """
    path = Path(filepath)
    ext = path.suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    result = {"type": SUPPORTED_EXTENSIONS[ext], "filepath": str(path)}

    if ext == ".pdf" and fitz:
        result.update(await _read_pdf(path))
    elif ext in (".doc", ".docx") and DocxDocument:
        result.update(await _read_docx(path))
    elif ext in (".xlsx", ".xls") and openpyxl:
        result.update(await _read_xlsx(path))
    elif ext == ".csv":
        result.update(await _read_csv(path))
    elif ext == ".code":
        result.update(await _read_code(path))

    return result


async def _read_pdf(path: Path) -> dict:
    """Read PDF using pymupdf (fitz)."""
    doc = fitz.open(path)
    text = ""
    pages = []
    tables = []
    for i, page in enumerate(doc):
        page_text = page.get_text("text")
        pages.append({"page": i + 1, "text": page_text})
        text += page_text
    return {"pages": pages, "text": text, "page_count": len(doc)}


async def _read_docx(path: Path) -> dict:
    """Read DOCX using python-docx."""
    doc = DocxDocument(path)
    text = ""
    tables = []
    for para in doc.paragraphs:
        text += para.text + "\n"
    for table in doc.tables:
        table_data = []
        for row in table.rows:
            table_data.append([cell.text for cell in row.cells])
        tables.append(table_data)
    return {"text": text, "tables": tables}


async def _read_xlsx(path: Path) -> dict:
    """Read XLSX using openpyxl."""
    wb = openpyxl.load_workbook(path, data_only=True)
    sheets = {}
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        sheet_text = ""
        sheet_rows = []
        for row in ws.iter_rows(min_row=1, values_only=True):
            sheet_rows.append([str(c) if c is not None else "" for c in row])
            sheet_text += ", ".join(str(c) if c is not None else "" for c in row) + "\n"
        sheets[sheet_name] = {"rows": sheet_rows, "text": sheet_text}
    return {"sheets": sheets}


async def _read_csv(path: Path) -> dict:
    """Read CSV using Python's built-in csv module."""
    rows = []
    text = ""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header:
            text += ", ".join(header) + "\n"
        for row in reader:
            rows.append(row)
            text += ", ".join(row) + "\n"
    return {"rows": rows, "text": text, "has_header": header is not None}


async def _read_code(path: Path) -> dict:
    """Read a code file — return full text and summary stats."""
    try:
        async with asyncio.to_thread(path.read_text, encoding="utf-8") as text:
            # Basic stats
            lines = text.splitlines()
            return {"text": text, "line_count": len(lines), "char_count": len(text)}
    except UnicodeDecodeError:
        # Try latin-1 fallback
        text = await asyncio.to_thread(path.read_text, encoding="latin-1")
        lines = text.splitlines()
        return {"text": text, "line_count": len(lines), "char_count": len(text)}


async def summarize_text(text: str, max_lines: int = 100) -> str:
    """Summarize long text by extracting key sentences.

    Simple extractive summary: take first and last N lines,
    plus any line containing important keywords.
    """
    if not text:
        return ""

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return ""

    if len(lines) <= max_lines:
        return "\n".join(lines)

    # Take first 3, last 3, and any line with important keywords
    keywords = {"error", "warning", "failure", "success", "result", "summary",
                "total", "average", "max", "min", "top", "best"}
    important = [l for l in lines if any(k in l.lower() for k in keywords)]

    summary = lines[:3]
    if important:
        summary.extend(important[:3])
    summary.extend(lines[-3:])

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for l in summary:
        if l not in seen:
            seen.add(l)
            deduped.append(l)

    return "\n".join(deduped)


async def can_read(filepath: str | Path) -> bool:
    """Check if Atulya can read a file type."""
    path = Path(filepath)
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return False
    # Check if the required library is available
    if ext == ".pdf" and fitz is None:
        return False
    if ext in (".doc", ".docx") and DocxDocument is None:
        return False
    if ext in (".xlsx", ".xls") and openpyxl is None:
        return False
    return True