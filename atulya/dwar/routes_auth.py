"""Dwar (द्वार, gate): the server's API: accounts and sessions, chat history, sign-in, brains and keys, chat and voice, home and dashboard, automation."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Any
from urllib.parse import parse_qsl

from pydantic import BaseModel
from fastapi import (
    Depends,
    Header,
    HTTPException,
    Request,
)

from atulya import dwar as users
from atulya import kriya as money
from atulya import raksha as vault

from . import router
from atulya import dwar as _d



@router.post("/api/auth/login")
def api_auth_login(body: dict):
    username = body.get("username")
    password = body.get("password")
    
    user = users.authenticate(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Wrong username or password")
        
    token = users.create_session(username)
    jwt = _d._jwt_encode({"sub": username, "role": user.get("role", "user"), "name": user.get("display_name", "")})
    return {
        "ok": True,
        "token": token,
        "jwt": jwt,
        "user": user
    }


def _is_local_request(request: Request) -> bool:
    """True only for a direct connection from this computer (never through a proxy)."""
    if any(h in request.headers for h in ("x-forwarded-for", "x-real-ip", "forwarded")):
        return False
    # A page in another browser tab can still issue this request, so require the
    # fetch to come from the address bar or this origin, not another site.
    if request.headers.get("sec-fetch-site", "").lower() in ("cross-site", "same-site"):
        return False
    return (request.client.host if request.client else "") in ("127.0.0.1", "::1")


@router.get("/api/auth/local")
def api_auth_local(request: Request):
    """Sign in without a password when you are on the computer Atulya runs on.

    Phones and other devices on the network still need to log in. Set
    ``ATULYA_REQUIRE_LOGIN=on`` to turn this off.
    """

    if os.environ.get("ATULYA_REQUIRE_LOGIN", "").strip().lower() in ("on", "1", "true", "yes"):
        raise HTTPException(status_code=403, detail="Login required")
    if not _is_local_request(request):
        raise HTTPException(status_code=403, detail="Login required")
    return {"ok": True, "token": _d.ADMIN_TOKEN,
            "user": {"username": "admin", "role": "admin", "display_name": "Admin"}}


@router.post("/api/auth/verify")
def api_auth_verify(user: dict = Depends(_d._require_auth)):
    return {
        "ok": True,
        "user": user
    }


@router.post("/api/auth/logout")
def api_auth_logout(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    if token:
        users.kill_session(token)
    return {"ok": True}


# ── Telegram Mini App ───────────────────────────────────────────────────────
# Telegram signs initData when the Mini App opens and treats it as good for a
# day; the session minted from it is deliberately far shorter-lived.
MINI_APP_INIT_DATA_MAX_AGE = 86400
MINI_APP_SESSION_SECONDS = 3600


def _telegram_allowed(user_id: Any) -> bool:
    """Whether this Telegram account may open the Mini App.

    An empty allowlist admits nobody. This endpoint hands a session to
    whoever reaches it, so failing open would turn the hologram into a public
    door the moment the server is tunneled out of the house.
    """
    allowed = {item.strip() for item in os.environ.get("ATULYA_TELEGRAM_ALLOWLIST", "").split(",") if item.strip()}
    return bool(allowed) and str(user_id) in allowed


def verify_telegram_init_data(init_data: str, bot_token: str, max_age: int = MINI_APP_INIT_DATA_MAX_AGE) -> dict:
    """Check Telegram's signature over ``initData`` and return the user it names.

    The secret key is HMAC-SHA256("WebAppData", bot_token) and the signature
    covers every received field, sorted, with ``hash`` removed. A match means
    somebody produced this holding this bot's token -- either Telegram or the
    token's owner -- which is the only thing that makes it safe to expose a
    session-minting endpoint through a public tunnel. Anything less returns
    an empty dict rather than a guess.
    """
    if not init_data or not bot_token:
        return {}
    fields = parse_qsl(init_data, keep_blank_values=True)
    signature = next((value for key, value in fields if key == "hash"), "")
    if not signature:
        return {}
    signed = [(key, value) for key, value in fields if key != "hash"]
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(signed))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest(), signature):
        return {}
    values = {key: value for key, value in fields}
    try:
        auth_date = int(values.get("auth_date") or "")
    except ValueError:
        return {}
    if abs(int(time.time()) - auth_date) > max_age:
        return {}  # a captured link must stop working, not become a key
    try:
        user = json.loads(values.get("user") or "{}")
    except json.JSONDecodeError:
        return {}
    return user if isinstance(user, dict) else {}


class MiniAppBody(BaseModel):
    init_data: str = ""


@router.post("/api/miniapp/session")
def api_miniapp_session(body: MiniAppBody):
    """Turn Telegram's signed ``initData`` into a session the hologram can use.

    Opened from a link, the page runs on Telegram's host rather than this
    server's, so there is no ``X-Atulya-Token`` to send and the local sign-in
    shortcut is no help -- that one is for the computer Atulya runs on. The
    signature is the credential instead, and the account it names must be on
    the allowlist like anywhere else. Allowlisted Telegram users already
    operate Atulya through chat, including PC control, so they get the same
    standing here.
    """
    bot_token = os.environ.get("ATULYA_TELEGRAM_BOT_TOKEN", "").strip()
    if not bot_token:
        raise HTTPException(status_code=503, detail="The Telegram bot is not configured")
    user = verify_telegram_init_data(body.init_data, bot_token)
    if not user:
        raise HTTPException(status_code=401, detail="Telegram could not confirm this request")
    if not _telegram_allowed(user.get("id")):
        raise HTTPException(status_code=403, detail="This Telegram account may not open Atulya")
    user_id = user["id"]
    name = str(user.get("first_name") or user.get("username") or "Telegram")
    return {
        "ok": True,
        "token": _d._jwt_encode({"sub": f"telegram:{user_id}", "role": "admin", "name": name},
                             expires_in=MINI_APP_SESSION_SECONDS),
        "user": {"username": f"telegram:{user_id}", "role": "admin", "display_name": name},
    }


# ── pairing: phones, laptops and desktops that belong to you ─────────────────────────────────────────────
class PairCodeBody(BaseModel):
    permission: str = "files"


class EnrollBody(BaseModel):
    code: str
    name: str = "device"
    kind: str = "device"


@router.post("/api/pairing/code")
def api_pairing_code(body: PairCodeBody, request: Request, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    """Make a one-time code (valid 10 minutes) to pair a new device (admin only)."""
    admin = _d._require_admin(token)
    try:
        made = vault.paired_devices().new_code(body.permission, owner=admin)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    money.audit("pairing.code", by=admin.get("username"), permission=made["permission"])
    return {**made, "url": str(request.base_url).rstrip("/")}


@router.post("/api/pairing/telegram/code")
def api_telegram_pairing_code(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    """Create a short-lived Telegram link code for the signed-in owner account."""
    admin = _d._require_admin(token)
    try:
        made = vault.paired_devices().new_telegram_code(admin)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    money.audit("pairing.telegram_code", by=admin.get("username"))
    return made


@router.get("/api/pairing/telegram")
def api_telegram_pairings(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    """List Telegram senders explicitly linked to owner accounts."""
    _d._require_admin(token)
    return {"links": vault.paired_devices().telegram_links()}


@router.post("/api/pairing/telegram/{telegram_id}/revoke")
def api_telegram_pairing_revoke(telegram_id: str, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    """Unlink a Telegram sender from the owner profile while keeping its own history."""
    admin = _d._require_admin(token)
    if not vault.paired_devices().unlink_telegram(telegram_id):
        raise HTTPException(status_code=404, detail="Telegram account is not linked")
    money.audit("pairing.telegram_revoked", by=admin.get("username"), telegram_id=telegram_id)
    return {"ok": True}


@router.post("/api/pairing/enroll")
def api_pairing_enroll(body: EnrollBody, request: Request):
    """A new device trades the code for its own token. No login needed, but wrong codes are rate limited."""
    who = request.client.host if request.client else ""
    try:
        device, device_token = vault.paired_devices().enroll(body.code, body.name, body.kind, who)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    money.audit("pairing.enrolled", device=device["name"], kind=device["kind"], permission=device["permission"])
    return {"token": device_token, "device": device}


@router.get("/api/pairing/devices")
def api_pairing_devices(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    _d._require_admin(token)
    return {"devices": vault.paired_devices().list()}


@router.post("/api/pairing/devices/{device_id}/revoke")
def api_pairing_revoke(device_id: str, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    admin = _d._require_admin(token)
    if not vault.paired_devices().revoke(device_id):
        raise HTTPException(status_code=404, detail="No such device")
    money.audit("pairing.revoked", by=admin.get("username"), device_id=device_id)
    return {"ok": True}


class PermissionBody(BaseModel):
    permission: str


@router.post("/api/pairing/devices/{device_id}/permission")
def api_pairing_permission(device_id: str, body: PermissionBody, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    admin = _d._require_admin(token)
    try:
        done = vault.paired_devices().set_permission(device_id, body.permission)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not done:
        raise HTTPException(status_code=404, detail="No such device")
    money.audit("pairing.permission", by=admin.get("username"), device_id=device_id, permission=body.permission)
    return {"ok": True}


@router.get("/api/users")
def api_list_users(_admin: dict = Depends(_d._require_admin)):
    return {"ok": True, "users": users.list_users()}


@router.post("/api/users")
def api_create_user(body: dict, _admin: dict = Depends(_d._require_admin)):
    username = body.get("username", "").strip()
    password = body.get("password", "")
    role = body.get("role", "user")
    display_name = body.get("display_name", "").strip()

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    if role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="Invalid role")

    user = users.create_user(username, password, role, display_name)
    if not user:
        raise HTTPException(status_code=400, detail="Username already exists")

    return {"ok": True, "user": user}


@router.delete("/api/users/{username}")
def api_delete_user(username: str, admin: dict = Depends(_d._require_admin)):
    target_username = username.strip().lower()
    if target_username == admin.get("username"):
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    success = users.delete_user(target_username)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")

    return {"ok": True}


@router.get("/api/user/preferences")
def api_get_preferences(user: dict = Depends(_d._require_auth)):
    prefs = users.get_preferences(user["username"])
    return {"ok": True, "preferences": prefs}


@router.put("/api/user/preferences")
def api_update_preferences(body: dict, user: dict = Depends(_d._require_auth)):
    updates = body.get("preferences", {})
    if not isinstance(updates, dict):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid preferences format")
    result = users.update_preferences(user["username"], updates)
    return {"ok": True, "preferences": result}


