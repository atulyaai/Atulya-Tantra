from __future__ import annotations

import json
from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from drishti.dashboard import chat_history
from drishti.dashboard.helpers import _checkpoint_index, _require_auth
from drishti.dashboard.state import MAX_CHAT_TOKENS, MAX_PROMPT_CHARS

router = APIRouter()


def _resolve_model_id(model_id: str):
    allowed = _checkpoint_index()
    if model_id not in allowed:
        return None, {"error": "Model path not allowed"}
    return allowed[model_id], None


def _merge_history(frontend_history: list[dict], server_history: list[dict], limit: int = 10) -> list[dict]:
    """Merge frontend-provided history with server-persisted history, deduplicating by content."""
    seen = set()
    merged = []
    for msg in server_history + frontend_history:
        content = (msg.get("content") or msg.get("text") or "").strip()
        role = msg.get("role", "user")
        if not content:
            continue
        key = f"{role}:{content[:80]}"
        if key in seen:
            continue
        seen.add(key)
        merged.append({"role": role, "content": content})
    return merged[-limit:]


@router.post("/api/chat")
async def api_chat(request: Request, body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    model_id = str(body.get("model_id") or "latest")
    if "\\" in model_id or "/" in model_id:
        _, error = _resolve_model_id(model_id)
        return error
    prompt = str(body.get("prompt") or "")[:MAX_PROMPT_CHARS]
    from atulya.llm import get_default_llm

    server_messages = chat_history.list_messages(user, limit=20)
    server_hist = [{"role": m["role"], "content": m["text"]} for m in server_messages if m.get("text")]
    frontend_hist = body.get("history") or []
    history = _merge_history(frontend_hist, server_hist)

    llm = getattr(request.app.state, "llm", None) or get_default_llm()
    response = await llm.ask(
        prompt,
        history=history,
        approved_tool_call=body.get("approved_tool") or None,
        provider=str(body.get("provider") or model_id),
    )
    chat_history.append_exchange(user, prompt, response.text, provider=response.provider)
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
    user = _require_auth(token)
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
            server_messages = chat_history.list_messages(user, limit=20)
            server_hist = [{"role": m["role"], "content": m["text"]} for m in server_messages if m.get("text")]
            frontend_hist = body.get("history") or []
            history = _merge_history(frontend_hist, server_hist)

            llm = getattr(request.app.state, "llm", None) or get_default_llm()
            response_parts: list[str] = []
            async for event in llm.stream(
                prompt,
                history=history,
                approved_tool_call=body.get("approved_tool") or None,
                provider=str(body.get("provider") or model_id),
            ):
                if event.type == "token":
                    response_parts.append(event.content)
                    yield f"data: {json.dumps({'token': event.content})}\n\n"
                elif event.type == "tool":
                    yield f"data: {json.dumps({'tool': event.metadata})}\n\n"
                elif event.type == "done":
                    chat_history.append_exchange(
                        user,
                        prompt,
                        "".join(response_parts),
                        provider=str(event.metadata.get("provider") or ""),
                    )
                    payload = {"done": True, "model_id": model_id, **event.metadata}
                    yield f"data: {json.dumps(payload)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/api/chat/history")
async def api_chat_history(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    return {"messages": chat_history.list_messages(user)}


@router.delete("/api/chat/history")
async def api_chat_history_clear(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    chat_history.clear_messages(user)
    return {"ok": True}
