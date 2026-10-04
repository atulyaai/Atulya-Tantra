"""Dashboard helper functions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time

from fastapi import Header, HTTPException

from atulya.sevak.state import ADMIN_TOKEN, JWT_SECRET

logger = logging.getLogger(__name__)

_JWT_SECRET = JWT_SECRET


def _jwt_encode(payload: dict, expires_in: int = 86400) -> str:
    payload = {**payload, "iat": int(time.time()), "exp": int(time.time()) + expires_in}
    header_b64 = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    sig = hmac.new(_JWT_SECRET.encode(), f"{header_b64}.{payload_b64}".encode(), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def _jwt_decode(token: str) -> dict | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        expected = hmac.new(_JWT_SECRET.encode(), f"{header_b64}.{payload_b64}".encode(), hashlib.sha256).digest()
        actual = base64.urlsafe_b64decode(sig_b64 + "==")
        if not hmac.compare_digest(expected, actual):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def _require_auth(token: str | None = Header(default=None, alias="X-Atulya-Token")) -> dict:
    from atulya.sevak import users
    if token:
        user = users.get_session(token)
        if user:
            return user
        if token == ADMIN_TOKEN:
            return {"username": "admin", "role": "admin", "display_name": "Admin"}
        jwt_payload = _jwt_decode(token)
        if jwt_payload:
            return {"username": jwt_payload.get("sub", "jwt_user"), "role": jwt_payload.get("role", "user"), "display_name": jwt_payload.get("name", "")}
    raise HTTPException(status_code=401, detail="Unauthorized")


def _require_admin(token: str | None = Header(default=None, alias="X-Atulya-Token")) -> dict:
    user = _require_auth(token)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user




# Details only the admin should see: which model answered, tool traces, provider names.
_ADMIN_ONLY_KEYS = {"provider": "Atulya", "provider_name": "Atulya", "model_id": "latest", "steps": [], "trace": []}


def redact_for(user: dict | None, payload: dict) -> dict:
    """Hide model, provider and tool-trace details from normal users."""
    if (user or {}).get("role") == "admin":
        return payload
    return {key: _ADMIN_ONLY_KEYS.get(key, value) if key in _ADMIN_ONLY_KEYS else value for key, value in payload.items()}
