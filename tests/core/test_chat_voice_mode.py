"""/api/chat mode="voice" sends only the voice tool subset to the model (PLAN M1-B1)."""
import asyncio
from pathlib import Path

import httpx
from conftest import authenticate_test_admin

from atulya import server
from atulya.settings import Settings
from tools.plugins.brain import Brain
from tools.plugins.toolkit import VOICE_TOOLS


class _StubProvider:
    name = "stub"
    model = "stub-model"

    def __init__(self):
        self.tool_counts = []
        self.system_prompts = []
        self.turns = []

    async def complete(self, messages):
        return "ok"

    async def stream(self, messages, tools=None):
        self.turns.append(list(messages))
        self.tool_counts.append(len(tools or []))
        self.system_prompts.append(messages[0].content)
        yield "It is sunny."


def _app(tmp: Path, monkeypatch):
    provider = _StubProvider()
    monkeypatch.setattr(server, "_make_brain", lambda config: Brain(provider, assistant_name="Atulya"))
    settings = Settings(assistant_name="Atulya", host="127.0.0.1", port=8501, data_dir=tmp / "data",
                        models_dir=tmp / "models", model_provider="", model_name="", model_base_url="",
                        model_api_key="")
    return server.create_app(settings), provider


def test_voice_mode_uses_tool_subset(project_temp_dir, monkeypatch):
    app, provider = _app(project_temp_dir, monkeypatch)

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            authenticate_test_admin(client, app)
            body = {"messages": [{"role": "user", "content": "tell me something nice"}]}
            text = await client.post("/api/chat", json=body)
            voice = await client.post("/api/chat", json={**body, "mode": "voice"})
            bad = await client.post("/api/chat", json={**body, "mode": "shout"})
            return text, voice, bad

    text, voice, bad = asyncio.run(run())
    assert text.status_code == 200 and voice.status_code == 200 and bad.status_code == 422
    text_tools, voice_tools = provider.tool_counts[0], provider.tool_counts[-1]
    assert 0 < voice_tools <= len(VOICE_TOOLS) < text_tools
    assert "spoken" in provider.system_prompts[-1] and "spoken conversation" not in provider.system_prompts[0]


def test_voice_prefix_stays_fixed_with_different_profiles(project_temp_dir, monkeypatch):
    from atulya.profiles import ProfileStore

    app, provider = _app(project_temp_dir, monkeypatch)
    profiles = ProfileStore(project_temp_dir / "data")

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            authenticate_test_admin(client, app)
            body = {"mode": "voice", "messages": [{"role": "user", "content": "tell me something nice"}]}
            profiles.update("admin", {"city": "Delhi", "preferred_name": "AJ"})
            assert (await client.post("/api/chat", json=body)).status_code == 200
            profiles.update("admin", {"city": "Mumbai", "preferred_name": "Sam"})
            assert (await client.post("/api/chat", json=body)).status_code == 200

    asyncio.run(run())
    assert provider.system_prompts[0] == provider.system_prompts[-1]
    assert "Delhi" not in provider.system_prompts[0] and "Mumbai" not in provider.system_prompts[-1]
    assert any("Delhi" in m.content and m.role == "user" for m in provider.turns[0][1:])
    assert any("Mumbai" in m.content and m.role == "user" for m in provider.turns[-1][1:])


def test_transcribe_uses_authenticated_profile_language(project_temp_dir, monkeypatch):
    from atulya.profiles import ProfileStore

    app, _ = _app(project_temp_dir, monkeypatch)
    ProfileStore(project_temp_dir / "data").update("admin", {"language": "english"})
    seen = []

    def transcribe(self, audio, *, content_type, language):
        seen.append(language)
        return "hello"

    monkeypatch.setattr(server.LocalVoice, "transcribe", transcribe)

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            authenticate_test_admin(client, app)
            for data in ({}, {"language": "hi"}):
                response = await client.post("/api/voice/transcribe", files={"audio": ("test.wav", b"audio", "audio/wav")}, data=data)
                assert response.status_code == 200 and response.json()["text"] == "hello"

    asyncio.run(run())
    assert seen == ["english", "hi"]
