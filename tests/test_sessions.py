"""Tests for multi-user session management and persistence."""
from __future__ import annotations

import json

import pytest


@pytest.fixture
def users_module(tmp_path, monkeypatch):
    """Isolate users.py on a fresh users.json and sessions.json under tmp_path."""
    import drishti.dashboard.users as users_mod
    users_file = tmp_path / "users.json"
    sessions_file = tmp_path / "sessions.json"
    monkeypatch.setattr(users_mod, "USERS_FILE", users_file)
    monkeypatch.setattr(users_mod, "SESSIONS_FILE", sessions_file)
    # Reset the in-memory session store so previous tests don't leak tokens.
    users_mod._sessions.clear()
    return users_mod


def test_sessions_survive_restart(users_module):
    users_module.create_user("alice", "pw123", role="user", display_name="Alice")
    token = users_module.create_session("alice")
    assert users_module.get_session(token) is not None
    # The session must have been persisted to the sessions file.
    assert users_module.SESSIONS_FILE.exists()
    stored = json.loads(users_module.SESSIONS_FILE.read_text())
    assert token in stored

    # Simulate a server restart: drop the in-memory store, then rehydrate from
    # the persisted file (the same path the import-time bootstrap reads).
    users_module._sessions.clear()
    with users_module._lock:
        users_module._sessions.update(users_module._read_sessions())
    assert users_module.get_session(token) is not None
    assert users_module.get_session(token)["username"] == "alice"


def test_expired_sessions_dropped_on_lookup(users_module):
    import time as _time
    users_module.create_user("bob", "pw", role="user", display_name="Bob")
    token = users_module.create_session("bob")
    # Force expiry.
    users_module._sessions[token]["expires_at"] = _time.time() - 1
    assert users_module.get_session(token) is None
    assert token not in users_module._sessions


def test_kill_user_sessions_clears_all(users_module):
    users_module.create_user("carol", "pw", role="user", display_name="Carol")
    t1 = users_module.create_session("carol")
    t2 = users_module.create_session("carol")
    users_module.kill_user_sessions("carol")
    assert users_module.get_session(t1) is None
    assert users_module.get_session(t2) is None
    # Sessions file should no longer contain either token.
    data = json.loads(users_module.SESSIONS_FILE.read_text())
    assert t1 not in data and t2 not in data


def test_kill_session_persists(users_module):
    users_module.create_user("dave", "pw", role="user", display_name="Dave")
    token = users_module.create_session("dave")
    # Wipe memory to prove the session lives in the file, then rehydrate.
    users_module._sessions.clear()
    with users_module._lock:
        users_module._sessions.update(users_module._read_sessions())
    assert users_module.get_session(token) is not None
    users_module.kill_session(token)
    assert users_module.get_session(token) is None
    # After kill, the on-disk store should not contain the token.
    data = json.loads(users_module.SESSIONS_FILE.read_text())
    assert token not in data
