from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, UploadFile, File

from atulya.sevak.helpers import _require_auth

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parents[3] / "data" / "uploads"
_MAX_SIZE = 50 * 1024 * 1024  # 50MB


def _safe_component(value: str, label: str = "identifier") -> str:
    """Reject any path-like input so it can't traverse outside the uploads dir.

    A valid username / file_id is a single path component with no separators,
    no parent references, and no null bytes. Anything else is a traversal
    attempt (e.g. '..', 'a/../../etc', '%2e%2e').
    """
    if not value or value in (".", "..") or "/" in value or "\\" in value or "\x00" in value:
        raise HTTPException(400, f"Invalid {label}")
    if os.path.basename(value) != value:
        raise HTTPException(400, f"Invalid {label}")
    return value


def _resolve_upload_path(username: str, file_id: str) -> Path:
    """Build an uploads path and confirm it stays inside UPLOAD_DIR."""
    _safe_component(username, "username")
    _safe_component(file_id, "file id")
    path = (UPLOAD_DIR / username / file_id).resolve()
    base = UPLOAD_DIR.resolve()
    if base not in path.parents:
        raise HTTPException(400, "Invalid path")
    return path
_ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf", "text/plain", "text/csv",
    "application/json", "application/zip",
}

@router.post("/api/upload")
async def api_upload(
    file: UploadFile = File(...),
    token: str | None = Header(default=None, alias="X-Atulya-Token")
):
    user = _require_auth(token)
    if not file.filename:
        raise HTTPException(400, "No filename")

    ext = Path(file.filename).suffix.lower() if file.filename else ""
    content_type = file.content_type or ""

    if content_type and content_type not in _ALLOWED_TYPES and not content_type.startswith("image/"):
        if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".txt", ".csv", ".json", ".zip"):
            raise HTTPException(400, f"File type '{content_type}' not allowed")

    user_dir = UPLOAD_DIR / user["username"]
    user_dir.mkdir(parents=True, exist_ok=True)

    file_id = f"{uuid.uuid4().hex}{ext}"
    dest = user_dir / file_id

    content = await file.read()
    if len(content) > _MAX_SIZE:
        raise HTTPException(400, f"File too large (max {_MAX_SIZE // 1024 // 1024}MB)")

    dest.write_bytes(content)

    return {
        "ok": True,
        "file_id": file_id,
        "filename": file.filename,
        "size": len(content),
        "url": f"/api/files/{user['username']}/{file_id}",
    }

@router.get("/api/files/{username}/{file_id}")
async def api_get_file(username: str, file_id: str, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    if username != user["username"] and user.get("role") != "admin":
        raise HTTPException(403, "Forbidden")
    file_path = _resolve_upload_path(username, file_id)
    if not file_path.is_file():
        raise HTTPException(404, "File not found")
    from fastapi.responses import FileResponse
    return FileResponse(str(file_path))

@router.get("/api/files")
async def api_list_files(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    user_dir = UPLOAD_DIR / user["username"]
    if not user_dir.exists():
        return {"files": []}
    files = []
    for f in user_dir.iterdir():
        if f.is_file():
            files.append({
                "file_id": f.name,
                "size": f.stat().st_size,
                "modified": f.stat().st_mtime,
            })
    return {"files": sorted(files, key=lambda x: x["modified"], reverse=True)}

@router.delete("/api/files/{file_id}")
async def api_delete_file(file_id: str, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    file_path = _resolve_upload_path(user["username"], file_id)
    if not file_path.is_file():
        raise HTTPException(404, "File not found")
    file_path.unlink()
    return {"ok": True}
