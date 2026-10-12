"""Document reading: PDF, DOCX, XLSX, CSV, code summarization.

Uses free, offline-capable libraries:
- PDF: pymupdf (fitz)
- DOCX: python-docx
- XLSX: openpyxl
- CSV: built-in csv module
- Code: plain text files
"""
from __future__ import annotations

import asyncio
import csv
import logging
from pathlib import Path

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
    ".md": "code",
    ".txt": "code",
    ".json": "code",
    ".toml": "code",
    ".yaml": "code",
    ".yml": "code",
}


async def read_document(filepath: str | Path) -> dict:
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
    elif SUPPORTED_EXTENSIONS[ext] == "code":
        result.update(await _read_code(path))
    else:
        raise ValueError(f"Library not installed for {ext}")
    return result


async def _read_pdf(path: Path) -> dict:
    def _sync():
        doc = fitz.open(path)
        text = ""
        pages = []
        for i, page in enumerate(doc):
            page_text = page.get_text("text")
            pages.append({"page": i + 1, "text": page_text})
            text += page_text
        page_count = len(doc)
        doc.close()
        return {"pages": pages, "text": text, "page_count": page_count}
    return await asyncio.to_thread(_sync)


async def _read_docx(path: Path) -> dict:
    def _sync():
        doc = DocxDocument(path)
        text = ""
        tables = []
        for para in doc.paragraphs:
            text += para.text + "\n"
        for table in doc.tables:
            table_data = [[cell.text for cell in row.cells] for row in table.rows]
            tables.append(table_data)
        return {"text": text, "tables": tables}
    return await asyncio.to_thread(_sync)


async def _read_xlsx(path: Path) -> dict:
    def _sync():
        wb = openpyxl.load_workbook(path, data_only=True)
        sheets = {}
        texts = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            sheet_text = ""
            sheet_rows = []
            for row in ws.iter_rows(min_row=1, values_only=True):
                sheet_rows.append([str(c) if c is not None else "" for c in row])
                sheet_text += ", ".join(str(c) if c is not None else "" for c in row) + "\n"
            sheets[sheet_name] = {"rows": sheet_rows, "text": sheet_text}
            texts.append(sheet_text)
        return {"sheets": sheets, "text": "\n".join(texts)}
    return await asyncio.to_thread(_sync)


async def _read_csv(path: Path) -> dict:
    def _sync():
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
    return await asyncio.to_thread(_sync)


async def _read_code(path: Path) -> dict:
    def _sync():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="latin-1")
        lines = text.splitlines()
        return {"text": text, "line_count": len(lines), "char_count": len(text)}
    return await asyncio.to_thread(_sync)


async def summarize_text(text: str, max_lines: int = 100) -> str:
    if not text:
        return ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return ""
    if len(lines) <= max_lines:
        return "\n".join(lines)
    keywords = {"error", "warning", "failure", "success", "result", "summary",
                "total", "average", "max", "min", "top", "best"}
    important = [l for l in lines if any(k in l.lower() for k in keywords)]
    summary = lines[:3]
    if important:
        summary.extend(important[:3])
    summary.extend(lines[-3:])
    seen: set[str] = set()
    deduped = []
    for l in summary:
        if l not in seen:
            seen.add(l)
            deduped.append(l)
    return "\n".join(deduped)


async def can_read(filepath: str | Path) -> bool:
    path = Path(filepath)
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return False
    if ext == ".pdf" and fitz is None:
        return False
    if ext in (".doc", ".docx") and DocxDocument is None:
        return False
    if ext in (".xlsx", ".xls") and openpyxl is None:
        return False
    return True
