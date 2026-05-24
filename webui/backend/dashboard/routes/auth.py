from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from webui.backend.dashboard import state
from webui.backend.dashboard.helpers import _require_admin

router = APIRouter()


@router.post("/api/auth/login")
def api_auth_login(body: dict):
    token = str(body.get("token") or body.get("password") or "")
    if token != state.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Wrong dashboard token")
    return {"ok": True, "token": state.ADMIN_TOKEN, "token_source": state.ADMIN_TOKEN_SOURCE}


@router.post("/api/auth/verify")
def api_auth_verify(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    return {"ok": True, "token_source": state.ADMIN_TOKEN_SOURCE}
