"""Dwar (द्वार, gate): the server's API: accounts and sessions, chat history, sign-in, brains and keys, chat and voice, home and dashboard, automation."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import html
import json
import logging
import os
import platform
import re
import secrets
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import psutil
from pydantic import BaseModel
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse

from atulya import dwar as chat_history
from atulya import dwar as helpers
from atulya import dwar as users
from atulya import kriya as money
from atulya import push as push_service
from atulya import dut as computer_agent
from atulya import phone as phone_store
from atulya import raksha as vault
from atulya.adhar import get_config, set_env_value
from atulya.kaushal import AtulyaTantraConnector, CreationResult
from atulya.mastishk import BY_ID, CATALOG
from atulya.smriti import build_memory_graph
from atulya.upakaran import DeviceError, discover, get_hub
from atulya.vani import VoicePipeline

# ── khata ────────────────────────────────────────────────────────────
# ── state ────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[1]
# Dashboard runtime files (automation jobs). Git-ignored.
OUTPUTS_DIR = _ROOT / "outputs"
MAX_PROMPT_CHARS = 20_000
MAX_CHAT_TOKENS = 4096

def _load_admin_token() -> tuple[str, str]:
    env_token = os.environ.get("ATULYA_DASHBOARD_TOKEN")
    if env_token:
        return env_token, "env"
    return secrets.token_urlsafe(24), "generated_runtime"


ADMIN_TOKEN, ADMIN_TOKEN_SOURCE = _load_admin_token()


def _load_jwt_secret() -> str:
    """The key that signs sign-in tokens (including 90-day device tokens).

    ATULYA_JWT_SECRET wins; a configured ATULYA_DASHBOARD_TOKEN keeps working as
    before; otherwise a random key is created once in kosh/jwt_secret.key
    (owner-only) so tokens survive restarts and every worker agrees on it.
    """
    if os.environ.get("ATULYA_JWT_SECRET"):
        return os.environ["ATULYA_JWT_SECRET"]
    # Never derive the signing key from the dashboard token: that token appears
    # in logs and examples, so a JWT signed with it would be forgeable.
    path = Path(os.environ.get("ATULYA_JWT_SECRET_FILE") or _ROOT / "kosh" / "jwt_secret.key")
    for _ in range(2):
        try:
            existing = path.read_text(encoding="utf-8").strip()
            if existing:
                return existing
        except OSError:
            pass
        secret = secrets.token_urlsafe(48)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue  # another worker created it first: read theirs
        except OSError:
            return secret  # read-only disk: tokens last until restart
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(secret)
        return secret
    return secrets.token_urlsafe(48)


JWT_SECRET = _load_jwt_secret()


# ── users ────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

USERS_FILE = _ROOT / "kosh" / "users.json"
SESSIONS_FILE = _ROOT / "kosh" / "sessions.json"

_lock = threading.Lock()

# In-memory session store: {session_token: {"username": ..., "role": ..., ...}}
_sessions: dict[str, dict[str, Any]] = {}



def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Hash a password with PBKDF2-HMAC-SHA256 + salt. Returns (hash, salt)."""
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return dk.hex(), salt


def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verify a password against its stored hash."""
    computed, _ = _hash_password(password, salt)
    return secrets.compare_digest(computed, stored_hash)



def _read_store() -> dict:
    """Read the users JSON file."""
    if not USERS_FILE.exists():
        return {"users": {}}
    try:
        data = json.loads(USERS_FILE.read_text(encoding="utf-8"))
        if "users" not in data:
            data["users"] = {}
        return data
    except Exception as exc:
        logger.warning("Failed to read users file: %s", exc)
        return {"users": {}}


def _write_store(data: dict) -> None:
    """Write the users JSON file."""
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _read_sessions() -> dict[str, dict[str, Any]]:
    """Read the sessions JSON file into memory."""
    if not SESSIONS_FILE.exists():
        return {}
    try:
        data = json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception as exc:
        logger.warning("Failed to read sessions file: %s", exc)
    return {}


def _save_sessions() -> None:
    """Persist the in-memory sessions to disk."""
    SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not _sessions:
        if SESSIONS_FILE.exists():
            SESSIONS_FILE.write_text("{}", encoding="utf-8")
        return
    SESSIONS_FILE.write_text(
        json.dumps(_sessions, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _prune_expired_sessions() -> None:
    """Drop expired sessions and persist the cleaned store."""
    expired = [t for t, s in _sessions.items() if time.time() > s.get("expires_at", 0)]
    if not expired:
        return
    for t in expired:
        _sessions.pop(t, None)
    _save_sessions()


# Load persisted sessions into memory on import so logins survive a restart.
with _lock:
    _sessions.update(_read_sessions())
    _prune_expired_sessions()



def create_user(
    username: str,
    password: str,
    role: str = "user",
    display_name: str = "",
) -> dict | None:
    """Create a new user. Returns user dict or None if username exists."""
    username = username.strip().lower()
    if not username or not password:
        return None

    with _lock:
        store = _read_store()
        if username in store["users"]:
            return None

        pw_hash, salt = _hash_password(password)
        user = {
            "password_hash": pw_hash,
            "salt": salt,
            "role": role,
            "display_name": display_name or username.title(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        store["users"][username] = user
        _write_store(store)

    logger.info("Created user: %s (role=%s)", username, role)
    return {"username": username, "role": role, "display_name": user["display_name"]}


def authenticate(username: str, password: str) -> dict | None:
    """Authenticate a user. Returns user info dict or None."""
    if not username or not password:
        return None
    username = username.strip().lower()

    with _lock:
        store = _read_store()

    user = store["users"].get(username)
    if not user:
        return None

    if not _verify_password(password, user["password_hash"], user["salt"]):
        return None

    return {
        "username": username,
        "role": user["role"],
        "display_name": user["display_name"],
    }


def list_users() -> list[dict]:
    """List all users (without password hashes)."""
    with _lock:
        store = _read_store()
    result = []
    for uname, data in store["users"].items():
        result.append({
            "username": uname,
            "role": data["role"],
            "display_name": data["display_name"],
            "created_at": data.get("created_at", ""),
        })
    return result


def delete_user(username: str) -> bool:
    """Delete a user. Returns True if deleted."""
    username = username.strip().lower()
    with _lock:
        store = _read_store()
        if username not in store["users"]:
            return False
        del store["users"][username]
        _write_store(store)
    # Also remove any active sessions for this user
    kill_user_sessions(username)
    logger.info("Deleted user: %s", username)
    return True


def create_session(username: str) -> str:
    """Create a session token for a user. Returns the token."""
    username = username.strip().lower()
    with _lock:
        store = _read_store()
        user = store["users"].get(username)
        if not user:
            raise ValueError(f"User {username} not found")

        token = secrets.token_urlsafe(32)
        _sessions[token] = {
            "username": username,
            "role": user["role"],
            "display_name": user["display_name"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": time.time() + 86400,
        }
        _save_sessions()
    return token


def get_session(token: str | None) -> dict | None:
    """Look up a session by token. Returns user info or None."""
    if not token:
        return None
    session = _sessions.get(token)
    if session is None:
        return None
    if time.time() > session.get("expires_at", 0):
        with _lock:
            _sessions.pop(token, None)
            _save_sessions()
        return None
    return session


def kill_session(token: str) -> None:
    """Remove a session."""
    with _lock:
        _sessions.pop(token, None)
        _save_sessions()


def kill_user_sessions(username: str) -> None:
    """Remove all sessions for a specific user."""
    username = username.strip().lower()
    with _lock:
        to_remove = [t for t, s in _sessions.items() if s["username"] == username]
        for t in to_remove:
            _sessions.pop(t, None)
        _save_sessions()



def seed_default_admin() -> None:
    """Create a default admin user if no users exist.

    Uses ATULYA_DASHBOARD_TOKEN env var as default admin password,
    or generates a random one and writes it to kosh/admin_token.txt.
    """
    with _lock:
        store = _read_store()

    if store["users"]:
        logger.info("Users file has %d user(s). Skipping seed.", len(store["users"]))
        return

    password = os.environ.get("ATULYA_DASHBOARD_TOKEN") or secrets.token_urlsafe(12)
    create_user("admin", password, role="admin", display_name="Admin")

    if not os.environ.get("ATULYA_DASHBOARD_TOKEN"):
        token_file = _ROOT / "kosh" / "admin_token.txt"
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(password, encoding="utf-8")
        print("\n  +------------------------------------------+")
        print("  |  Default admin account created:          |")
        print("  |                                          |")
        print("  |  Username: admin                         |")
        print(f"  |  Password written to: {str(token_file):<15s}|")
        print("  |                                          |")
        print("  |  Change this after first login!          |")
        print("  +------------------------------------------+\n")
    else:
        print("\n  +------------------------------------------+")
    print("  |  Default admin account created:          |")
    print("  |                                          |")
    print("  |  Username: admin                         |")
    print("  |  Password: (from env var)                |")
    print("  |                                          |")
    print("  |  Change this after first login!          |")
    print("  +------------------------------------------+\n")


def get_preferences(username: str) -> dict:
    username = username.strip().lower()
    with _lock:
        store = _read_store()
    user = store["users"].get(username)
    if not user:
        return {}
    return user.get("preferences", {})


def update_preferences(username: str, updates: dict) -> dict:
    username = username.strip().lower()
    with _lock:
        store = _read_store()
        if username not in store["users"]:
            return {}
        current = store["users"][username].get("preferences", {})
        current.update(updates)
        store["users"][username]["preferences"] = current
        _write_store(store)
    return current


# ── helpers ────────────────────────────────────────────────────────────
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
    from atulya import dwar as users
    if token:
        user = users.get_session(token)
        if user:
            return user
        if token == ADMIN_TOKEN:
            return {"username": "admin", "role": "admin", "display_name": "Admin"}
        device = vault.paired_devices().authenticate(token)
        if device:  # a paired phone or computer: everyday access only, never admin
            return {"username": f"device:{device['id']}", "role": "device", "display_name": device["name"],
                    "device_id": device["id"], "permission": device["permission"],
                    "profile_user": device.get("owner_username", ""),
                    "profile_display_name": device.get("owner_display_name", "")}
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


# ── chat_history ────────────────────────────────────────────────────────────
HISTORY_FILE = _ROOT / "kosh" / "chat_history.json"
_MAX_MESSAGES = 300


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_history() -> dict[str, Any]:
    if not HISTORY_FILE.exists():
        return {"users": {}}
    try:
        data = json.loads(vault.read_text(HISTORY_FILE))
    except vault.VaultLocked:
        raise  # locked is not empty: callers must not overwrite it
    except Exception:
        return {"users": {}}
    if not isinstance(data, dict):
        return {"users": {}}
    data.setdefault("users", {})
    return data


def _write_history(data: dict[str, Any]) -> None:
    vault.write_text(HISTORY_FILE, json.dumps(data, indent=2, ensure_ascii=False))


def _user_key(user: dict[str, Any] | None) -> str:
    return str((user or {}).get("username") or "anonymous").strip().lower() or "anonymous"


def list_messages(user: dict[str, Any] | None, limit: int = 120) -> list[dict[str, Any]]:
    key = _user_key(user)
    with _lock:
        store = _read_history()
        messages = list(store["users"].get(key, {}).get("messages") or [])
    return messages[-max(1, min(limit, _MAX_MESSAGES)):]


def append_exchange(
    user: dict[str, Any] | None,
    prompt: str,
    response: str,
    *,
    provider: str = "",
    surface: str = "chat",
) -> None:
    prompt = str(prompt or "").strip()
    response = str(response or "").strip()
    if not prompt and not response:
        return

    key = _user_key(user)
    created = _now()
    new_messages = []
    if prompt:
        new_messages.append({"role": "user", "text": prompt, "created_at": created, "surface": surface})
    if response:
        new_messages.append({
            "role": "assistant",
            "text": response,
            "created_at": _now(),
            "surface": surface,
            "provider": provider,
        })

    try:
        with _lock:
            store = _read_history()
            user_store = store["users"].setdefault(key, {"messages": []})
            user_store["messages"] = (list(user_store.get("messages") or []) + new_messages)[-_MAX_MESSAGES:]
            user_store["updated_at"] = _now()
            _write_history(store)
    except vault.VaultLocked:
        pass  # history is locked (wrong passphrase): skip saving rather than break the chat or overwrite it


def clear_messages(user: dict[str, Any] | None) -> None:
    key = _user_key(user)
    with _lock:
        store = _read_history()
        if key in store["users"]:
            del store["users"][key]
        _write_history(store)


# ── dwar_khata ────────────────────────────────────────────────────────────
# ── auth ────────────────────────────────────────────────────────────
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
    admin = _require_admin(token)
    try:
        made = vault.paired_devices().new_code(body.permission, owner=admin)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    money.audit("pairing.code", by=admin.get("username"), permission=made["permission"])
    return {**made, "url": str(request.base_url).rstrip("/")}


@router.post("/api/pairing/telegram/code")
def api_telegram_pairing_code(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    """Create a short-lived Telegram link code for the signed-in owner account."""
    admin = _require_admin(token)
    try:
        made = vault.paired_devices().new_telegram_code(admin)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    money.audit("pairing.telegram_code", by=admin.get("username"))
    return made


@router.get("/api/pairing/telegram")
def api_telegram_pairings(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    """List Telegram senders explicitly linked to owner accounts."""
    _require_admin(token)
    return {"links": vault.paired_devices().telegram_links()}


@router.post("/api/pairing/telegram/{telegram_id}/revoke")
def api_telegram_pairing_revoke(telegram_id: str, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    """Unlink a Telegram sender from the owner profile while keeping its own history."""
    admin = _require_admin(token)
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
    _require_admin(token)
    return {"devices": vault.paired_devices().list()}


@router.post("/api/pairing/devices/{device_id}/revoke")
def api_pairing_revoke(device_id: str, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    admin = _require_admin(token)
    if not vault.paired_devices().revoke(device_id):
        raise HTTPException(status_code=404, detail="No such device")
    money.audit("pairing.revoked", by=admin.get("username"), device_id=device_id)
    return {"ok": True}


class PermissionBody(BaseModel):
    permission: str


@router.post("/api/pairing/devices/{device_id}/permission")
def api_pairing_permission(device_id: str, body: PermissionBody, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    admin = _require_admin(token)
    try:
        done = vault.paired_devices().set_permission(device_id, body.permission)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not done:
        raise HTTPException(status_code=404, detail="No such device")
    money.audit("pairing.permission", by=admin.get("username"), device_id=device_id, permission=body.permission)
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


# ── system ────────────────────────────────────────────────────────────
START_TIME = time.time()


def _system_payload() -> dict:
    mem = psutil.virtual_memory()
    disk_root = OUTPUTS_DIR.parent
    disk_root.mkdir(parents=True, exist_ok=True)
    disk = psutil.disk_usage(str(disk_root))
    return {
        "cpu_pct": psutil.cpu_percent(interval=0.0),
        "cpu_count": psutil.cpu_count(logical=True),
        "ram_pct": mem.percent,
        "ram_total_gb": round(mem.total / (1024 ** 3), 2),
        "ram_avail_gb": round(mem.available / (1024 ** 3), 2),
        "disk_free_gb": round(disk.free / (1024 ** 3), 2),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "token_source": ADMIN_TOKEN_SOURCE,
    }


def _format_uptime(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _provider_registry() -> list[dict]:
    try:
        from atulya.mastishk import ProviderRouter

        providers = []
        for provider in ProviderRouter().providers:
            name = provider.name()
            provider_id = name.split(" ", 1)[0].lower()
            providers.append({
                "id": provider_id,
                "name": name,
                "available": bool(provider.is_available()),
            })
        return [{"id": "auto", "name": "Auto Provider", "available": True}] + providers
    except Exception:
        return [{"id": "auto", "name": "Auto Provider", "available": True}]


def _telemetry_events(system: dict, providers: list[dict]) -> list[dict]:
    ready_providers = [item["name"] for item in providers if item.get("available") and item.get("id") != "auto"]
    events = [
        {
            "title": "System Telemetry",
            "desc": f"CPU {system['cpu_pct']}%, RAM {system['ram_pct']}%, disk free {system['disk_free_gb']} GB.",
            "type": "ready" if system["cpu_pct"] < 85 and system["ram_pct"] < 90 else "warning",
        },
        {
            "title": "Provider Router",
            "desc": f"{len(ready_providers)} provider(s) available: {', '.join(ready_providers[:4]) or 'local/offline fallback only'}.",
            "type": "ready" if ready_providers else "standby",
        },
    ]
    return events


@router.get("/api/system")
def api_system(_admin: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(_admin)
    return _system_payload()


@router.get("/api/telemetry")
def api_telemetry(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(token)
    system = _system_payload()
    providers = _provider_registry()
    return {
        "system": {
            **system,
            "uptime_seconds": int(time.time() - START_TIME),
            "uptime": _format_uptime(time.time() - START_TIME),
        },
        "providers": providers,
        "events": _telemetry_events(system, providers),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.get("/api/brain")
def api_brain(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    """Active brain tier (ATULYA_BRAIN), its local model, and the available tiers (admin only)."""
    _require_admin(token)
    from atulya.mastishk import describe

    return describe()


@router.get("/api/audit/verify")
def api_audit_verify(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    """Is the activity log intact? Any edited, removed or reordered line breaks the chain (admin only)."""
    _require_admin(token)
    from atulya.kriya import verify_audit

    return verify_audit()


@router.get("/api/audit")
def api_audit(limit: int = 50, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    """The most recent things Atulya did on your behalf (admin only)."""
    _require_admin(token)
    from atulya.kriya import recent

    return {"events": recent(max(1, min(limit, 500)))}


@router.get("/api/health")
def api_health(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(token)
    warnings = []

    # Check disk space
    mem = psutil.virtual_memory()
    disk_root = OUTPUTS_DIR.parent
    try:
        disk = psutil.disk_usage(str(disk_root))
        if disk.free / (1024**3) < 5:
            warnings.append({"severity": "high", "message": f"Low disk space: {disk.free / (1024**3):.1f} GB free"})
        elif disk.free / (1024**3) < 20:
            warnings.append({"severity": "medium", "message": f"Disk space getting low: {disk.free / (1024**3):.1f} GB free"})
    except Exception:
        pass

    # Check RAM
    if mem.percent > 90:
        warnings.append({"severity": "high", "message": f"Critical RAM usage: {mem.percent}%"})
    elif mem.percent > 80:
        warnings.append({"severity": "medium", "message": f"High RAM usage: {mem.percent}%"})

    return {"ok": True, "warnings": warnings, "healthy": len(warnings) == 0}


@router.get("/api/dashboard/bootstrap")
def api_dashboard_bootstrap(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    payload = {"user": user, "providers": []}
    if user.get("role") == "admin":  # which models and keys are set up is admin business
        payload["providers"] = _provider_registry()
        payload["system"] = _system_payload()
    return payload


# ── profile ────────────────────────────────────────────────────────────
def _store(request: Request):
    from atulya.buddhi import get_kernel
    from atulya.mastishk import get_default_llm

    return get_kernel(getattr(request.app.state, "llm", None) or get_default_llm()).profiles


def _key(user: dict) -> str:
    return str(user.get("profile_user") or user.get("username") or "default")


@router.get("/api/profile")
def api_profile(request: Request, user: dict = Depends(_require_auth)):
    profile = _store(request).view(_key(user))
    profile["display_name"] = (user.get("profile_display_name") or user.get("display_name") or "")
    return profile


@router.post("/api/profile/facts")
def api_add_fact(request: Request, body: dict, user: dict = Depends(_require_auth)):
    """Teach Atulya something: {"text": "my wife's name is Priya"}."""
    from atulya.buddhi import describe_fact, extract_facts

    text = str(body.get("text") or "").strip()
    facts = extract_facts(text)
    if not facts and text:  # anything else is kept as a plain note, in the user's own words
        facts = [{"kind": "note", "key": "note", "value": text[:200]}]
    if not facts:
        raise HTTPException(status_code=400, detail="Tell me something about you")
    stored = _store(request).remember(_key(user), facts)
    return {"ok": True, "facts": [{**f, "text": describe_fact(f)} for f in stored]}


@router.delete("/api/profile/facts/{fact_id}")
def api_forget_fact(fact_id: str, request: Request, user: dict = Depends(_require_auth)):
    if not _store(request).forget(_key(user), fact_id=fact_id):
        raise HTTPException(status_code=404, detail="Fact not found")
    return {"ok": True}


@router.post("/api/profile/trust")
def api_trust(request: Request, body: dict, user: dict = Depends(_require_auth)):
    """Stop asking (trusted=true) or start asking again (false) before an action."""
    store = _store(request)
    key = str(body.get("key") or "")
    if bool(body.get("trusted")):
        known = {a["key"] for a in store.view(_key(user))["approvals"]}
        if key not in known or not store.trust(_key(user), key):
            raise HTTPException(status_code=400, detail="Atulya can only stop asking about actions you've approved")
    else:
        store.untrust(_key(user), key or None)
    return {"ok": True, "trusted": store.view(_key(user))["trusted"]}


@router.delete("/api/profile")
def api_forget_everything(request: Request, user: dict = Depends(_require_auth)):
    _store(request).forget_everything(_key(user))
    return {"ok": True}


# ── providers ────────────────────────────────────────────────────────────
def _mask(value: str) -> str:
    return ("…" + value[-4:]) if len(value) >= 8 else ("set" if value else "")


def _row(spec) -> dict:
    key = os.environ.get(spec.key_var, "")
    row = {"id": spec.id, "label": spec.label, "free": spec.free, "docs": spec.docs, "configured": bool(key),
           "key_hint": _mask(key), "model": os.environ.get(spec.model_var, "") or spec.default_model,
           "default_model": spec.default_model, "needs_url": spec.id == "custom"}
    if spec.id == "custom":
        row["url"] = os.environ.get("ATULYA_CUSTOM_URL", "")
        row["configured"] = bool(row["url"])
    return row


def _provider(spec):
    from atulya.mastishk import OpenAICompatProvider, ProviderRouter

    if not spec.builtin:
        return OpenAICompatProvider(spec)
    wanted = {"anthropic": "Claude", "openai": "OpenAI", "gemini": "Gemini", "groq": "Groq", "nvidia": "NVIDIA",
              "openrouter": "OpenRouter", "opencode": "OpenCode Go"}[spec.id]
    for p in ProviderRouter().providers:
        if wanted.lower() in p.name().lower():
            return p
    raise HTTPException(status_code=404, detail="Provider not found")


@router.get("/api/providers")
def api_providers(user: dict = Depends(_require_admin)):
    from atulya.mastishk import speed_report

    rows = [_row(s) for s in CATALOG]
    return {"providers": rows, **speed_report(linked_cloud=sum(1 for r in rows if r["configured"] and r["id"] != "custom"))}


@router.post("/api/providers/{provider_id}")
def api_set_provider(provider_id: str, body: dict, user: dict = Depends(_require_admin)):
    """{"key": "...", "model": "...", "url": "..."}: any field left out is unchanged; "" removes it."""
    spec = BY_ID.get(provider_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Unknown provider")
    try:
        if "key" in body:
            set_env_value(spec.key_var, str(body["key"]).strip())
        if "model" in body:
            set_env_value(spec.model_var, str(body["model"]).strip())
        if spec.id == "custom" and "url" in body:
            set_env_value("ATULYA_CUSTOM_URL", str(body["url"]).strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not write .env: {exc}") from exc
    return _row(spec)


@router.post("/api/providers/{provider_id}/test")
async def api_test_provider(provider_id: str, user: dict = Depends(_require_admin)):
    spec = BY_ID.get(provider_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Unknown provider")
    provider = _provider(spec)
    if not provider.is_available():
        return {"ok": False, "error": "No key is set yet."}
    started = time.monotonic()
    try:
        text = await asyncio.wait_for(provider.chat("Reply with the single word: ready", "You are a connection test."), 40)
    except Exception as exc:  # noqa: BLE001 - show the provider's own message
        return {"ok": False, "error": str(exc)[:300]}
    return {"ok": True, "seconds": round(time.monotonic() - started, 1), "reply": str(text)[:80]}


# ── vault ────────────────────────────────────────────────────────────
@router.get("/api/vault")
def api_vault_status(user: dict = Depends(_require_admin)):
    return vault.status()


@router.post("/api/vault/encrypt-now")
def api_vault_encrypt(user: dict = Depends(_require_admin)):
    try:
        return {"converted": vault.encrypt_tree(), **vault.status()}
    except vault.VaultLocked as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ── dwar_vartalap ────────────────────────────────────────────────────────────
# ── chat ────────────────────────────────────────────────────────────


def _merge_history(frontend_history: list[dict], server_history: list[dict], limit: int = 10) -> list[dict]:
    """Merge frontend-provided history with server-persisted history, deduplicating by content."""
    seen = set()
    merged = []
    for msg in server_history + frontend_history:
        content = (msg.get("content") or msg.get("text") or "").strip()
        role = msg.get("role", "user")
        if not content:
            continue
        key = f"{role}:{content[:80]}"
        if key in seen:
            continue
        seen.add(key)
        merged.append({"role": role, "content": content})
    return merged[-limit:]


@router.post("/api/chat")
async def api_chat(request: Request, body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    model_id = str(body.get("model_id") or "latest")
    if "\\" in model_id or "/" in model_id:
        return {"error": "Model path not allowed"}
    prompt = str(body.get("prompt") or "")[:MAX_PROMPT_CHARS]
    if not prompt.strip() and not body.get("approved_tool"):
        return {"error": "Say or type something first."}
    from atulya.buddhi import get_kernel
    from atulya.mastishk import get_default_llm

    server_messages = chat_history.list_messages(user, limit=20)
    server_hist = [{"role": m["role"], "content": m["text"]} for m in server_messages if m.get("text")]
    frontend_hist = body.get("history") or []
    history = _merge_history(frontend_hist, server_hist)

    # Every request goes through the cognitive kernel: intent -> safety -> action,
    # or the brain for open conversation.
    kernel = get_kernel(getattr(request.app.state, "llm", None) or get_default_llm())
    response = await kernel.handle(
        prompt,
        user=user,
        history=history,
        approved_tool=body.get("approved_tool") or None,
        provider=str(body.get("provider") or model_id),
        source="chat",
    )
    chat_history.append_exchange(user, prompt, response.text, provider=response.provider)
    return redact_for(user, {
        "response": response.text[:MAX_CHAT_TOKENS * 8],
        "model_id": model_id,
        "provider": response.provider,
        "steps": response.tool_steps,
        "needs_approval": response.needs_approval,
        "pending_tool": response.pending_tool,
        "trace": getattr(response, "trace", []),
    })


@router.post("/api/chat/stream")
async def api_chat_stream(request: Request, body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    model_id = str(body.get("model_id") or "latest")
    prompt = str(body.get("prompt") or "")[:MAX_PROMPT_CHARS]
    if "\\" in model_id or "/" in model_id:
        error = {"error": "Model path not allowed"}
        async def error_events():
            yield f"data: {json.dumps(error)}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        return StreamingResponse(error_events(), media_type="text/event-stream")

    async def events():
        from atulya.buddhi import get_kernel
        from atulya.mastishk import get_default_llm

        try:
            server_messages = chat_history.list_messages(user, limit=20)
            server_hist = [{"role": m["role"], "content": m["text"]} for m in server_messages if m.get("text")]
            frontend_hist = body.get("history") or []
            history = _merge_history(frontend_hist, server_hist)

            kernel = get_kernel(getattr(request.app.state, "llm", None) or get_default_llm())
            response_parts: list[str] = []
            async for event in kernel.stream(
                prompt,
                user=user,
                history=history,
                approved_tool=body.get("approved_tool") or None,
                provider=str(body.get("provider") or model_id),
                source="chat",
            ):
                if event.type == "token":
                    response_parts.append(event.content)
                    yield f"data: {json.dumps({'token': event.content})}\n\n"
                elif event.type == "tool":
                    yield f"data: {json.dumps({'tool': event.metadata})}\n\n"
                elif event.type == "done":
                    chat_history.append_exchange(
                        user,
                        prompt,
                        "".join(response_parts),
                        provider=str(event.metadata.get("provider") or ""),
                    )
                    payload = {"done": True, "model_id": model_id, **event.metadata}
                    yield f"data: {json.dumps(payload)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/api/chat/history")
async def api_chat_history(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    return {"messages": chat_history.list_messages(user)}


@router.delete("/api/chat/history")
async def api_chat_history_clear(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    chat_history.clear_messages(user)
    return {"ok": True}


# ── openai ────────────────────────────────────────────────────────────
def _model_registry() -> list[dict]:
    """The assistant is exposed as a single model; the brain routes behind it."""
    return [{"id": "atulya", "label": "Atulya", "owned_by": "atulya"}]


def _require_bearer(authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    parts = authorization.split(" ")
    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = parts[1]
    if token == helpers.ADMIN_TOKEN:
        return
    from atulya import dwar as users
    session = users.get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if session.get("role") != "admin":  # which models are configured is admin business
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/v1/models")
def list_models(authorization: str | None = Header(default=None, alias="Authorization")):
    _require_bearer(authorization)
    return {"object": "list", "data": [{"id": item["id"], "object": "model", **item} for item in _model_registry()]}


# ── voice ────────────────────────────────────────────────────────────


# Initialize voice pipeline components
# We save to the configured Atulya data directory inside the workspace by default.
assets_dir = get_config().data_dir
tts_dir = assets_dir / "audio" / "tts"
stt_dir = assets_dir / "audio" / "stt"

voice_pipeline = VoicePipeline(tts_dir=str(tts_dir), stt_dir=str(stt_dir))


_DEVANAGARI = re.compile(r"[\u0900-\u097F]")


def voice_for_reply(text: str, voice: str) -> str:
    """Keep the chosen gender but speak Hindi replies with a Hindi voice (and back)."""
    lang, _, gender = voice.partition("_")
    if gender not in ("male", "female") or lang not in ("en", "hi"):
        return voice
    return f"{'hi' if _DEVANAGARI.search(text or '') else 'en'}_{gender}"


@router.get("/api/voice/voices")
def get_voices():
    """Get the available voice profiles for high-quality edge-tts."""
    return {
        "voices": [
            {"id": "en_male", "name": "Atulya Neural (Male)", "lang": "en", "voice_id": "en-GB-RyanNeural"},
            {"id": "en_female", "name": "Atulya Neural (Female)", "lang": "en", "voice_id": "en-GB-SoniaNeural"},
            {"id": "hi_male", "name": "Madhur Neural (Hindi Male)", "lang": "hi", "voice_id": "hi-IN-MadhurNeural"},
            {"id": "hi_female", "name": "Swara Neural (Hindi Female)", "lang": "hi", "voice_id": "hi-IN-SwaraNeural"},
            {"id": "sa_male", "name": "Sanskrit Neural (Male)", "lang": "sa", "voice_id": "sa-IN-Neural"},
            {"id": "sa_female", "name": "Sanskrit Neural (Female)", "lang": "sa", "voice_id": "sa-IN-Neural"},
        ]
    }


@router.post("/api/voice/tts")
async def api_voice_tts(
    body: dict, 
    token: str | None = Header(default=None, alias="X-Atulya-Token")
):
    """Text to Speech using high quality edge-tts."""
    _require_auth(token)
    text = str(body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text parameter is required")
    
    voice = str(body.get("voice") or "en_male")
    speed = float(body.get("speed") or 1.0)
    
    try:
        result = await voice_pipeline.tts.synthesize(text=text, voice=voice, speed=speed, save=False)
        if result.provider == "fallback":
            return JSONResponse(
                status_code=200,
                content={
                    "error": "edge-tts is not installed. Using local fallback.",
                    "text": text,
                    "provider": "fallback"
                }
            )
        return {
            "audio_base64": result.audio_base64,
            "format": result.format.value,
            "duration": result.duration,
            "id": result.id,
            "provider": result.provider
        }
    except Exception as e:
        logger.error(f"TTS synthesis failed: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/voice/stt")
async def api_voice_stt(
    file: UploadFile = File(...),
    language: str = Form("en"),
    token: str | None = Header(default=None, alias="X-Atulya-Token")
):
    """Speech to Text by uploading audio file."""
    _require_auth(token)
    try:
        # Create temp audio file
        temp_dir = assets_dir / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_filepath = temp_dir / f"upload_{os.urandom(8).hex()}.wav"
        
        with open(temp_filepath, "wb") as f:
            f.write(await file.read())
            
        result = await voice_pipeline.stt.transcribe(
            audio_path=str(temp_filepath),
            language=language
        )
        
        # Clean up temp file
        if temp_filepath.exists():
            temp_filepath.unlink()
            
        return {
            "text": result.text,
            "language": result.language,
            "confidence": result.confidence,
            "provider": result.provider,
            "error": result.error
        }
    except Exception as e:
        logger.error(f"STT transcription failed: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/voice/chat")
async def api_voice_chat(
    body: dict,
    token: str | None = Header(default=None, alias="X-Atulya-Token")
):
    """Full voice chat round-trip using the Atulya Pluggable Provider Router."""
    user = _require_auth(token)
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
        
    voice = str(body.get("voice") or "en_male")
    # The always-listening app speaks for itself; only these two surfaces are
    # accepted, so a client can never claim a pre-authorized source.
    source = "ambient" if body.get("source") == "ambient" else "voice"
    surface = "ambient" if source == "ambient" else "live"

    # Route through the cognitive kernel (intent -> safety -> action, or the
    # brain). A risky action is answered with a spoken confirmation question;
    # the user's next utterance ("yes" / "no") resolves it.
    response_text = ""
    provider_name = "Atulya Fallback"
    needs_approval = False
    pending_tool = None
    trace: list = []
    try:
        from atulya.buddhi import get_kernel
        server_messages = chat_history.list_messages(user, limit=20)
        server_hist = [{"role": m["role"], "content": m["text"]} for m in server_messages if m.get("text")]
        frontend_hist = body.get("history") or []
        seen = set()
        history = []
        for msg in server_hist + frontend_hist:
            content = (msg.get("content") or msg.get("text") or "").strip()
            role = msg.get("role", "user")
            if not content:
                continue
            key = f"{role}:{content[:80]}"
            if key in seen:
                continue
            seen.add(key)
            history.append({"role": role, "content": content})
        history = history[-10:]

        # A camera frame or screenshot rides along: read it first, then let
        # the brain answer with what was seen.
        brain_prompt = prompt
        if body.get("image"):
            from atulya.indriya import as_context, look

            try:
                seen = await look(str(body["image"]), prompt)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            brain_prompt = as_context(seen) + prompt
        response = await get_kernel().handle(
            brain_prompt,
            user=user,
            history=history,
            provider=str(body.get("provider") or body.get("model_id") or ""),
            source=source,
        )
        response_text, provider_name = response.text, response.provider
        needs_approval, pending_tool = response.needs_approval, response.pending_tool
        trace = getattr(response, "trace", [])
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Intelligence router failure: {exc}")
        response_text = "Sorry, something went wrong while I was thinking. The details are in the server window."
        provider_name = "Diagnostics Fallback"

    reply = {
        "prompt": prompt,
        "response_text": response_text,
        "provider_name": provider_name,
        "needs_approval": needs_approval,
        "pending_tool": pending_tool,
        "trace": trace,
    }
    if body.get("tts") is False:  # the device speaks with its own voice
        chat_history.append_exchange(user, prompt, response_text, provider=provider_name, surface=surface)
        return redact_for(user, reply)

    # 3. Synthesize generated text into premium audio
    try:
        tts_result = await voice_pipeline.tts.synthesize(
            text=response_text, voice=voice_for_reply(response_text, voice), save=False)
        chat_history.append_exchange(user, prompt, response_text, provider=provider_name, surface=surface)
        return redact_for(user, {
            "prompt": prompt,
            "response_text": response_text,
            "audio_base64": tts_result.audio_base64,
            "format": tts_result.format.value,
            "provider": tts_result.provider,
            "provider_name": provider_name,
            "needs_approval": needs_approval,
            "pending_tool": pending_tool,
            "trace": trace,
        })
    except Exception as e:
        logger.error(f"Voice chat TTS synthesis failed: {e}")
        chat_history.append_exchange(user, prompt, response_text, provider=provider_name, surface=surface)
        return redact_for(user, {
            "prompt": prompt,
            "response_text": response_text,
            "provider_name": provider_name,
            "needs_approval": needs_approval,
            "pending_tool": pending_tool,
            "trace": trace,
            "error": f"Audio synthesis failed: {e}"
        })


# ── ws ────────────────────────────────────────────────────────────
_active_connections: set[WebSocket] = set()
_broadcast_history: list[dict[str, Any]] = []


@router.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Authenticate the WebSocket connection via a token query parameter
    # (browsers cannot set arbitrary headers on a WebSocket handshake),
    # falling back to the X-Atulya-Token header if present. The connection is
    # rejected (4401 -> 1008 policy violation) before accept() when unauthenticated.
    token = websocket.query_params.get("token")
    if not token:
        token = websocket.headers.get("x-atulya-token")

    try:
        user = _require_auth(token)
    except Exception:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    _active_connections.add(websocket)

    await websocket.send_json({"type": "welcome", "user": user.get("username"), "role": user.get("role")})

    # Send recent history, flagged so clients can show it without re-alerting.
    for msg in _broadcast_history[-20:]:
        await websocket.send_json({**msg, "replay": True})

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
            # Handle ping/pong
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        _active_connections.discard(websocket)


async def broadcast(event_type: str, data: dict[str, Any]) -> None:
    payload = {"type": event_type, "data": data, "timestamp": time.time()}
    _broadcast_history.append(payload)
    if len(_broadcast_history) > 200:
        _broadcast_history[:] = _broadcast_history[-200:]

    disconnected = set()
    for ws in _active_connections:
        try:
            await ws.send_json(payload)
        except Exception:
            disconnected.add(ws)
    _active_connections.difference_update(disconnected)


async def broadcast_training(status: dict) -> None:
    await broadcast("training_status", status)


async def broadcast_telemetry(telemetry: dict) -> None:
    await broadcast("telemetry", telemetry)


async def broadcast_event(title: str, desc: str, event_type: str = "info") -> None:
    await broadcast("event", {"title": title, "desc": desc, "type": event_type})
    if push_service.configured():
        try:
            # This event stream belongs to the owner/admin; never fan private reminder text out to every user.
            await asyncio.to_thread(push_service.send, "admin",
                                    {"title": title, "body": desc, "type": event_type})
        except Exception:  # noqa: BLE001 - push delivery must not interrupt live events
            logger.exception("Web Push delivery failed")


# ── dwar_ghar ────────────────────────────────────────────────────────────
# ── notifications ────────────────────────────────────────────────────────────

@router.get("/api/notifications/vapid-key")
def notifications_vapid_key(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(token)
    return {"public_key": push_service.public_key(), "available": push_service.configured()}


@router.post("/api/notifications/subscribe")
def subscribe(body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_admin(token)
    try:
        push_service.subscribe(user.get("username", "unknown"), body.get("subscription"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "delivery_configured": push_service.configured()}

@router.post("/api/notifications/unsubscribe")
def unsubscribe(body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_admin(token)
    sub = body.get("subscription") or {}
    username = user.get("username", "unknown")
    endpoint = sub.get("endpoint", "") if isinstance(sub, dict) else ""
    push_service.unsubscribe(username, endpoint)
    return {"ok": True}

@router.post("/api/notifications/test")
async def test_notification(body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_admin(token)
    title = body.get("title", "Test")
    message = body.get("message", "This is a test notification")
    from fastapi.responses import JSONResponse
    if not push_service.configured():
        return JSONResponse({"ok": False, "sent": False, "title": title, "message": message,
                             "detail": "Web Push is not configured on this server."}, status_code=503)
    sent = await asyncio.to_thread(push_service.send, user.get("username", "admin"),
                                    {"title": str(title), "body": str(message), "type": "test"})
    return JSONResponse({"ok": True, "sent": sent > 0, "count": sent, "title": title, "message": message})


# ── memory ────────────────────────────────────────────────────────────
def _vector_count() -> int:
    try:
        import json
        from pathlib import Path

        total = 0
        for f in Path("kosh/memory").glob("*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            total += len(data) if isinstance(data, (list, dict)) else 0
        return total
    except Exception:  # noqa: BLE001 - a count only decorates the view
        return 0


@router.get("/api/memory/graph")
def api_memory_graph(request: Request, user: dict = Depends(_require_auth)):
    from atulya import dwar as chat_history
    from atulya.bhava import MoodState
    from atulya.kriya import TOOL_REGISTRY
    from atulya.mastishk import _SPEED, get_default_llm

    llm = getattr(request.app.state, "llm", None) or get_default_llm()
    mood = getattr(llm, "mood", None) or MoodState.load()
    episodes = [m for m in chat_history.list_messages(user, 60) if m.get("role") == "user"][-24:][::-1]
    brains = [{"name": n, "seconds": round(v["avg"], 1)} for n, v in _SPEED.items() if v.get("avg")]
    return build_memory_graph(
        _store(request).view(_key(user)),
        episodes=episodes,
        skills=[(n, str(t.get("description", ""))) for n, t in TOOL_REGISTRY.items()],
        mood={"mood": mood.label, "energy": round(mood.energy, 2), "valence": round(mood.valence, 2)},
        brains=brains,
        vectors=_vector_count(),
    )


# ── mood ────────────────────────────────────────────────────────────
@router.get("/api/mood")
def api_mood(request: Request, user: dict = Depends(_require_auth)):
    from atulya.bhava import MoodState
    from atulya.mastishk import get_default_llm

    llm = getattr(request.app.state, "llm", None) or get_default_llm()
    mood = getattr(llm, "mood", None) or MoodState.load()
    return {"label": mood.label, "valence": round(mood.valence, 2), "energy": round(mood.energy, 2)}


# ── money ────────────────────────────────────────────────────────────
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
def api_money_inbox(request: Request, user: dict = Depends(_require_admin)):
    """The secret and the address to give your phone's SMS-forwarding app."""
    return {"key": money.inbox_token(), "path": "/api/money/sms", "origin": str(request.base_url).rstrip("/")}


@router.post("/api/money/inbox/rotate")
def api_money_inbox_rotate(user: dict = Depends(_require_admin)):
    return {"key": money.inbox_token(rotate=True)}


# ── paired phone companion ────────────────────────────────────────────────
def _require_phone_device(token: str | None, *, command: bool = False) -> dict[str, Any]:
    device = vault.paired_devices().authenticate(token)
    if not device:
        raise HTTPException(status_code=401, detail="A paired phone token is required.")
    if str(device.get("kind", "")).lower() not in {"phone", "termux", "android"}:
        raise HTTPException(status_code=403, detail="Pair this device as a phone before using phone sync.")
    if command and device.get("permission") != "full":
        raise HTTPException(status_code=403, detail="Phone commands require full permission.")
    return device


@router.post("/api/phone/{kind}")
async def api_phone_receive(kind: str, request: Request,
                            token: str | None = Header(default=None, alias="X-Atulya-Token")):
    """Receive SMS, notification, or location batches from a paired Termux phone."""
    device = _require_phone_device(token)
    if kind not in {"sms", "notifications", "location"}:
        raise HTTPException(status_code=404, detail="Unknown phone inbox type.")
    try:
        content_length = int(request.headers.get("content-length", "0"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid content length.") from exc
    if content_length > 512_000:
        raise HTTPException(status_code=413, detail="Phone sync batch is too large.")
    chunks = []
    received_bytes = 0
    async for chunk in request.stream():
        received_bytes += len(chunk)
        if received_bytes > 512_000:
            raise HTTPException(status_code=413, detail="Phone sync batch is too large.")
        chunks.append(chunk)
    try:
        body = json.loads(b"".join(chunks) or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Send a valid JSON body.") from exc
    if not isinstance(body, dict) or not isinstance(body.get("items"), list):
        raise HTTPException(status_code=422, detail="Send a JSON body with an items array.")
    try:
        result = phone_store.add_items(kind, device["id"], body["items"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    money.audit("phone.inbox", kind=kind, device_id=device["id"], added=result["added"])
    return {"ok": True, **result}


@router.get("/api/phone/inbox")
def api_phone_inbox(kind: str = "all", limit: int = 100, user: dict = Depends(_require_admin)):
    try:
        items = phone_store.list_items(kind, limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"items": items}


@router.delete("/api/phone/inbox")
def api_phone_clear(kind: str = "all", user: dict = Depends(_require_admin)):
    try:
        deleted = phone_store.clear_items(kind)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    money.audit("phone.inbox.cleared", by=user.get("username"), kind=kind, deleted=deleted)
    return {"ok": True, "deleted": deleted}


@router.get("/api/phone/devices")
def api_phone_devices(user: dict = Depends(_require_admin)):
    now = time.time()
    devices = [device for device in vault.paired_devices().list()
               if str(device.get("kind", "")).lower() in {"phone", "termux", "android"} and not device.get("revoked")]
    return {"devices": [{**device, "online": now - float(device.get("last_seen", 0)) < 120} for device in devices]}


class PhoneCommandBody(BaseModel):
    action: str


@router.post("/api/phone/devices/{device_id}/commands")
def api_phone_command(device_id: str, body: PhoneCommandBody, user: dict = Depends(_require_admin)):
    device = next((item for item in vault.paired_devices().list()
                   if item.get("id") == device_id and not item.get("revoked")), None)
    if not device or str(device.get("kind", "")).lower() not in {"phone", "termux", "android"}:
        raise HTTPException(status_code=404, detail="No paired phone with that id.")
    try:
        command = phone_store.enqueue(device_id, body.action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    money.audit("phone.command", by=user.get("username"), device_id=device_id, action=body.action)
    return {"ok": True, "command": command}


@router.get("/api/phone/commands")
def api_phone_commands(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    device = _require_phone_device(token, command=True)
    return {"commands": phone_store.poll(device["id"])}


@router.post("/api/phone/commands/{command_id}/result")
def api_phone_command_result(command_id: str, body: dict,
                             token: str | None = Header(default=None, alias="X-Atulya-Token")):
    device = _require_phone_device(token, command=True)
    result = body.get("result", {})
    if not isinstance(result, dict):
        raise HTTPException(status_code=422, detail="Command result must be an object.")
    if not phone_store.acknowledge(device["id"], command_id, result):
        raise HTTPException(status_code=404, detail="No pending command for this phone.")
    money.audit("phone.command.result", device_id=device["id"], command_id=command_id,
                ok=bool(result.get("ok")))
    return {"ok": True}


# ── outbound companion for a paired computer ─────────────────────────────────
def _require_computer_device(token: str | None) -> dict[str, Any]:
    device = vault.paired_devices().authenticate(token)
    if not device:
        raise HTTPException(status_code=401, detail="A paired computer token is required.")
    if str(device.get("kind", "")).lower() not in {"computer", "laptop", "workstation"}:
        raise HTTPException(status_code=403, detail="Pair this device as a computer before using the companion.")
    return device


class RemoteComputerCommandBody(BaseModel):
    device_id: str
    operation: str
    arguments: dict[str, Any] | None = None


@router.post("/api/agent/computer/commands")
def api_queue_computer_command(body: RemoteComputerCommandBody, user: dict = Depends(_require_admin)):
    device = next((row for row in vault.paired_devices().list()
                   if row.get("id") == body.device_id and not row.get("revoked")), None)
    if not device or str(device.get("kind", "")).lower() not in {"computer", "laptop", "workstation"}:
        raise HTTPException(status_code=404, detail="No paired computer with that id.")
    if device.get("permission") not in {"read", "files", "full"}:
        raise HTTPException(status_code=403, detail="The paired computer has no usable permission.")
    try:
        command = computer_agent.enqueue(body.device_id, body.operation, body.arguments or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    money.audit("computer.command", by=user.get("username"), device_id=body.device_id,
                operation=body.operation)
    return {"ok": True, "command": command}


@router.get("/agent/commands")
def api_computer_poll(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    device = _require_computer_device(token)
    return {"commands": computer_agent.poll(device["id"], device.get("permission", "read"))}


@router.post("/agent/results/{command_id}")
def api_computer_result(command_id: str, body: dict,
                        token: str | None = Header(default=None, alias="X-Atulya-Token")):
    device = _require_computer_device(token)
    result = body.get("result")
    if not isinstance(result, dict):
        raise HTTPException(status_code=422, detail="Command result must be an object.")
    if not computer_agent.result(device["id"], command_id, result):
        raise HTTPException(status_code=404, detail="No outstanding command for this computer.")
    money.audit("computer.command.result", device_id=device["id"], command_id=command_id,
                ok=bool(result.get("ok")))
    return {"ok": True}


# ── dashboard ────────────────────────────────────────────────────────────
SECTIONS = [
    {"id": "system", "label": "System status", "words": ["system", "status", "health", "brain"]},
    {"id": "pc", "label": "PC desktop automation", "words": ["pc", "desktop", "computer"]},
    {"id": "web", "label": "Web browser automation", "words": ["web", "browser", "workflow"]},
    {"id": "home", "label": "Smart home hub", "words": ["home", "smart home", "lights", "devices"]},
    {"id": "calendar", "label": "Calendar & reminders", "words": ["calendar", "reminders", "schedule", "meetings"]},
    {"id": "money", "label": "Money", "words": ["money", "spending", "expenses", "bills", "budget", "finance"]},
    {"id": "media", "label": "Audio media player", "words": ["music", "media", "player", "audio", "song"]},
]


def _web_flow(events: list[dict[str, Any]]) -> dict[str, Any]:
    """The latest web task, as steps (navigate, click, type …) with how it ended."""
    flow: list[dict[str, Any]] = []
    for e in events:
        kind = str(e.get("event", ""))
        if not kind.startswith("web_task."):
            continue
        if kind == "web_task.step":
            if flow and flow[-1].get("end"):
                flow = []  # a new task began after the last one ended
            flow.append({"label": str(e.get("action") or "step"), "url": e.get("url", "")})
        else:
            flow.append({"label": kind.split(".", 1)[1], "url": e.get("url", ""), "end": True,
                         "note": e.get("reason") or e.get("say") or ""})
    goal = next((e.get("goal") for e in reversed(events) if str(e.get("event", "")).startswith("web_task.")), "")
    ended = bool(flow and flow[-1].get("end"))
    return {"goal": goal, "steps": flow[-8:], "state": ("finished" if ended else "running") if flow else "idle"}


def build_dashboard(*, audit: list[dict[str, Any]], speeds: dict[str, dict[str, float]], ready: list[str],
                    calendar: list[dict[str, Any]], reminders: list[dict[str, Any]], devices: dict[str, dict[str, Any]],
                    simulated_home: bool, pc_on: bool, is_admin: bool, now: float | None = None,
                    money: dict[str, Any] | None = None, vault: dict[str, Any] | None = None,
                    fabric: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    now = now or time.time()
    measured = sorted(((n, v["avg"]) for n, v in speeds.items() if v.get("avg")), key=lambda x: x[1])
    tools_used = [e for e in audit if e.get("event") == "tool"]
    music = next((e for e in reversed(tools_used) if e.get("name") == "play_music"), None)
    data: dict[str, Any] = {
        "sections": SECTIONS,
        "calendar": {
            "events": [{"title": e["title"], "time": e["time"], "minutes": e.get("duration", 60)}
                       for e in sorted(calendar, key=lambda x: x["time"]) if now <= e["time"] <= now + 7 * 86400][:8],
            "reminders": [{"message": r.get("message", ""), "time": r.get("scheduled_time")}
                          for r in sorted(reminders, key=lambda x: x.get("scheduled_time") or 0)
                          if (r.get("scheduled_time") or 0) >= now][:8],
        },
        "media": {"now_playing": (music or {}).get("args", {}).get("query", "") if music else "",
                  "at": (music or {}).get("t")},
        "money": money or {},
        "fabric": fabric or [],
        "home": {"simulated": simulated_home,
                 "devices": [{"id": i, **d} for i, d in devices.items()]},
    }
    if is_admin:
        data["system"] = {"agent": "Atulya", "ready": ready, "brains": [{"name": n, "seconds": round(s, 2)} for n, s in measured],
                          "fastest": measured[0][0] if measured else (ready[0] if ready else "none"),
                          "latency": round(measured[0][1], 2) if measured else None, "vault": vault or {}}
        data["pc"] = {"control": pc_on, "recent": [{"name": e.get("name"), "t": e.get("t")} for e in tools_used
                                                    if str(e.get("name", "")).startswith("pc_")][-6:]}
        data["web"] = _web_flow(audit)
    return data


@router.get("/api/dashboard")
def api_dashboard(user: dict = Depends(_require_auth)):
    from atulya import kriya as money
    from atulya import kriya as pc_control
    from atulya import kriya as tools
    from atulya import raksha as vault
    from atulya.kriya import recent
    from atulya.mastishk import _SPEED, ProviderRouter
    from atulya.upakaran import get_hub

    ready = [p.name() for p in ProviderRouter().providers if p.is_available() and p.name() != "No brain loaded"]
    return build_dashboard(
        audit=recent(200), speeds=_SPEED, ready=ready,
        calendar=list(tools._CALENDAR.values()), reminders=list(tools._reminders.values()),
        devices=tools._HOME_DEVICES if (os.environ.get("HOME_ASSISTANT_URL") or tools.simulated_home()) else {}, simulated_home=not os.environ.get("HOME_ASSISTANT_URL"),
        pc_on=pc_control.enabled(),
        is_admin=user.get("role") == "admin", money=money.snapshot(), vault=vault.status(),
        fabric=get_hub().describe(),
    )


@router.post("/api/dashboard/pc-control")
def api_toggle_pc(body: dict, user: dict = Depends(_require_auth)):
    """Switch PC control on or off (admin). It still asks before every action."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    on = bool(body.get("on"))
    set_env_value("ATULYA_PC_CONTROL", "on" if on else "")
    return {"control": on}


@router.post("/api/dashboard/media")
async def api_media(body: dict, user: dict = Depends(_require_auth)):
    from atulya.kriya import media_control

    action = str(body.get("action") or "")
    return {"message": await media_control(action)}


@router.post("/api/dashboard/home")
async def api_home(body: dict, user: dict = Depends(_require_auth)):
    """Turn a light or thermostat on/off from the dashboard. Locks are never touched here."""
    from atulya import kriya as tools

    device = tools._HOME_DEVICES.get(str(body.get("device_id")))
    action = str(body.get("action") or "")
    if device is None or device.get("type") == "lock" or action not in ("on", "off"):
        raise HTTPException(status_code=400, detail="Only lights and thermostats can be switched here")
    return {"message": await tools.home_control(str(body["device_id"]), action)}


# ── fabric ────────────────────────────────────────────────────────────
@router.get("/api/fabric")
def api_fabric(user: dict = Depends(_require_auth)):
    return {"devices": get_hub().describe()}


@router.post("/api/fabric/discover")
async def api_fabric_discover(user: dict = Depends(_require_admin)):
    hub = get_hub()
    found = await discover(profiles=hub.profiles)
    have = {(d.driver, d.address, str(sorted(d.config.items()))) for d in hub.devices.values()}
    fresh = [c for c in found if (c.driver, c.host, str(sorted(c.config.items()))) not in have]
    hub.last_candidates = {c.id: c for c in fresh}
    hub.last_order = [c.id for c in fresh]
    return {"found": [c.to_dict() for c in fresh[:60]]}


@router.post("/api/fabric/add")
async def api_fabric_add(body: dict, user: dict = Depends(_require_admin)):
    try:
        dev = await get_hub().add_candidate(str(body.get("candidate", "")), str(body.get("name", "")), str(body.get("room", "")))
    except DeviceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": dev.id, "name": dev.name, "can": [c.name for c in dev.capabilities]}


@router.post("/api/fabric/{device_id}/do")
async def api_fabric_do(device_id: str, body: dict, user: dict = Depends(_require_auth)):
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
def api_fabric_remove(device_id: str, user: dict = Depends(_require_admin)):
    try:
        return {"removed": get_hub().remove(device_id)}
    except DeviceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── senses ────────────────────────────────────────────────────────────
def _senses(request: Request):
    senses = getattr(request.app.state, "senses", None)
    if senses is None:  # app started without lifespan (e.g. tests)
        from atulya.adhar import default_bus
        from atulya.indriya import Senses

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
    """An always-listening device checking in (see ``python -m atulya.shruti``)."""
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


# ── google ────────────────────────────────────────────────────────────
def redirect_uri(request: Request) -> str:
    """Where Google sends the user back. Set ATULYA_PUBLIC_URL behind a proxy."""
    base = os.environ.get("ATULYA_PUBLIC_URL", "").rstrip("/") or str(request.base_url).rstrip("/")
    return f"{base}/api/google/callback"


@router.get("/api/google/status")
def api_google_status(request: Request, user: dict = Depends(_require_auth)):
    from atulya.jaal import GoogleAccount, client_config

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
    from atulya.jaal import GoogleError, save_client_config

    try:
        save_client_config(str(body.get("client_id") or ""), str(body.get("client_secret") or ""))
    except GoogleError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@router.post("/api/google/connect")
def api_google_connect(request: Request, user: dict = Depends(_require_auth)):
    from atulya.jaal import GoogleError, begin_sign_in

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
    from atulya.jaal import GoogleError, finish_sign_in

    if error:
        return _page("Google sign-in cancelled", "Nothing was connected.", ok=False)
    try:
        _user, email = await finish_sign_in(state, code)
    except GoogleError as exc:
        return _page("Couldn't connect Google", str(exc), ok=False)
    return _page("Google connected", f"Atulya can now use Gmail and Calendar for {email or 'your account'}.", ok=True)


@router.post("/api/google/disconnect")
async def api_google_disconnect(user: dict = Depends(_require_auth)):
    from atulya.jaal import GoogleAccount

    return {"ok": await GoogleAccount(str(user.get("username") or "")).disconnect()}


# ── dwar_karya ────────────────────────────────────────────────────────────
# ── automation_runner ────────────────────────────────────────────────────────────
try:
    from croniter import croniter
except ImportError:  # pragma: no cover
    croniter = None


def _next_job_run(schedule: str, now: float) -> float:
    """Calculate the next interval or cron run without runner state."""
    try:
        return now + max(float(schedule), 1.0)
    except ValueError:
        if croniter is None:
            return now + 60.0
        return croniter(schedule, now).get_next(float)


class AutomationRunner:
    """Run scheduled assistant jobs with persisted lifecycle state and bounds."""

    MAX_RUN_SECONDS = 300
    RUN_STATE_TTL = 7 * 24 * 60 * 60

    def __init__(self, jobs_file: str | Path, llm: Any, interval: float = 1.0):
        self.jobs_file = Path(jobs_file)
        self.llm = llm
        self.interval = interval
        self._running = False
        self._tasks: dict[str, asyncio.Task] = {}

    async def start(self) -> None:
        self._running = True
        while self._running:
            await self.tick()
            await asyncio.sleep(self.interval)

    async def stop(self) -> None:
        self._running = False
        tasks = list(self._tasks.values())
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def tick(self) -> None:
        jobs = self._load_jobs()
        now = time.time()
        changed = False
        for job in jobs:
            if not job.get("enabled", True):
                continue
            if job.get("run_status") == "running":
                if str(job.get("id") or "") in self._tasks:
                    continue
                # The previous process disappeared mid-run. Do not replay a
                # possibly completed side effect after restart; move to the
                # next occurrence and make the interruption visible.
                job.update({"run_status": "interrupted", "run_phase": "server_restarted",
                            "run_progress": 100, "run_updated_at": now,
                            "last_error": "Server restarted during this run; it was not replayed."})
                job["next_run"] = self._next_run(str(job.get("schedule") or "60"), now)
                changed = True
                continue
            next_run = float(job.get("next_run") or 0)
            if next_run <= 0:
                job["next_run"] = self._next_run(str(job.get("schedule") or "60"), now)
                changed = True
                continue
            if next_run > now:
                continue
            command = str(job.get("command") or job.get("callback") or "").strip()
            if command:
                # Persist the next occurrence before any action starts. A
                # process crash can miss this occurrence, but cannot repeat
                # an action whose completion was uncertain.
                job["last_run"] = now
                job["run_count"] = int(job.get("run_count") or 0) + 1
                job["next_run"] = self._next_run(str(job.get("schedule") or "60"), now)
                self._save_jobs(jobs)
                await self.run_job(job)
                changed = False
                continue
            job["last_run"] = now
            job["run_count"] = int(job.get("run_count") or 0) + 1
            job["next_run"] = self._next_run(str(job.get("schedule") or "60"), now)
            changed = True
        if changed:
            self._save_jobs(jobs)

    def _load_jobs(self) -> list[dict[str, Any]]:
        if not self.jobs_file.exists():
            return []
        try:
            return json.loads(self.jobs_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_jobs(self, jobs: list[dict[str, Any]]) -> None:
        self.jobs_file.parent.mkdir(parents=True, exist_ok=True)
        self.jobs_file.write_text(json.dumps(jobs, indent=2), encoding="utf-8")

    async def run_job(self, job: dict[str, Any]) -> dict[str, Any]:
        command = str(job.get("command") or job.get("callback") or "").strip()
        job_id = str(job.get("id") or "")
        started = time.time()
        job.update({"run_status": "running", "run_progress": 0, "run_phase": "starting",
                    "run_started_at": started, "run_updated_at": started,
                    "run_expires_at": started + self.RUN_STATE_TTL})
        self._persist_run_state(job)
        if not command:
            job["last_error"] = "No command configured"
            job.update({"run_status": "failed", "run_progress": 100,
                        "run_phase": "finished", "run_updated_at": time.time()})
            self._persist_run_state(job)
            await self._notify_job(job, error="No command configured")
            return job
        try:
            # Through the cognitive kernel: clear actions ("turn off the lights")
            # run deterministically — the job was authorized when it was
            # created — and open-ended commands ("summarize my unread email")
            # go to the brain. Actions are remembered and published as events.
            from atulya.buddhi import get_kernel

            job.update({"run_progress": 10, "run_phase": "thinking", "run_updated_at": time.time()})
            self._persist_run_state(job)
            response = await asyncio.wait_for(
                get_kernel(self.llm).handle(command, user="automation", source="automation"),
                timeout=self.MAX_RUN_SECONDS,
            )
            job["last_result"] = (response.text or "")[:2000] if response.text is not None else ""
            job["last_provider"] = response.provider if response.provider is not None else ""
            job["last_error"] = ""
            if getattr(response, "needs_approval", False):
                job.update({"run_status": "needs_approval", "run_phase": "waiting_for_owner",
                            "pending_tool": getattr(response, "pending_tool", None)})
            else:
                job.update({"run_status": "completed", "run_phase": "finished", "run_progress": 100})
        except asyncio.CancelledError:
            job.update({"run_status": "cancelled", "run_phase": "cancelled", "last_error": "Cancelled by owner"})
            raise
        except Exception as exc:
            job["last_error"] = "Job exceeded its time limit" if isinstance(exc, asyncio.TimeoutError) else str(exc)
            job["last_result"] = ""
            job["last_provider"] = ""
            job.update({"run_status": "failed", "run_phase": "finished"})
        finally:
            job["run_progress"] = int(job.get("run_progress") or 0) if job.get("run_status") == "needs_approval" else 100
            job["run_updated_at"] = time.time()
            self._persist_run_state(job)
            if job_id:
                self._tasks.pop(job_id, None)
        if job.get("run_status") == "needs_approval":
            await self._notify_job(job, error="Approval required")
        else:
            await self._notify_job(job, error=job.get("last_error") or "")
        return job

    async def start_job(self, job: dict[str, Any]) -> dict[str, Any]:
        """Start a manual run in the background and return its persisted state."""
        job_id = str(job.get("id") or "")
        current = self._tasks.get(job_id)
        if current and not current.done():
            return {**job, "run_status": "running"}
        task = asyncio.create_task(self.run_job(job))
        self._tasks[job_id] = task
        # Yield once so the initial `running` state is written before returning.
        await asyncio.sleep(0)
        return dict(job)

    async def cancel_job(self, job_id: str) -> dict[str, Any] | None:
        """Cancel a running job and wait for its cancelled state to be saved."""
        task = self._tasks.get(job_id)
        if task is None or task.done():
            return None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return next((job for job in self._load_jobs() if str(job.get("id")) == job_id), None)

    def _persist_run_state(self, job: dict[str, Any]) -> None:
        """Persist only lifecycle/result fields, preserving concurrent job edits."""
        if not job.get("id"):
            return
        jobs = self._load_jobs()
        current = next((item for item in jobs if str(item.get("id")) == str(job["id"])), None)
        if current is None:
            current = {"id": str(job["id"])}
            jobs.append(current)
        for key in ("run_status", "run_progress", "run_phase", "run_started_at", "run_updated_at",
                    "run_expires_at", "last_result", "last_provider", "last_error", "pending_tool"):
            if key in job:
                current[key] = job[key]
        self._save_jobs(jobs)

    async def _notify_job(self, job: dict[str, Any], error: str = "") -> None:
        """Emit a completion event for a finished automation job.

        Best-effort: broadcasts to WebSocket listeners and, when a notification
        channel is configured, forwards to the `yantra` notification system.
        Never lets a notification failure abort the job itself.
        """
        name = job.get("name") or job.get("id") or "automation job"
        try:
            # Publish on the event bus so trigger rules can react (e.g. alert on failure).
            from atulya.adhar import default_bus
            event_name = "automation.failed" if error and error != "Approval required" else (
                "automation.pending_approval" if error == "Approval required" else "automation.completed")
            await default_bus.emit(event_name, {
                "job": name,
                "result": str(job.get("last_result") or "")[:500],
                "error": error,
                "source": "automation",
            })
        except Exception:  # pragma: no cover - events are best-effort
            pass

        try:
            desc = (error or "job finished")[:280]
            await broadcast_event(
                f"Automation job: {name}",
                desc,
                event_type="warning" if error == "Approval required" else ("success" if not error else "error"),
            )
        except Exception:  # pragma: no cover - notifications are best-effort
            pass

        try:
            from atulya.sandesh import NotificationSystem
            await NotificationSystem().send(
                f"{name}: {'failed' if error else 'completed'}",
                channel="console",
                title="Automation",
            )
        except Exception:  # pragma: no cover - notifications are best-effort
            pass

    @staticmethod
    def _next_run(schedule: str, now: float) -> float:
        return _next_job_run(schedule, now)


# ── api_agent ────────────────────────────────────────────────────────────
# ── automation ────────────────────────────────────────────────────────────

JOBS_FILE = OUTPUTS_DIR / "automation_jobs.json"


def _load_jobs() -> list[dict]:
    if not JOBS_FILE.exists():
        return []
    try:
        jobs = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
        now = time.time()
        changed = False
        for job in jobs:
            expires = float(job.get("run_expires_at") or 0)
            if expires and expires <= now:
                for key in ("run_status", "run_progress", "run_phase", "run_started_at", "run_updated_at",
                            "run_expires_at", "last_result", "last_provider", "last_error", "pending_tool"):
                    job.pop(key, None)
                changed = True
        if changed:
            _save_jobs(jobs)
        return jobs
    except Exception:
        return []


def _save_jobs(jobs: list[dict]) -> None:
    JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    JOBS_FILE.write_text(json.dumps(jobs, indent=2), encoding="utf-8")


def _valid_job_schedule(value: Any) -> bool:
    """Accept bounded interval seconds or a valid cron expression."""
    schedule = str(value or "").strip()
    if not schedule or len(schedule) > 100:
        return False
    try:
        interval = float(schedule)
        return 1 <= interval <= 365 * 24 * 60 * 60
    except ValueError:
        return bool(croniter and croniter.is_valid(schedule))


def _seed_default_jobs() -> None:
    """Provision a small set of proactive jobs on first launch.

    The AutomationRunner executes each job's command through the LLM with tools
    on its schedule, so Atulya acts without being prompted. Existing files are
    left untouched (idempotent).
    """
    if not JOBS_FILE.exists():
        defaults = [
            {
                "id": "seed_proactive_morning",
                "name": "Morning Initiative",
                "schedule": "86400",
                "command": (
                    "Proactively check current todos, memory notes, and pending "
                    "automation, then summarize what is most important today."
                ),
                "enabled": True,
                "created_at": time.time(),
            },
            {
                "id": "seed_proactive_cleanup",
                "name": "Periodic Cleanup Review",
                "schedule": "43200",
                "command": (
                    "Review recent memory and chat history for stale or outdated notes"
                    " and leave a short maintenance summary."
                ),
                "enabled": False,
                "created_at": time.time(),
            },
        ]
        _save_jobs(defaults)


@router.get("/api/cron/jobs")
def api_cron_jobs(_admin: dict = Depends(_require_admin)):
    return {"jobs": _load_jobs()}


@router.post("/api/cron/jobs")
def api_cron_add_job(body: dict, _admin: dict = Depends(_require_admin)):
    jobs = _load_jobs()
    name = str(body.get("name") or "job").strip()
    schedule = str(body.get("schedule") or "").strip()
    command = str(body.get("command") or body.get("callback") or "").strip()
    if not name or len(name) > 80:
        raise HTTPException(status_code=400, detail="Job name must be 1–80 characters")
    if not _valid_job_schedule(schedule):
        raise HTTPException(status_code=400, detail="Schedule must be 1–31536000 seconds or a valid cron expression")
    if not command or len(command) > 1000:
        raise HTTPException(status_code=400, detail="Job command must be 1–1000 characters")
    job = {
        "id": str(body.get("id") or int(time.time() * 1000)),
        "name": name,
        "schedule": schedule,
        "command": command,
        "enabled": bool(body.get("enabled", True)),
        "created_at": time.time(),
    }
    jobs.append(job)
    _save_jobs(jobs)
    return {"ok": True, "job": job}


@router.delete("/api/cron/jobs/{job_id}")
def api_cron_delete_job(job_id: str, _admin: dict = Depends(_require_admin)):
    jobs = [job for job in _load_jobs() if str(job.get("id")) != job_id]
    _save_jobs(jobs)
    return {"ok": True, "jobs": jobs}


@router.patch("/api/cron/jobs/{job_id}")
def api_cron_update_job(job_id: str, body: dict, _admin: dict = Depends(_require_admin)):
    jobs = _load_jobs()
    for job in jobs:
        if str(job.get("id")) != job_id:
            continue
        for key in ("name", "schedule", "command"):
            if key in body:
                value = str(body.get(key) or "").strip()
                if key == "name" and (not value or len(value) > 80):
                    raise HTTPException(status_code=400, detail="Job name must be 1–80 characters")
                if key == "schedule" and not _valid_job_schedule(value):
                    raise HTTPException(status_code=400, detail="Schedule must be 1–31536000 seconds or a valid cron expression")
                if key == "command" and (not value or len(value) > 1000):
                    raise HTTPException(status_code=400, detail="Job command must be 1–1000 characters")
                job[key] = value
        if "enabled" in body:
            job["enabled"] = bool(body["enabled"])
        job["updated_at"] = time.time()
        _save_jobs(jobs)
        return {"ok": True, "job": job}
    return {"ok": False, "error": "Job not found"}


@router.post("/api/cron/jobs/{job_id}/run")
async def api_cron_run_job(
    request: Request,
    job_id: str,
    _admin: dict = Depends(_require_admin),
):
    jobs = _load_jobs()
    for job in jobs:
        if str(job.get("id")) != job_id:
            continue
        runner = getattr(request.app.state, "automation_runner", None)
        if runner is None:
            from atulya.mastishk import get_default_llm
            runner = AutomationRunner(JOBS_FILE, get_default_llm())
            request.app.state.automation_runner = runner
        started = time.time()
        job["last_run"] = started
        job["run_count"] = int(job.get("run_count") or 0) + 1
        job["next_run"] = _next_job_run(str(job.get("schedule") or "60"), started)
        _save_jobs(jobs)
        job = await runner.start_job(job)
        return {"ok": True, "job": job}
    return {"ok": False, "error": "Job not found"}


@router.post("/api/cron/jobs/{job_id}/cancel")
async def api_cron_cancel_job(
    request: Request,
    job_id: str,
    _admin: dict = Depends(_require_admin),
):
    """Cancel an active manual job. Scheduled jobs remain configured."""
    runner = getattr(request.app.state, "automation_runner", None)
    if runner is None:
        return {"ok": False, "error": "No active job runner"}
    job = await runner.cancel_job(job_id)
    if job is None:
        return {"ok": False, "error": "Job is not running"}
    return {"ok": True, "job": job}


# ── upload ────────────────────────────────────────────────────────────

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "kosh" / "uploads"
_MAX_SIZE = 50 * 1024 * 1024  # 50MB


def _safe_component(value: str, label: str = "identifier") -> str:
    """Reject any path-like input so it can't traverse outside the uploads dir.

    A valid username / file_id is a single path component with no separators,
    no parent references, and no null bytes. Anything else is a traversal
    attempt (e.g. '..', 'a/../../etc', '%2e%2e').
    """
    if not value or value in (".", "..") or "/" in value or "\\" in value or "\x00" in value:
        raise HTTPException(400, f"Invalid {label}")
    if os.path.basename(value) != value:
        raise HTTPException(400, f"Invalid {label}")
    return value


def _resolve_upload_path(username: str, file_id: str) -> Path:
    """Build an uploads path and confirm it stays inside UPLOAD_DIR."""
    _safe_component(username, "username")
    _safe_component(file_id, "file id")
    path = (UPLOAD_DIR / username / file_id).resolve()
    base = UPLOAD_DIR.resolve()
    if base not in path.parents:
        raise HTTPException(400, "Invalid path")
    return path
_ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf", "text/plain", "text/csv",
    "application/json", "application/zip",
}

@router.post("/api/upload")
async def api_upload(
    file: UploadFile = File(...),
    token: str | None = Header(default=None, alias="X-Atulya-Token")
):
    user = _require_auth(token)
    if not file.filename:
        raise HTTPException(400, "No filename")

    ext = Path(file.filename).suffix.lower() if file.filename else ""
    content_type = file.content_type or ""

    if content_type and content_type not in _ALLOWED_TYPES and not content_type.startswith("image/"):
        if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".txt", ".csv", ".json", ".zip"):
            raise HTTPException(400, f"File type '{content_type}' not allowed")

    user_dir = UPLOAD_DIR / user["username"]
    user_dir.mkdir(parents=True, exist_ok=True)

    file_id = f"{uuid.uuid4().hex}{ext}"
    dest = user_dir / file_id

    content = await file.read()
    if len(content) > _MAX_SIZE:
        raise HTTPException(400, f"File too large (max {_MAX_SIZE // 1024 // 1024}MB)")

    dest.write_bytes(content)

    return {
        "ok": True,
        "file_id": file_id,
        "filename": file.filename,
        "size": len(content),
        "url": f"/api/files/{user['username']}/{file_id}",
    }

@router.get("/api/files/{username}/{file_id}")
async def api_get_file(username: str, file_id: str, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    if username != user["username"] and user.get("role") != "admin":
        raise HTTPException(403, "Forbidden")
    file_path = _resolve_upload_path(username, file_id)
    if not file_path.is_file():
        raise HTTPException(404, "File not found")
    from fastapi.responses import FileResponse
    return FileResponse(str(file_path))

@router.get("/api/files")
async def api_list_files(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    user_dir = UPLOAD_DIR / user["username"]
    if not user_dir.exists():
        return {"files": []}
    files = []
    for f in user_dir.iterdir():
        if f.is_file():
            files.append({
                "file_id": f.name,
                "size": f.stat().st_size,
                "modified": f.stat().st_mtime,
            })
    return {"files": sorted(files, key=lambda x: x["modified"], reverse=True)}

@router.delete("/api/files/{file_id}")
async def api_delete_file(file_id: str, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    user = _require_auth(token)
    file_path = _resolve_upload_path(user["username"], file_id)
    if not file_path.is_file():
        raise HTTPException(404, "File not found")
    file_path.unlink()
    return {"ok": True}


# ── agent ────────────────────────────────────────────────────────────
_AGENT = None


def set_agent(agent):
    global _AGENT
    _AGENT = agent


def _get_agent():
    if _AGENT is None:
        raise HTTPException(status_code=503, detail="Atulya Agent not initialized")
    return _AGENT


@router.get("/api/agent/status")
async def agent_status(user: dict = Depends(_require_admin)):
    a = _get_agent()
    return {"tools": a.list_tools(), "status": "ready"}


@router.post("/api/agent/process")
async def agent_process(request: Request, user: dict = Depends(_require_auth)):
    body = await request.json()
    user_input = body.get("input", "")
    history = body.get("history")
    if not user_input:
        return {"status": "error", "message": "No input"}
    a = _get_agent()
    reply = await a.process(user_input, history, user=user)
    return {"status": "success", "reply": reply}


@router.get("/api/agent/tools")
async def agent_tools(user: dict = Depends(_require_admin)):
    a = _get_agent()
    return {"tools": a.list_tools()}


@router.get("/api/agent/schemas")
async def agent_schemas(user: dict = Depends(_require_admin)):
    a = _get_agent()
    return {"schemas": a.get_tool_schemas()}


# ── create ────────────────────────────────────────────────────────────
def _connector() -> AtulyaTantraConnector:
    return AtulyaTantraConnector("kosh/creations")


def _payload(result: CreationResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "format": result.format,
        "path": result.path,
        "fallback": result.fallback,
        "metadata": result.metadata,
        "error": result.error,
    }


def _options(body: dict) -> dict[str, Any]:
    return {key: value for key, value in body.items() if key not in {"prompt", "format", "formats"}}


@router.post("/api/create")
def api_create(body: dict, _user: dict = Depends(_require_auth)):
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return {"ok": False, "error": "prompt is required"}
    connector = _connector()
    formats = body.get("formats")
    if isinstance(formats, list) and formats:
        results = connector.create_multi(prompt, [str(item) for item in formats])
        return {"ok": all(item.ok for item in results), "results": [_payload(item) for item in results]}
    return _payload(connector.create(prompt, str(body.get("format") or "auto"), **_options(body)))


@router.post("/api/create/document")
def api_create_document(body: dict, _user: dict = Depends(_require_auth)):
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return {"ok": False, "error": "prompt is required"}
    return _payload(_connector().create(prompt, str(body.get("format") or "pdf"), **_options(body)))


@router.post("/api/create/video")
def api_create_video(body: dict, _user: dict = Depends(_require_auth)):
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return {"ok": False, "error": "prompt is required"}
    return _payload(_connector().create(prompt, "video", **_options(body)))


# ── triggers ────────────────────────────────────────────────────────────
def _engine(request: Request):
    engine = getattr(request.app.state, "triggers", None)
    if engine is None:  # app started without lifespan (e.g. some tests)
        from atulya.buddhi import TriggerEngine

        engine = TriggerEngine()
        request.app.state.triggers = engine
    return engine


@router.get("/api/triggers")
def api_list_triggers(request: Request, _admin: dict = Depends(_require_admin)):
    return {"triggers": _engine(request).list_rules()}


@router.post("/api/triggers")
def api_add_trigger(request: Request, body: dict, _admin: dict = Depends(_require_admin)):
    try:
        rule = _engine(request).add_rule(body)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "trigger": rule}


@router.delete("/api/triggers/{rule_id}")
def api_delete_trigger(rule_id: str, request: Request, _admin: dict = Depends(_require_admin)):
    if not _engine(request).remove_rule(rule_id):
        raise HTTPException(status_code=404, detail="Trigger not found")
    return {"ok": True}


@router.post("/api/events/emit")
async def api_emit_event(body: dict, _admin: dict = Depends(_require_admin)):
    """Publish an event on the bus — handy for testing trigger rules."""
    from atulya.adhar import default_bus

    event_type = str(body.get("type") or "").strip()
    if not event_type:
        raise HTTPException(status_code=400, detail="type is required")
    payload: dict[str, Any] = body.get("payload") if isinstance(body.get("payload"), dict) else {}
    event = await default_bus.emit(event_type, payload)
    return {"ok": True, "type": event.type}


@router.get("/api/events/recent")
def api_recent_events(limit: int = 50, _admin: dict = Depends(_require_admin)):
    """The assistant's recent 'nervous system' activity."""
    from atulya.adhar import default_bus

    limit = max(1, min(int(limit), 500))
    return {"events": [
        {"type": e.type, "payload": e.payload, "timestamp": getattr(e, "timestamp", None)}
        for e in default_bus.history(limit)
    ]}


# ── routines ────────────────────────────────────────────────────────────
def _kernel(request: Request):
    from atulya.buddhi import get_kernel
    from atulya.mastishk import get_default_llm

    return get_kernel(getattr(request.app.state, "llm", None) or get_default_llm())


@router.get("/api/routines")
def api_list_routines(request: Request, _admin: dict = Depends(_require_admin)):
    from atulya.buddhi import routine_steps

    store = _kernel(request).planner.routines
    return {"routines": [
        {**r, "plan": [s.command for s in routine_steps(r)]} for r in store.list()
    ]}


@router.post("/api/routines")
def api_save_routine(request: Request, body: dict, _admin: dict = Depends(_require_admin)):
    try:
        routine = _kernel(request).planner.routines.save(body)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "routine": routine}


@router.delete("/api/routines/{routine_id}")
def api_delete_routine(routine_id: str, request: Request, _admin: dict = Depends(_require_admin)):
    if not _kernel(request).planner.routines.remove(routine_id):
        raise HTTPException(status_code=404, detail="Routine not found")
    return {"ok": True}


@router.post("/api/routines/{routine_id}/run")
async def api_run_routine(routine_id: str, request: Request, admin: dict = Depends(_require_admin)):
    from atulya.buddhi import Plan, routine_steps

    kernel = _kernel(request)
    routine = kernel.planner.routines.get(routine_id)
    if routine is None:
        raise HTTPException(status_code=404, detail="Routine not found")
    plan = Plan(goal=str(routine["name"]), title=str(routine["name"]), source="routine",
                steps=routine_steps(routine), routine_id=routine_id)
    response = await kernel.start_plan(plan, user=admin, source="chat")
    return {
        "response": response.text,
        "needs_approval": response.needs_approval,
        "pending_tool": response.pending_tool,
        "trace": response.trace,
        "steps": response.tool_steps,
    }


@router.post("/api/plan/preview")
def api_preview_plan(request: Request, body: dict, _admin: dict = Depends(_require_admin)):
    """What Atulya would do for a sentence, without doing it."""
    from atulya.buddhi import steps_for_clause

    text = str(body.get("text") or "").strip()
    plan = _kernel(request).planner.plan(text)
    if plan is not None:
        return {"plan": plan.to_dict()}
    steps = steps_for_clause(text) or []
    return {"plan": {"goal": text, "title": text, "source": "single" if steps else "brain",
                     "steps": [{"command": s.command, "tool": s.tool, "arguments": s.arguments} for s in steps]}}

