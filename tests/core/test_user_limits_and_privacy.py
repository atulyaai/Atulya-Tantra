"""PLAN M12-4 (per-user daily limits, admin-managed) and M12-5 (the admin cannot read other users' chats)."""
import asyncio
from pathlib import Path

import httpx
import pytest

from atulya import server
from atulya.profiles import ProfileStore
from atulya.settings import Settings
from tools.plugins.brain import Brain
from tools.plugins.registry import PluginContext
from tools.plugins.toolkit import TOOLS, Toolbox


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
                c.cookies.set("atulya_session", sessions[who])
                return await c.request(method, path, json=body)
        return asyncio.run(run())

    return call, app


def _chat(call, who, text="hello there", conversation="c1"):
    return call(who, "POST", "/api/chat", {"conversation_id": conversation,
                                           "messages": [{"role": "user", "content": text}]})


def test_message_limit_is_enforced_and_admin_managed(api):
    call, _app = api
    assert call("bob", "PUT", "/api/auth/users/bob/limits", {"messages_per_day": 99}).status_code == 403
    assert call("admin", "PUT", "/api/auth/users/bob/limits", {"messages_per_day": 2}).json()["limits"] == {
        "messages_per_day": 2, "tools_per_day": 150}
    assert [_chat(call, "bob").status_code for _ in range(3)] == [200, 200, 429]
    for _ in range(3):  # the admin has no limit
        assert _chat(call, "admin").status_code == 200
    bob = next(u for u in call("admin", "GET", "/api/auth/users").json()["users"] if u["id"] == "bob")
    assert bob["usage_today"]["messages"] == 2 and bob["limits"]["messages_per_day"] == 2
    assert bob["age_group"] == "child" and bob["age_source"] == "none"
    assert call("admin", "PUT", "/api/auth/users/bob/limits", {"messages_per_day": None}).json()["limits"][
        "messages_per_day"] == 300  # back to the default
    assert call("admin", "PUT", "/api/auth/users/bob/limits", {"tools_per_day": -1}).status_code == 422


def test_tool_limit_counts_calls(tmp_path):
    store = ProfileStore(tmp_path)
    store.set_limits("bob", {"tools_per_day": 1})
    box = Toolbox(TOOLS, PluginContext("web", None, None, "bob", profile=store, is_admin=False))
    assert asyncio.run(box.call("calculate", {"expression": "1+1"})).strip().endswith("2")
    assert "limit" in asyncio.run(box.call("calculate", {"expression": "2+2"}))
    admin = Toolbox(TOOLS, PluginContext("web", None, None, "admin", profile=store, is_admin=True))
    assert asyncio.run(admin.call("calculate", {"expression": "2+2"})).strip().endswith("4")


def test_admin_cannot_read_other_users_chats(api):
    call, _app = api
    _chat(call, "bob", "my secret plan is mangoes", conversation="bob-chat")
    call("bob", "POST", "/api/conversations/bob-chat/messages",
         {"message_id": "m1", "role": "user", "content": "my secret plan is mangoes"})
    assert "mangoes" in str(call("bob", "GET", "/api/conversations/bob-chat").json())
    assert "mangoes" not in str(call("admin", "GET", "/api/conversations/bob-chat").json())
    assert "bob-chat" not in str(call("admin", "GET", "/api/conversations").json())
    assert call("admin", "DELETE", "/api/conversations/bob-chat").json() == {"deleted_messages": 0}
    assert "mangoes" in str(call("bob", "GET", "/api/conversations/bob-chat").json())  # untouched
