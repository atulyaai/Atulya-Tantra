"""Money inbox: a phone (or any app) forwards each bank SMS here, and Atulya records the spending.

The phone holds one secret that can add alerts and do nothing else (no chat, no tools, no settings).
Send it as the ``X-Atulya-Inbox`` header, or in the URL as ``?key=...`` for apps that cannot set headers.
"""
from __future__ import annotations

import json
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request

from atulya.agent import money
from atulya.server.helpers import _require_auth

router = APIRouter()
_MAX_BYTES = 4000


async def _alert_text(request: Request) -> str:
    raw = (await request.body())[:_MAX_BYTES]
    text = raw.decode("utf-8", "ignore").strip()
    if text.startswith("{"):
        try:
            data = json.loads(text)
            return str(data.get("text") or data.get("message") or data.get("body") or data.get("sms") or "")
        except json.JSONDecodeError:
            return text
    if "=" in text and "\n" not in text and " " not in text.split("=", 1)[0]:
        form = parse_qs(text)
        for key in ("text", "message", "body", "sms"):
            if form.get(key):
                return form[key][0]
    return text


@router.post("/api/money/sms")
async def api_money_sms(request: Request):
    key = request.headers.get("x-atulya-inbox") or request.query_params.get("key")
    if not money.inbox_token_ok(key):
        raise HTTPException(status_code=401, detail="Bad inbox key")
    text = await _alert_text(request)
    if not text:
        raise HTTPException(status_code=400, detail="No message text")
    result = await money.record_alert_async(text, "sms")
    return {"status": result["status"], "message": money._alert_reply(result)}


@router.get("/api/money/inbox")
def api_money_inbox(request: Request, user: dict = Depends(_require_auth)):
    """The secret and the address to give your phone's SMS-forwarding app."""
    return {"key": money.inbox_token(), "path": "/api/money/sms", "origin": str(request.base_url).rstrip("/")}


@router.post("/api/money/inbox/rotate")
def api_money_inbox_rotate(user: dict = Depends(_require_auth)):
    return {"key": money.inbox_token(rotate=True)}
