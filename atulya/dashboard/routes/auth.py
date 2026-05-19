"""NP-DNA Dashboard Authentication Routes.
"""
from __future__ import annotations
from fastapi import APIRouter, Header, Request
from atulya.dashboard.helpers import _check_request_origin, _require_admin

router = APIRouter()


@router.post("/api/auth/verify")
def api_auth_verify(
    request: Request,
    _admin: str | None = Header(default=None, alias="X-Atulya-Token"),
):
    _check_request_origin(request)
    _require_admin(_admin)
    return {"status": "authorized"}
