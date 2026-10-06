"""Dwar (द्वार, gate): the server's API: accounts and sessions, chat history, sign-in, brains and keys, chat and voice, home and dashboard, automation."""
from __future__ import annotations

import asyncio

from fastapi import (
    Depends,
    Header,
    HTTPException,
    Request,
)

from atulya import sandesh as push_service  # Web Push now lives in sandesh
from atulya.smriti import build_memory_graph

from . import router
from atulya import dwar as _d
from .routes_system import _key, _store

# ── dwar_ghar ────────────────────────────────────────────────────────────
# ── notifications ────────────────────────────────────────────────────────────

@router.get("/api/notifications/vapid-key")
def notifications_vapid_key(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    _d._require_admin(token)
    return {"public_key": push_service.public_key(), "available": push_service.configured()}


@router.post("/api/notifications/subscribe")
def subscribe(body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _d._require_admin(token)
    try:
        push_service.subscribe(user.get("username", "unknown"), body.get("subscription"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "delivery_configured": push_service.configured()}

@router.post("/api/notifications/unsubscribe")
def unsubscribe(body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _d._require_admin(token)
    sub = body.get("subscription") or {}
    username = user.get("username", "unknown")
    endpoint = sub.get("endpoint", "") if isinstance(sub, dict) else ""
    push_service.unsubscribe(username, endpoint)
    return {"ok": True}

@router.post("/api/notifications/test")
async def test_notification(body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _d._require_admin(token)
    title = body.get("title", "Test")
    message = body.get("message", "This is a test notification")
    from fastapi.responses import JSONResponse
    if not push_service.configured():
        return JSONResponse({"ok": False, "sent": False, "title": title, "message": message,
                             "detail": "Web Push is not configured on this server."}, status_code=503)
    sent = await asyncio.to_thread(push_service.send, user.get("username", "admin"),
                                    {"title": str(title), "body": str(message), "type": "test"})
    return JSONResponse({"ok": True, "sent": sent > 0, "count": sent, "title": title, "message": message})


# ── memory ────────────────────────────────────────────────────────────
def _vector_count() -> int:
    try:
        import json
        from pathlib import Path

        total = 0
        for f in Path("kosh/memory").glob("*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            total += len(data) if isinstance(data, (list, dict)) else 0
        return total
    except Exception:  # noqa: BLE001 - a count only decorates the view
        return 0


@router.get("/api/memory/graph")
def api_memory_graph(request: Request, user: dict = Depends(_d._require_auth)):
    from atulya import dwar as chat_history
    from atulya.bhava import MoodState
    from atulya.kriya import TOOL_REGISTRY
    from atulya.mastishk import _SPEED, get_default_llm

    llm = getattr(request.app.state, "llm", None) or get_default_llm()
    mood = getattr(llm, "mood", None) or MoodState.load()
    episodes = [m for m in chat_history.list_messages(user, 60) if m.get("role") == "user"][-24:][::-1]
    brains = [{"name": n, "seconds": round(v["avg"], 1)} for n, v in _SPEED.items() if v.get("avg")]
    return build_memory_graph(
        _store(request).view(_key(user)),
        episodes=episodes,
        skills=[(n, str(t.get("description", ""))) for n, t in TOOL_REGISTRY.items()],
        mood={"mood": mood.label, "energy": round(mood.energy, 2), "valence": round(mood.valence, 2)},
        brains=brains,
        vectors=_vector_count(),
    )


# ── mood ────────────────────────────────────────────────────────────
@router.get("/api/mood")
def api_mood(request: Request, user: dict = Depends(_d._require_auth)):
    from atulya.bhava import MoodState
    from atulya.mastishk import get_default_llm

    llm = getattr(request.app.state, "llm", None) or get_default_llm()
    mood = getattr(llm, "mood", None) or MoodState.load()
    return {"label": mood.label, "valence": round(mood.valence, 2), "energy": round(mood.energy, 2)}


