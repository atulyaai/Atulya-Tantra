import asyncio
import json

import httpx
from conftest import authenticate_test_admin

from atulya import server
from atulya.profiles import ProfileStore
from test_chat_voice_mode import _app


def test_weather_fast_path_stream_and_json_use_profile_without_model(project_temp_dir, monkeypatch):
    from tools.plugins.information import weather

    app, provider = _app(project_temp_dir, monkeypatch)
    ProfileStore(project_temp_dir / "data").update("admin", {"city": "Sangam Vihar, New Delhi"})
    calls = []

    async def find_place(name, **kwargs):
        assert name == "Sangam Vihar, New Delhi"
        return {"latitude": 28.5, "longitude": 77.2, "label": "Sangam Vihar"}

    async def forecast(lat, lon, label, when):
        calls.append((lat, lon, when))
        return "☀️ Sangam Vihar\nClear · 24°C · feels 25°C\n📅 Tomorrow: 20–31°C · rain 0%\nOpen-Meteo · 21:30 local"

    monkeypatch.setattr(weather, "find_place", find_place)
    monkeypatch.setattr(weather, "forecast", forecast)

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            authenticate_test_admin(client, app)
            body = {"mode": "voice", "messages": [{"role": "user", "content": "what's the weather tomorrow?"}]}
            result = await client.post("/api/chat", json=body)
            assert result.status_code == 200
            data = result.json()
            assert data["route"] == "voice_fast" and data["receipt"]["tool"] == "get_weather"
            assert "Tomorrow in Sangam Vihar: 20 to 31 degrees, rain 0 percent." in data["text"] and data["ui"] == []
            streamed = await client.post("/api/chat", json={**body, "stream": True})
            events = [json.loads(line[6:]) for line in streamed.text.splitlines() if line.startswith("data: ")]
            assert events[0]["text"].strip() == "Checking the weather."
            assert "Tomorrow in Sangam Vihar: 20 to 31 degrees, rain 0 percent." in events[-2]["text"]
            assert events[-1]["done"] and events[-1]["receipt"]["arguments"] == {"when": "tomorrow"}
            assert not provider.turns
            await client.post("/api/plugins/online-information", json={"enabled": False})
            disabled = await client.post("/api/chat", json=body)
            assert "app or chat" in disabled.json()["text"]

    asyncio.run(run())
    assert calls == [(28.5, 77.2, "tomorrow")] * 2


def test_non_english_preference_uses_model_translation(project_temp_dir, monkeypatch):
    app, provider = _app(project_temp_dir, monkeypatch)
    ProfileStore(project_temp_dir / "data").update("admin", {"language": "hindi"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            authenticate_test_admin(client, app)
            response = await client.post("/api/chat", json={"mode": "voice", "messages": [{"role": "user", "content": "what time is it?"}]})
            assert response.status_code == 200 and "route" not in response.json()
            assert provider.turns
            assert any('"language":"hindi"' in message.content for message in provider.turns[0])

    asyncio.run(run())


def test_fast_app_action_returns_approval_and_no_model_call(project_temp_dir, monkeypatch):
    monkeypatch.setenv("DISPLAY", ":test")
    app, provider = _app(project_temp_dir, monkeypatch)

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            authenticate_test_admin(client, app)
            response = await client.post("/api/chat", json={"mode": "voice", "messages": [{"role": "user", "content": "open calculator"}]})
            assert response.status_code == 200
            data = response.json()
            assert len(data["confirm"]) == 1 and "NOT run" in data["text"]
            assert data["receipt"]["tool"] == "open_app" and not provider.turns

    asyncio.run(run())


def test_fast_path_works_without_model_but_complex_request_needs_it(project_temp_dir, monkeypatch):
    monkeypatch.setattr(server, "_make_brain", lambda config: None)
    # _app normally supplies a stub provider; build settings with it, then remove the model before create_app.
    from atulya.settings import Settings
    app = server.create_app(Settings(assistant_name="Atulya", host="127.0.0.1", port=8501,
                                    data_dir=project_temp_dir / "data", models_dir=project_temp_dir / "models",
                                    model_provider="", model_name="", model_base_url="", model_api_key=""))

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            authenticate_test_admin(client, app)
            simple = await client.post("/api/chat", json={"mode": "voice", "messages": [{"role": "user", "content": "what time is it"}]})
            assert simple.status_code == 200 and simple.json()["route"] == "voice_fast"
            complex_reply = await client.post("/api/chat", json={"mode": "voice", "messages": [{"role": "user", "content": "weather for my trip to Goa next month"}]})
            assert complex_reply.status_code == 503

    asyncio.run(run())
