"""PLAN M13-5: sign-ins, approvals, device jobs and admin changes are in a tamper-evident log the admin can read."""
import asyncio
import sqlite3
from pathlib import Path

import httpx
import pytest

from atulya import server
from atulya.security_log import SecurityLog
from atulya.settings import Settings
from tools.plugins.system.agents import AgentHub


def test_chain_detects_edits_and_deletions(tmp_path):
    log = SecurityLog(tmp_path)
    for index in range(3):
        log.record("auth", "admin", f"POST /api/auth/login/verify #{index}", outcome="ok 200", ip="127.0.0.1")
    assert log.verify()
    with sqlite3.connect(log.path) as db:
        db.execute("UPDATE events SET outcome='denied 401' WHERE id=2")
    assert not log.verify()
    log2 = SecurityLog(tmp_path / "b")
    for index in range(3):
        log2.record("admin", "admin", f"x{index}")
    with sqlite3.connect(log2.path) as db:
        db.execute("DELETE FROM events WHERE id=2")
    assert not log2.verify()
    with pytest.raises(ValueError):
        log.record("weird", "a", "b")


@pytest.fixture()
def app(project_temp_dir: Path):
    settings = Settings(assistant_name="Atulya", host="127.0.0.1", port=8501, data_dir=project_temp_dir / "data",
                        models_dir=project_temp_dir / "models", model_provider="", model_name="",
                        model_base_url="", model_api_key="")
    application = server.create_app(settings)
    yield application, settings.data_dir
    from atulya.security_log import set_default
    set_default(None)


def _call(app, method, path, cookie=None, body=None):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            if cookie:
                client.cookies.set("atulya_session", cookie)
            return await client.request(method, path, json=body)
    return asyncio.run(run())


def test_events_are_recorded_and_admin_only(app):
    application, data_dir = app
    store = application.state.auth_store
    admin, bob = store.create_session("admin"), store.create_session("bob")
    _call(application, "POST", "/api/auth/login/verify", body={})                  # a failed sign-in attempt
    _call(application, "PUT", "/api/auth/users/bob/limits", bob, {"messages_per_day": 1})   # refused admin change
    _call(application, "PUT", "/api/auth/users/bob/limits", admin, {"messages_per_day": 9})  # admin change
    _call(application, "POST", "/api/devices/pair", bob, {"name": "Bob Phone", "abilities": ["ping"]})
    AgentHub(data_dir).enqueue("bob", "Bob Phone", "ping")
    action = application.state.action_queue.add("open_app", {"name": "Notepad"}, "Open app: Notepad", "admin")
    _call(application, "POST", f"/api/actions/{action.id}", admin, {"approve": False})

    assert _call(application, "GET", "/api/security-log", bob).status_code == 403
    body = _call(application, "GET", "/api/security-log", admin).json()
    assert body["intact"] is True
    events = [(e["kind"], e["actor"], e["action"], e["target"], e["outcome"]) for e in body["events"]]
    assert ("auth", "anonymous", "POST /api/auth/login/verify") in [e[:3] for e in events]
    assert any(e[0] == "auth" and e[4] != "ok 200" for e in events if e[2] == "POST /api/auth/login/verify")
    assert ("admin", "bob", "PUT /api/auth/users/bob/limits", "", "denied 403") in events
    assert ("admin", "admin", "PUT /api/auth/users/bob/limits", "", "ok 200") in events
    assert any(e[:3] == ("device", "bob", "pair") and e[3].startswith("Bob Phone") for e in events)
    assert any(e[:3] == ("device", "bob", "enqueue") and e[3].startswith("Bob Phone: ping") for e in events)
    assert ("approval", "admin", "deny", "open_app", "ok") in events
    # Nothing secret: no device token, no message text, no action summary.
    text = str(body)
    assert "Notepad" not in text and "token" not in text.lower()


def test_device_job_detail_is_never_logged(tmp_path, monkeypatch):
    from atulya.security_log import set_default
    log = SecurityLog(tmp_path)
    set_default(log)
    try:
        hub = AgentHub(tmp_path)
        hub.pair("admin", "Phone", ["send_sms"])
        hub.enqueue("admin", "Phone", "send_sms", "+15550100|meet me at the secret place")
        with pytest.raises(ValueError):
            hub.enqueue("admin", "Phone", "place_call", "+15550100")
    finally:
        set_default(None)
    rows = log.recent()
    assert "secret place" not in str(rows) and "+15550100" not in str(rows)
    assert [r["outcome"] for r in rows if r["action"] == "enqueue"] == ["refused", "ok"]
