"""Senses: cameras, Home Assistant sensors and always-listening devices."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse

from atulya.server.helpers import _jwt_encode, _require_admin, _require_auth

router = APIRouter()


def _senses(request: Request):
    senses = getattr(request.app.state, "senses", None)
    if senses is None:  # app started without lifespan (e.g. tests)
        from atulya.events import default_bus
        from atulya.senses import Senses

        senses = Senses(default_bus)
        request.app.state.senses = senses
    return senses


@router.get("/api/senses")
def api_senses(request: Request, _admin: dict = Depends(_require_admin)):
    return _senses(request).status()


@router.post("/api/senses/cameras")
async def api_add_camera(request: Request, body: dict, _admin: dict = Depends(_require_admin)):
    try:
        camera = await _senses(request).add_camera(str(body.get("name") or ""), str(body.get("source") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "camera": camera}


@router.delete("/api/senses/cameras/{name}")
async def api_remove_camera(name: str, request: Request, _admin: dict = Depends(_require_admin)):
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
    _require_admin(header_token or token)
    watcher = _senses(request).cameras.get(name)
    path = getattr(watcher, "last_snapshot", "")
    if not path:
        raise HTTPException(status_code=404, detail="No snapshot yet")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/api/senses/heartbeat")
def api_listener_heartbeat(request: Request, body: dict, user: dict = Depends(_require_auth)):
    """An always-listening device checking in (see ``python -m atulya.ambient``)."""
    return {"ok": True, "listener": _senses(request).heartbeat(body, user=str(user.get("username") or ""))}


DEVICE_TOKEN_DAYS = 90


@router.post("/api/senses/device-token")
def api_device_token(body: dict, user: dict = Depends(_require_auth)):
    """A long-lived sign-in for an always-listening device (sessions expire daily).

    It acts as the signed-in user — same role, same confirmations.
    """
    device = str(body.get("device") or "listener")[:60]
    token = _jwt_encode({"sub": user.get("username"), "role": user.get("role", "user"),
                         "name": user.get("display_name", ""), "device": device},
                        expires_in=DEVICE_TOKEN_DAYS * 86400)
    return {"token": token, "device": device, "expires_in": DEVICE_TOKEN_DAYS * 86400}
