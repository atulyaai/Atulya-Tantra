from __future__ import annotations

import json
import threading

import psutil
import torch
from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from webui.backend.dashboard.helpers import _checkpoint_index, _load_cached_model, _require_admin
from webui.backend.dashboard.state import MAX_CHAT_TOKENS, MAX_PROMPT_CHARS

router = APIRouter()

_GENERATION_LOCK = threading.Lock()


def _resolve_model_id(model_id: str):
    allowed = _checkpoint_index()
    if model_id not in allowed:
        return None, {"error": "Model path not allowed"}
    return allowed[model_id], None


@router.post("/api/chat")
def api_chat(body: dict, _admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    model_id = str(body.get("model_id") or "latest")
    model_path, error = _resolve_model_id(model_id)
    if error:
        return error
    if psutil.virtual_memory().available < 500 * 1024 * 1024:
        return {"error": "Not enough free RAM to run generation safely"}
    prompt = str(body.get("prompt") or "")[:MAX_PROMPT_CHARS]
    max_tokens = max(1, min(int(body.get("max_tokens") or 128), MAX_CHAT_TOKENS))
    temperature = float(body.get("temperature") or 0.7)
    with _GENERATION_LOCK, torch.inference_mode():
        core = _load_cached_model(model_path)
        response = core.generate(prompt, max_tokens=max_tokens, temperature=temperature)
    return {"response": response, "model_id": model_id}


@router.post("/api/chat/stream")
def api_chat_stream(body: dict, _admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    model_id = str(body.get("model_id") or "latest")
    model_path, error = _resolve_model_id(model_id)
    prompt = str(body.get("prompt") or "")[:MAX_PROMPT_CHARS]
    max_tokens = max(1, min(int(body.get("max_tokens") or 128), MAX_CHAT_TOKENS))
    temperature = float(body.get("temperature") or 0.7)

    def events():
        if error:
            yield f"data: {json.dumps(error)}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
            return
        if psutil.virtual_memory().available < 500 * 1024 * 1024:
            yield f"data: {json.dumps({'error': 'Not enough free RAM to run generation safely'})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
            return
        try:
            with _GENERATION_LOCK, torch.inference_mode():
                core = _load_cached_model(model_path)
                for token in core.generate_stream(prompt, max_tokens=max_tokens, temperature=temperature):
                    yield f"data: {json.dumps({'token': token})}\n\n"
            yield f"data: {json.dumps({'done': True, 'model_id': model_id})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
