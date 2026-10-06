"""Dwar (द्वार, gate): the server's API: accounts and sessions, chat history, sign-in, brains and keys, chat and voice, home and dashboard, automation."""
from __future__ import annotations

import json

from fastapi import (
    Header,
    HTTPException,
    Request,
)
from fastapi.responses import StreamingResponse

from atulya import dwar as chat_history
from atulya import dwar as helpers

from . import router
from atulya import dwar as _d

# ── dwar_vartalap ────────────────────────────────────────────────────────────
# ── chat ────────────────────────────────────────────────────────────


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
    user = _d._require_auth(token)
    model_id = str(body.get("model_id") or "latest")
    if "\\" in model_id or "/" in model_id:
        return {"error": "Model path not allowed"}
    prompt = str(body.get("prompt") or "")[:_d.MAX_PROMPT_CHARS]
    if not prompt.strip() and not body.get("approved_tool"):
        return {"error": "Say or type something first."}
    from atulya.buddhi import get_kernel
    from atulya.mastishk import get_default_llm

    server_messages = chat_history.list_messages(user, limit=20)
    server_hist = [{"role": m["role"], "content": m["text"]} for m in server_messages if m.get("text")]
    frontend_hist = body.get("history") or []
    history = _merge_history(frontend_hist, server_hist)

    # Every request goes through the cognitive kernel: intent -> safety -> action,
    # or the brain for open conversation.
    kernel = get_kernel(getattr(request.app.state, "llm", None) or get_default_llm())
    response = await kernel.handle(
        prompt,
        user=user,
        history=history,
        approved_tool=body.get("approved_tool") or None,
        provider=str(body.get("provider") or model_id),
        source="chat",
    )
    chat_history.append_exchange(user, prompt, response.text, provider=response.provider)
    return _d.redact_for(user, {
        "response": response.text[:_d.MAX_CHAT_TOKENS * 8],
        "model_id": model_id,
        "provider": response.provider,
        "steps": response.tool_steps,
        "needs_approval": response.needs_approval,
        "pending_tool": response.pending_tool,
        "trace": getattr(response, "trace", []),
    })


@router.post("/api/chat/stream")
async def api_chat_stream(request: Request, body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _d._require_auth(token)
    model_id = str(body.get("model_id") or "latest")
    prompt = str(body.get("prompt") or "")[:_d.MAX_PROMPT_CHARS]
    if "\\" in model_id or "/" in model_id:
        error = {"error": "Model path not allowed"}
        async def error_events():
            yield f"data: {json.dumps(error)}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        return StreamingResponse(error_events(), media_type="text/event-stream")

    async def events():
        from atulya.buddhi import get_kernel
        from atulya.mastishk import get_default_llm

        try:
            server_messages = chat_history.list_messages(user, limit=20)
            server_hist = [{"role": m["role"], "content": m["text"]} for m in server_messages if m.get("text")]
            frontend_hist = body.get("history") or []
            history = _merge_history(frontend_hist, server_hist)

            kernel = get_kernel(getattr(request.app.state, "llm", None) or get_default_llm())
            response_parts: list[str] = []
            async for event in kernel.stream(
                prompt,
                user=user,
                history=history,
                approved_tool=body.get("approved_tool") or None,
                provider=str(body.get("provider") or model_id),
                source="chat",
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
    user = _d._require_auth(token)
    return {"messages": chat_history.list_messages(user)}


@router.delete("/api/chat/history")
async def api_chat_history_clear(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _d._require_auth(token)
    chat_history.clear_messages(user)
    return {"ok": True}


@router.post("/api/feedback")
async def api_feedback(body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    """Mark an answer good or bad, so the next one is different.

    The question and answer travel with the verdict: a rating on its own only
    says a number went down, which is no use to anybody trying to work out
    what was wrong with it.
    """
    _d._require_auth(token)
    rating = str(body.get("rating") or "").strip().lower()
    if rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="rating must be 'up' or 'down'")
    from atulya.adhar import default_bus
    from atulya.kriya import record_feedback

    tally = record_feedback(
        rating,
        str(body.get("prompt") or ""),
        str(body.get("reply") or ""),
        str(body.get("comment") or ""),
    )
    await default_bus.emit("feedback.received", {"rating": rating, **tally})
    return {"ok": True, **tally}


# ── openai ────────────────────────────────────────────────────────────
def _model_registry() -> list[dict]:
    """The assistant is exposed as a single model; the brain routes behind it."""
    return [{"id": "atulya", "label": "Atulya", "owned_by": "atulya"}]


def _require_bearer(authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    parts = authorization.split(" ")
    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = parts[1]
    if token == helpers.ADMIN_TOKEN:
        return
    from atulya import dwar as users
    session = users.get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if session.get("role") != "admin":  # which models are configured is admin business
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/v1/models")
def list_models(authorization: str | None = Header(default=None, alias="Authorization")):
    _require_bearer(authorization)
    return {"object": "list", "data": [{"id": item["id"], "object": "model", **item} for item in _d._model_registry()]}


