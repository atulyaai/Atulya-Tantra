"""B30 (PLAN M10 tail): the proactive inbox API the phone worker polls and acks."""
import asyncio
from pathlib import Path

import httpx
import pytest

from atulya import server
from atulya.inbox import Inbox
from atulya.settings import Settings
from tools.plugins.brain import Brain


class _Provider:
    name = "stub"
    model = "stub"

    async def complete(self, messages):
        return "ok"

    async def stream(self, messages, tools=None):
        yield "Fine."


@pytest.fixture()
def api(project_temp_dir: Path, monkeypatch):
    monkeypatch.setattr(server, "_make_brain", lambda config: Brain(_Provider(), assistant_name="Atulya"))
    settings = Settings(assistant_name="Atulya", host="127.0.0.1", port=8501, data_dir=project_temp_dir / "data",
                        models_dir=project_temp_dir / "models", model_provider="", model_name="",
                        model_base_url="", model_api_key="")
    app = server.create_app(settings)
    sessions = {"admin": app.state.auth_store.create_session("admin"), "bob": app.state.auth_store.create_session("bob")}

    def call(who, method, path, body=None):
        async def run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as c:
                if who:
                    c.cookies.set("atulya_session", sessions[who])
                return await c.request(method, path, json=body)
        return asyncio.run(run())

    return call, app


def test_owner_polls_inbox_notifications_and_they_are_marked_delivered(api):
    call, app = api
    store = Inbox(app.state.settings.data_dir)
    notice_id = store.add("admin", "High disk", "Disk at 93%", "disk", dedupe="disk:2026-11-11T09")

    listed = call("admin", "GET", "/api/notifications/inbox")
    assert listed.status_code == 200
    items = listed.json()["notifications"]
    assert len(items) == 1 and items[0]["id"] == notice_id
    assert "93%" in items[0]["body"] and "disk" in items[0]["kind"]

    # A read marks the notice delivered, so it is not handed out twice.
    assert call("admin", "GET", "/api/notifications/inbox").json()["notifications"] == []


def test_owner_acks_an_inbox_notification(api):
    call, app = api
    store = Inbox(app.state.settings.data_dir)
    notice_id = store.add("admin", "Charging soon", "Battery at 8%", "battery", dedupe="battery:2026-11-11T10")

    acked = call("admin", "POST", "/api/notifications/inbox/ack", {"ids": [notice_id]})
    assert acked.status_code == 200 and acked.json()["marked"] == 1
    assert call("admin", "GET", "/api/notifications/inbox").json()["notifications"] == []


def test_inbox_ack_accepts_an_empty_id_list(api):
    call, _app = api
    result = call("admin", "POST", "/api/notifications/inbox/ack", {"ids": []})
    assert result.status_code == 200 and result.json()["marked"] == 0


def test_inbox_is_available_to_signed_in_users_not_admin_only(api):
    call, _app = api
    assert call("bob", "GET", "/api/notifications/inbox").status_code == 200
    assert call("bob", "POST", "/api/notifications/inbox/ack", {"ids": []}).status_code == 200


def test_inbox_requires_a_session(api):
    call, _app = api
    assert call(None, "GET", "/api/notifications/inbox").status_code == 401
    assert call(None, "POST", "/api/notifications/inbox/ack", {"ids": []}).status_code == 401
