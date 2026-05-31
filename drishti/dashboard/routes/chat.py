from __future__ import annotations

import json
from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from drishti.dashboard.helpers import _checkpoint_index, _require_auth
from drishti.dashboard.state import MAX_CHAT_TOKENS, MAX_PROMPT_CHARS

router = APIRouter()


def _resolve_model_id(model_id: str):
    allowed = _checkpoint_index()
    if model_id not in allowed:
        return None, {"error": "Model path not allowed"}
    return allowed[model_id], None


@router.post("/api/chat")
async def api_chat(request: Request, body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_auth(token)
    model_id = str(body.get("model_id") or "latest")
    if "\\" in model_id or "/" in model_id:
        _, error = _resolve_model_id(model_id)
        return error
    prompt = str(body.get("prompt") or "")[:MAX_PROMPT_CHARS]
    from atulya.llm import get_default_llm

    llm = getattr(request.app.state, "llm", None) or get_default_llm()
    response = await llm.ask(
        prompt,
        history=body.get("history") or [],
        approved_tool_call=body.get("approved_tool") or None,
    )
    return {
        "response": response.text[:MAX_CHAT_TOKENS * 8],
        "model_id": model_id,
        "provider": response.provider,
        "steps": response.tool_steps,
        "needs_approval": response.needs_approval,
        "pending_tool": response.pending_tool,
    }


@router.post("/api/chat/stream")
async def api_chat_stream(request: Request, body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_auth(token)
    model_id = str(body.get("model_id") or "latest")
    prompt = str(body.get("prompt") or "")[:MAX_PROMPT_CHARS]
    if "\\" in model_id or "/" in model_id:
        _, error = _resolve_model_id(model_id)
        async def error_events():
            yield f"data: {json.dumps(error)}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        return StreamingResponse(error_events(), media_type="text/event-stream")

    async def events():
        from atulya.llm import get_default_llm

        try:
            llm = getattr(request.app.state, "llm", None) or get_default_llm()
            async for event in llm.stream(
                prompt,
                history=body.get("history") or [],
                approved_tool_call=body.get("approved_tool") or None,
            ):
                if event.type == "token":
                    yield f"data: {json.dumps({'token': event.content})}\n\n"
                elif event.type == "tool":
                    yield f"data: {json.dumps({'tool': event.metadata})}\n\n"
                elif event.type == "done":
                    payload = {"done": True, "model_id": model_id, **event.metadata}
                    yield f"data: {json.dumps(payload)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
