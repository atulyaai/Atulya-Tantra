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
from urllib.parse import parse_qsl, parse_qs

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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse

from atulya import dwar as chat_history
from atulya import dwar as helpers
from atulya import kriya as money
from atulya import sandesh as push_service  # Web Push now lives in sandesh
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


def sync_admin_token() -> str:
    """Re-read ATULYA_DASHBOARD_TOKEN once .env has actually been loaded.

    ADMIN_TOKEN is frozen when this module is imported, but sevak imports it
    (line 18, module scope) before main() reads .env — so without this the
    token set in .env is ignored and a different random one is minted on every
    boot. Every consumer reads ADMIN_TOKEN as a module attribute at call time,
    so reassigning it here reaches them all.
    """
    global ADMIN_TOKEN, ADMIN_TOKEN_SOURCE
    ADMIN_TOKEN, ADMIN_TOKEN_SOURCE = _load_admin_token()
    return ADMIN_TOKEN


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
    configured = os.environ.get("ATULYA_JWT_SECRET_FILE")
    paths = [Path(configured)] if configured else []
    fallback = _ROOT / "kosh" / "jwt_secret.key"
    if fallback not in paths:
        paths.append(fallback)
    for path in paths:
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
                break  # this path is read-only; try the persistent kosh fallback
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


# Route modules register their handlers on ``router`` as they import.
from . import (
    routes_auth,
    routes_system,
    routes_chat,
    routes_voice,
    routes_notify,
    routes_companions,
    routes_fabric,
    routes_automation,
    routes_agent,
)  # noqa: F401
from .routes_auth import *  # noqa: F401,F403
from .routes_system import *  # noqa: F401,F403
from .routes_chat import *  # noqa: F401,F403
from .routes_voice import *  # noqa: F401,F403
from .routes_notify import *  # noqa: F401,F403
from .routes_companions import *  # noqa: F401,F403
from .routes_fabric import *  # noqa: F401,F403
from .routes_automation import *  # noqa: F401,F403
from .routes_agent import *  # noqa: F401,F403


# Private helpers that the server, the CLI and the tests reach through the package.
from .routes_agent import _AGENT, _ALLOWED_TYPES, _HOOKS_FILE, _HOOK_NAME_RE, _MAX_SIZE, _connector  # noqa: F401
from .routes_agent import _dispatch_channel_message, _engine, _get_agent, _hook_summary, _hooks, _kernel  # noqa: F401
from .routes_agent import _options, _payload, _resolve_upload_path, _safe_component, _save_hooks, _validate_twilio_webhook  # noqa: F401
from .routes_auth import _may_skip_login, _telegram_allowed  # noqa: F401
from .routes_automation import _load_jobs, _next_job_run, _save_jobs, _seed_default_jobs, _valid_job_schedule  # noqa: F401
from .routes_chat import _merge_history, _model_registry, _require_bearer  # noqa: F401
from .routes_companions import _MAX_BYTES, _alert_text, _require_computer_device, _require_phone_device, _web_flow  # noqa: F401
from .routes_fabric import _page, _senses  # noqa: F401
from .routes_notify import _vector_count  # noqa: F401
from .routes_system import _format_uptime, _key, _mask, _provider, _provider_registry, _row  # noqa: F401
from .routes_system import _store, _system_payload, _telemetry_events  # noqa: F401
from .routes_voice import _DEVANAGARI, _active_connections, _broadcast_history  # noqa: F401
