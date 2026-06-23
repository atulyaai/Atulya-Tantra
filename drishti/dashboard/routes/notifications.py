from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Header
from drishti.dashboard.helpers import _require_auth

logger = logging.getLogger(__name__)
router = APIRouter()

SUBS_FILE = Path(__file__).resolve().parents[3] / "config" / "push_subs.json"

@router.post("/api/notifications/subscribe")
def subscribe(body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    sub = body.get("subscription")
    if not sub:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Missing subscription")
    username = user.get("username", "unknown")
    SUBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    subs = {}
    if SUBS_FILE.exists():
        subs = json.loads(SUBS_FILE.read_text())
    if username not in subs:
        subs[username] = []
    subs[username].append(sub)
    SUBS_FILE.write_text(json.dumps(subs, indent=2))
    return {"ok": True}

@router.post("/api/notifications/unsubscribe")
def unsubscribe(body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    sub = body.get("subscription")
    username = user.get("username", "unknown")
    if not SUBS_FILE.exists():
        return {"ok": True}
    subs = json.loads(SUBS_FILE.read_text())
    if username in subs and sub in subs[username]:
        subs[username].remove(sub)
        SUBS_FILE.write_text(json.dumps(subs, indent=2))
    return {"ok": True}

@router.post("/api/notifications/test")
def test_notification(body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_auth(token)
    from drishti.dashboard.helpers import _require_admin
    _require_admin(token)
    title = body.get("title", "Test")
    message = body.get("message", "This is a test notification")
    from fastapi.responses import JSONResponse
    return JSONResponse({"ok": True, "sent": True, "title": title, "message": message})
