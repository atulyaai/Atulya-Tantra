from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from drishti.dashboard.helpers import _require_auth
from yantra.capabilities.connector import AtulyaTantraConnector, CreationResult

router = APIRouter()


def _connector() -> AtulyaTantraConnector:
    return AtulyaTantraConnector("assets/creations")


def _payload(result: CreationResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "format": result.format,
        "path": result.path,
        "fallback": result.fallback,
        "metadata": result.metadata,
        "error": result.error,
    }


def _options(body: dict) -> dict[str, Any]:
    return {key: value for key, value in body.items() if key not in {"prompt", "format", "formats"}}


@router.post("/api/create")
def api_create(body: dict, _user: dict = Depends(_require_auth)):
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return {"ok": False, "error": "prompt is required"}
    connector = _connector()
    formats = body.get("formats")
    if isinstance(formats, list) and formats:
        results = connector.create_multi(prompt, [str(item) for item in formats])
        return {"ok": all(item.ok for item in results), "results": [_payload(item) for item in results]}
    return _payload(connector.create(prompt, str(body.get("format") or "auto"), **_options(body)))


@router.post("/api/create/document")
def api_create_document(body: dict, _user: dict = Depends(_require_auth)):
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return {"ok": False, "error": "prompt is required"}
    return _payload(_connector().create(prompt, str(body.get("format") or "pdf"), **_options(body)))


@router.post("/api/create/video")
def api_create_video(body: dict, _user: dict = Depends(_require_auth)):
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return {"ok": False, "error": "prompt is required"}
    return _payload(_connector().create(prompt, "video", **_options(body)))
