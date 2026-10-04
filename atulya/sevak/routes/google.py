"""Google sign-in (Gmail + Calendar) for the signed-in user."""
from __future__ import annotations

import html
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from atulya.sevak.helpers import _require_admin, _require_auth

router = APIRouter()


def redirect_uri(request: Request) -> str:
    """Where Google sends the user back. Set ATULYA_PUBLIC_URL behind a proxy."""
    base = os.environ.get("ATULYA_PUBLIC_URL", "").rstrip("/") or str(request.base_url).rstrip("/")
    return f"{base}/api/google/callback"


@router.get("/api/google/status")
def api_google_status(request: Request, user: dict = Depends(_require_auth)):
    from atulya.yantra.google_workspace import GoogleAccount, client_config

    cfg = client_config()
    return {
        "configured": bool(cfg["client_id"]),
        "client_source": cfg["source"],
        "redirect_uri": redirect_uri(request),
        "account": GoogleAccount(str(user.get("username") or "")).status(),
        "is_admin": user.get("role") == "admin",
    }


@router.post("/api/google/client")
def api_google_client(body: dict, _admin: dict = Depends(_require_admin)):
    """Save the OAuth client (from Google Cloud Console) — admin only, stored owner-only."""
    from atulya.yantra.google_workspace import GoogleError, save_client_config

    try:
        save_client_config(str(body.get("client_id") or ""), str(body.get("client_secret") or ""))
    except GoogleError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@router.post("/api/google/connect")
def api_google_connect(request: Request, user: dict = Depends(_require_auth)):
    from atulya.yantra.google_workspace import GoogleError, begin_sign_in

    try:
        url = begin_sign_in(str(user.get("username") or ""), redirect_uri(request))
    except GoogleError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"url": url}


def _page(title: str, message: str, ok: bool) -> HTMLResponse:
    colour = "#2eb85c" if ok else "#f05a44"
    target = "/?google=connected" if ok else "/?google=failed"
    body = (
        "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
        f"<meta http-equiv='refresh' content='3;url={target}'><title>{html.escape(title)}</title></head>"
        "<body style=\"background:#0a0d1f;color:#fbf6ee;font-family:system-ui;display:grid;place-items:center;"
        "min-height:100vh;margin:0\"><div style='text-align:center;padding:24px'>"
        f"<h1 style='color:{colour}'>{html.escape(title)}</h1><p>{html.escape(message)}</p>"
        f"<p><a style='color:#ff9933' href='{target}'>Back to Atulya</a></p></div></body></html>"
    )
    return HTMLResponse(body, status_code=200 if ok else 400)


@router.get("/api/google/callback")
async def api_google_callback(state: str = "", code: str = "", error: str = ""):
    """Google redirects here after the consent screen. The single-use state is the proof."""
    from atulya.yantra.google_workspace import GoogleError, finish_sign_in

    if error:
        return _page("Google sign-in cancelled", "Nothing was connected.", ok=False)
    try:
        _user, email = await finish_sign_in(state, code)
    except GoogleError as exc:
        return _page("Couldn't connect Google", str(exc), ok=False)
    return _page("Google connected", f"Atulya can now use Gmail and Calendar for {email or 'your account'}.", ok=True)


@router.post("/api/google/disconnect")
async def api_google_disconnect(user: dict = Depends(_require_auth)):
    from atulya.yantra.google_workspace import GoogleAccount

    return {"ok": await GoogleAccount(str(user.get("username") or "")).disconnect()}
