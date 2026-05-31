"""User store and session management for Atulya Drishti.

Stores users in a JSON file at {project_root}/config/users.json.
Passwords are hashed with SHA-256 + per-user salt.
Sessions are in-memory dicts that reset on server restart.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[2]
USERS_FILE = _ROOT / "config" / "users.json"

_lock = threading.Lock()

# In-memory session store: {session_token: {"username": ..., "role": ..., ...}}
_sessions: dict[str, dict[str, Any]] = {}


# ─── Password Hashing ────────────────────────────────────────────────

def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Hash a password with SHA-256 + salt. Returns (hash, salt)."""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return hashed, salt


def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verify a password against its stored hash."""
    computed, _ = _hash_password(password, salt)
    return secrets.compare_digest(computed, stored_hash)


# ─── File I/O ─────────────────────────────────────────────────────────

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


# ─── User CRUD ────────────────────────────────────────────────────────

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


def update_role(username: str, new_role: str) -> bool:
    """Update a user's role. Returns True if updated."""
    username = username.strip().lower()
    if new_role not in ("admin", "user"):
        return False
    with _lock:
        store = _read_store()
        if username not in store["users"]:
            return False
        store["users"][username]["role"] = new_role
        _write_store(store)
    logger.info("Updated role for %s to %s", username, new_role)
    return True


def user_exists(username: str) -> bool:
    """Check if a user exists."""
    with _lock:
        store = _read_store()
    return username.strip().lower() in store["users"]


# ─── Session Management ──────────────────────────────────────────────

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
    }
    return token


def get_session(token: str | None) -> dict | None:
    """Look up a session by token. Returns user info or None."""
    if not token:
        return None
    return _sessions.get(token)


def kill_session(token: str) -> None:
    """Remove a session."""
    _sessions.pop(token, None)


def kill_user_sessions(username: str) -> None:
    """Remove all sessions for a specific user."""
    username = username.strip().lower()
    to_remove = [t for t, s in _sessions.items() if s["username"] == username]
    for t in to_remove:
        _sessions.pop(t, None)


# ─── Auto-seed ────────────────────────────────────────────────────────

def seed_default_admin() -> None:
    """Create a default admin user if no users exist.

    Uses ATULYA_DASHBOARD_TOKEN env var as default admin password,
    or generates a random one and prints it to console.
    """
    with _lock:
        store = _read_store()

    if store["users"]:
        logger.info("Users file has %d user(s). Skipping seed.", len(store["users"]))
        return

    password = os.environ.get("ATULYA_DASHBOARD_TOKEN") or secrets.token_urlsafe(12)
    create_user("admin", password, role="admin", display_name="Admin")

    print(f"\n  ┌──────────────────────────────────────────┐")
    print(f"  │  Default admin account created:           │")
    print(f"  │                                          │")
    print(f"  │  Username: admin                         │")
    print(f"  │  Password: {password:<29s}│")
    print(f"  │                                          │")
    print(f"  │  Change this after first login!          │")
    print(f"  └──────────────────────────────────────────┘\n")
