"""Voice turns share a byte-identical prompt prefix (system prompt + tool schemas); the city and
time live only in the per-turn Context message after it (PLAN M1-B2/B5)."""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from conftest import authenticate_test_admin

from atulya import server
from atulya.settings import Settings
from tools.plugins.brain import Brain


class _Recorder:
    name = "stub"
    model = "stub-model"

    def __init__(self):
        self.turns = []

    async def complete(self, messages):
        return "ok"

    async def stream(self, messages, tools=None):
        self.turns.append((messages[0].content, json.dumps(tools, sort_keys=True), [m.content for m in messages[1:]]))
        yield "Fine."


def test_voice_prefix_identical_across_city_and_time(project_temp_dir: Path, monkeypatch):
    provider = _Recorder()
    monkeypatch.setattr(server, "_make_brain", lambda config: Brain(provider, assistant_name="Atulya"))
    settings = Settings(assistant_name="Atulya", host="127.0.0.1", port=8501, data_dir=project_temp_dir / "data",
                        models_dir=project_temp_dir / "models", model_provider="", model_name="",
                        model_base_url="", model_api_key="")
    app = server.create_app(settings)
    clock = iter([datetime(2026, 10, 20, 18, 5, tzinfo=timezone(timedelta(hours=5, minutes=30))),
                  datetime(2026, 10, 21, 7, 40, tzinfo=timezone(timedelta(hours=5, minutes=30)))])
    import atulya.voice_context as vc
    original = vc.voice_context
    monkeypatch.setattr(vc, "voice_context", lambda profiles, user_id: original(profiles, user_id, now=next(clock)))

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            authenticate_test_admin(client, app)
            body = {"mode": "voice", "messages": [{"role": "user", "content": "tell me a fun fact about owls"}]}
            assert (await client.put("/api/profile", json={"city": "Delhi"})).status_code == 200
            assert (await client.post("/api/chat", json=body)).status_code == 200
            assert (await client.put("/api/profile", json={"city": "Mumbai"})).status_code == 200
            assert (await client.post("/api/chat", json=body)).status_code == 200

    asyncio.run(run())
    (system_a, tools_a, rest_a), (system_b, tools_b, rest_b) = provider.turns
    assert system_a == system_b and tools_a == tools_b
    for volatile in ("Delhi", "Mumbai", "2026-10-2"):
        assert volatile not in system_a
    assert "Delhi" in rest_a[0] and "2026-10-20T18:05" in rest_a[0]
    assert "Mumbai" in rest_b[0] and "2026-10-21T07:40" in rest_b[0]
