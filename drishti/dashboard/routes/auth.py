from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from drishti.dashboard import users
from drishti.dashboard.helpers import _require_auth, _require_admin, _jwt_encode

router = APIRouter()


@router.post("/api/auth/login")
def api_auth_login(body: dict):
    username = body.get("username")
    password = body.get("password")
    
    user = users.authenticate(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Wrong username or password")
        
    token = users.create_session(username)
    jwt = _jwt_encode({"sub": username, "role": user.get("role", "user"), "name": user.get("display_name", "")})
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
    return (request.client.host if request.client else "") in ("127.0.0.1", "::1")


@router.get("/api/auth/local")
def api_auth_local(request: Request):
    """Sign in without a password when you are on the computer Atulya runs on.

    Phones and other devices on the network still need to log in. Set
    ``ATULYA_REQUIRE_LOGIN=on`` to turn this off.
    """
    from drishti.dashboard.state import ADMIN_TOKEN

    if os.environ.get("ATULYA_REQUIRE_LOGIN", "").strip().lower() in ("on", "1", "true", "yes"):
        raise HTTPException(status_code=403, detail="Login required")
    if not _is_local_request(request):
        raise HTTPException(status_code=403, detail="Login required")
    return {"ok": True, "token": ADMIN_TOKEN,
            "user": {"username": "admin", "role": "admin", "display_name": "Admin"}}


@router.post("/api/auth/verify")
def api_auth_verify(user: dict = Depends(_require_auth)):
    return {
        "ok": True,
        "user": user
    }


@router.post("/api/auth/logout")
def api_auth_logout(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    if token:
        users.kill_session(token)
    return {"ok": True}


@router.get("/api/users")
def api_list_users(_admin: dict = Depends(_require_admin)):
    return {"ok": True, "users": users.list_users()}


@router.post("/api/users")
def api_create_user(body: dict, _admin: dict = Depends(_require_admin)):
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
def api_delete_user(username: str, admin: dict = Depends(_require_admin)):
    target_username = username.strip().lower()
    if target_username == admin.get("username"):
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    success = users.delete_user(target_username)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")

    return {"ok": True}


@router.get("/api/user/preferences")
def api_get_preferences(user: dict = Depends(_require_auth)):
    prefs = users.get_preferences(user["username"])
    return {"ok": True, "preferences": prefs}


@router.put("/api/user/preferences")
def api_update_preferences(body: dict, user: dict = Depends(_require_auth)):
    updates = body.get("preferences", {})
    if not isinstance(updates, dict):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid preferences format")
    result = users.update_preferences(user["username"], updates)
    return {"ok": True, "preferences": result}
