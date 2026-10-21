"""A paired device with the voice_loop ability can call only the voice-loop routes, as its admin owner (PLAN M1-3 R4)."""
import asyncio
from pathlib import Path

import httpx

from atulya import server
from atulya.settings import Settings
from tools.plugins.brain import Brain
from tools.plugins.system.agents import AgentHub


class _Provider:
    name = "stub"
    model = "stub"

    async def complete(self, messages):
        return "ok"

    async def stream(self, messages, tools=None):
        yield "Hello there."


def _app(tmp: Path, monkeypatch):
    monkeypatch.setattr(server, "_make_brain", lambda config: Brain(_Provider(), assistant_name="Atulya"))
    settings = Settings(assistant_name="Atulya", host="127.0.0.1", port=8501, data_dir=tmp / "data",
                        models_dir=tmp / "models", model_provider="", model_name="", model_base_url="",
                        model_api_key="")
    return server.create_app(settings), settings.data_dir


def _call(app, token, path="/api/chat", method="post"):
    body = {"mode": "voice", "messages": [{"role": "user", "content": "tell me something cheerful"}]}

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            if method == "get":
                return await client.get(path, headers=headers)
            return await client.post(path, json=body, headers=headers)

    return asyncio.run(run())


def test_voice_device_token(project_temp_dir, monkeypatch):
    app, data_dir = _app(project_temp_dir, monkeypatch)
    hub = AgentHub(data_dir)
    voice = hub.pair("admin", "Desk PC", ["voice_loop"])["token"]
    plain = hub.pair("admin", "Phone", ["ping"])["token"]
    stranger = hub.pair("guest", "Guest PC", ["voice_loop"])["token"]
    monkeypatch.setattr(app.state.auth_store, "is_admin", lambda user_id: user_id == "admin")

    assert _call(app, voice).status_code == 200
    assert _call(app, None).status_code == 401
    assert _call(app, "wrong-token").status_code == 401
    assert _call(app, plain).status_code == 403          # paired, but no voice_loop ability
    assert _call(app, stranger).status_code == 403       # voice_loop, but its owner is not an admin
    assert _call(app, voice, "/api/profile", "get").status_code == 401  # only the voice routes
    # B17: the voice-loop token can never approve or deny an action, even one that exists.
    queue_action = app.state.action_queue.add("open_app", {"name": "Notepad"}, "Open app: Notepad", "admin")
    action_id = queue_action.id
    for approve in (True, False):
        async def decide():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
                return await client.post(f"/api/actions/{action_id}", json={"approve": approve},
                                         headers={"Authorization": f"Bearer {voice}"})
        assert asyncio.run(decide()).status_code == 401
    assert app.state.action_queue.take(action_id, "admin") is queue_action  # still pending, untouched
    hub.revoke("admin", "Desk PC")
    assert _call(app, voice).status_code == 401
