"""API: the server's API: accounts and sessions, chat history, sign-in, brains and keys, chat and voice, home and dashboard, automation."""
from __future__ import annotations

import html
import os

from fastapi import (
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
)
from fastapi.responses import FileResponse, HTMLResponse

from atulya.devices import DeviceError, discover, get_hub

from . import router
from atulya import api as _d

# ── fabric ────────────────────────────────────────────────────────────
@router.get("/api/fabric")
def api_fabric(user: dict = Depends(_d._require_auth)):
    return {"devices": get_hub().describe()}


@router.post("/api/fabric/discover")
async def api_fabric_discover(user: dict = Depends(_d._require_admin)):
    hub = get_hub()
    found = await discover(profiles=hub.profiles)
    have = {(d.driver, d.address, str(sorted(d.config.items()))) for d in hub.devices.values()}
    fresh = [c for c in found if (c.driver, c.host, str(sorted(c.config.items()))) not in have]
    hub.last_candidates = {c.id: c for c in fresh}
    hub.last_order = [c.id for c in fresh]
    return {"found": [c.to_dict() for c in fresh[:60]]}


@router.post("/api/fabric/add")
async def api_fabric_add(body: dict, user: dict = Depends(_d._require_admin)):
    try:
        dev = await get_hub().add_candidate(str(body.get("candidate", "")), str(body.get("name", "")), str(body.get("room", "")))
    except DeviceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": dev.id, "name": dev.name, "can": [c.name for c in dev.capabilities]}


@router.post("/api/fabric/{device_id}/do")
async def api_fabric_do(device_id: str, body: dict, user: dict = Depends(_d._require_auth)):
    hub = get_hub()
    action = str(body.get("action", ""))
    if hub.is_risky(device_id, action) and not body.get("confirmed"):
        raise HTTPException(status_code=409, detail="This needs your confirmation.")
    dev = hub.find(device_id)
    cap = dev.cap(action) if dev else None
    args = {}
    if cap and cap.params and str(body.get("value", "")).strip():
        args[next(iter(cap.params))] = body["value"]
    if body.get("times"):
        args["times"] = body["times"]
    try:
        return {"message": await hub.act(device_id, action, args)}
    except DeviceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/fabric/{device_id}")
def api_fabric_remove(device_id: str, user: dict = Depends(_d._require_admin)):
    try:
        return {"removed": get_hub().remove(device_id)}
    except DeviceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── senses ────────────────────────────────────────────────────────────
def _senses(request: Request):
    senses = getattr(request.app.state, "senses", None)
    if senses is None:  # app started without lifespan (e.g. tests)
        from atulya.settings import default_bus
        from atulya.vision import Senses

        senses = Senses(default_bus)
        request.app.state.senses = senses
    return senses


@router.get("/api/senses")
def api_senses(request: Request, _admin: dict = Depends(_d._require_admin)):
    return _senses(request).status()


@router.post("/api/senses/cameras")
async def api_add_camera(request: Request, body: dict, _admin: dict = Depends(_d._require_admin)):
    try:
        camera = await _senses(request).add_camera(str(body.get("name") or ""), str(body.get("source") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "camera": camera}


@router.delete("/api/senses/cameras/{name}")
async def api_remove_camera(name: str, request: Request, _admin: dict = Depends(_d._require_admin)):
    if not await _senses(request).remove_camera(name):
        raise HTTPException(status_code=404, detail="Camera not found")
    return {"ok": True}


@router.get("/api/senses/cameras/{name}/snapshot")
def api_camera_snapshot(
    name: str,
    request: Request,
    token: str | None = Query(default=None),
    header_token: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    """The camera's latest 'someone is here' snapshot. Accepts ?token= so an <img> can load it."""
    _d._require_admin(header_token or token)
    watcher = _senses(request).cameras.get(name)
    path = getattr(watcher, "last_snapshot", "")
    if not path:
        raise HTTPException(status_code=404, detail="No snapshot yet")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/api/senses/heartbeat")
def api_listener_heartbeat(request: Request, body: dict, user: dict = Depends(_d._require_auth)):
    """An always-listening device checking in (see ``python -m atulya.ambient``)."""
    return {"ok": True, "listener": _senses(request).heartbeat(body, user=str(user.get("username") or ""))}


DEVICE_TOKEN_DAYS = 90


@router.post("/api/senses/device-token")
def api_device_token(body: dict, user: dict = Depends(_d._require_auth)):
    """A long-lived sign-in for an always-listening device (sessions expire daily).

    It acts as the signed-in user — same role, same confirmations.
    """
    device = str(body.get("device") or "listener")[:60]
    token = _d._jwt_encode({"sub": user.get("username"), "role": user.get("role", "user"),
                         "name": user.get("display_name", ""), "device": device},
                        expires_in=DEVICE_TOKEN_DAYS * 86400)
    return {"token": token, "device": device, "expires_in": DEVICE_TOKEN_DAYS * 86400}


# ── google ────────────────────────────────────────────────────────────
def redirect_uri(request: Request) -> str:
    """Where Google sends the user back. Set ATULYA_PUBLIC_URL behind a proxy."""
    base = os.environ.get("ATULYA_PUBLIC_URL", "").rstrip("/") or str(request.base_url).rstrip("/")
    return f"{base}/api/google/callback"


@router.get("/api/google/status")
def api_google_status(request: Request, user: dict = Depends(_d._require_auth)):
    from atulya.web import GoogleAccount, client_config

    cfg = client_config()
    return {
        "configured": bool(cfg["client_id"]),
        "client_source": cfg["source"],
        "redirect_uri": redirect_uri(request),
        "account": GoogleAccount(str(user.get("username") or "")).status(),
        "is_admin": user.get("role") == "admin",
    }


@router.post("/api/google/client")
def api_google_client(body: dict, _admin: dict = Depends(_d._require_admin)):
    """Save the OAuth client (from Google Cloud Console) — admin only, stored owner-only."""
    from atulya.web import GoogleError, save_client_config

    try:
        save_client_config(str(body.get("client_id") or ""), str(body.get("client_secret") or ""))
    except GoogleError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@router.post("/api/google/connect")
def api_google_connect(request: Request, user: dict = Depends(_d._require_auth)):
    from atulya.web import GoogleError, begin_sign_in

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
    from atulya.web import GoogleError, finish_sign_in

    if error:
        return _page("Google sign-in cancelled", "Nothing was connected.", ok=False)
    try:
        _user, email = await finish_sign_in(state, code)
    except GoogleError as exc:
        return _page("Couldn't connect Google", str(exc), ok=False)
    return _page("Google connected", f"Atulya can now use Gmail and Calendar for {email or 'your account'}.", ok=True)


@router.post("/api/google/disconnect")
async def api_google_disconnect(user: dict = Depends(_d._require_auth)):
    from atulya.web import GoogleAccount

    return {"ok": await GoogleAccount(str(user.get("username") or "")).disconnect()}


