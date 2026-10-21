import asyncio
from datetime import datetime, timedelta, timezone

from atulya.profiles import ProfileStore
from atulya.voice_context import voice_context
from tools.plugins.brain import Brain, OpenAICompatibleProvider
from tools.plugins.registry import PluginContext
from tools.plugins.toolkit import _weather


def test_voice_context_is_scoped_and_ignores_stale_location(project_temp_dir, monkeypatch):
    profiles = ProfileStore(project_temp_dir)
    profiles.update("alice", {"city": "Delhi", "preferred_name": "AJ", "language": "english"})
    profiles.update("bob", {"city": "Mumbai"})
    profiles.set_location("alice", 20, 70)
    profiles.set_place("alice", "home", 28.61, 77.21, "Delhi")
    now = datetime(2026, 10, 20, 18, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    fresh = voice_context(profiles, "alice", now=now)
    assert '"source":"device"' in fresh.content and '"lat":20' in fresh.content
    monkeypatch.setattr("atulya.profiles.time.time", lambda: now.timestamp() + 10**10)
    stale = voice_context(profiles, "alice", now=now)
    assert '"source":"saved home"' in stale.content and '"lat":28.61' in stale.content
    assert "Mumbai" not in stale.content and "AJ" in stale.content and "+05:30" in stale.content
    assert "location" not in voice_context(profiles, "bob", now=now).content


def test_weather_uses_home_then_city_without_location_prompt(project_temp_dir, monkeypatch):
    from tools.plugins.information import weather
    from tools.plugins import toolkit

    profiles = ProfileStore(project_temp_dir)
    profiles.update("alice", {"city": "Delhi"})
    profiles.set_place("alice", "home", 28.61, 77.21, "Delhi")
    calls = []

    async def forecast(lat, lon, label, when):
        calls.append((lat, lon, when))
        return "Tomorrow: sunny."

    async def find_place(name, **kwargs):
        assert name == "Delhi"
        return {"latitude": 28.61, "longitude": 77.21, "label": "Delhi"}

    monkeypatch.setattr(weather, "forecast", forecast)
    monkeypatch.setattr(weather, "find_place", find_place)
    monkeypatch.setattr(toolkit, "_ask_for_location", lambda: (_ for _ in ()).throw(AssertionError("unnecessary prompt")))
    ctx = PluginContext("owner", None, None, "alice", profile=profiles)
    home_report = asyncio.run(_weather({"when": "tomorrow"}, ctx))
    assert "saved home" in home_report and "share your location" not in home_report
    profiles.remove_place("alice", "home")
    city_report = asyncio.run(_weather({"when": "tomorrow"}, ctx))
    assert "saved home city" in city_report and "share your location" not in city_report
    assert calls == [(28.61, 77.21, "tomorrow")] * 2


def test_bench_early_return_closes_http_stream():
    import httpx
    from tools.voice_bench import _sentences

    class Body(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self):
            yield b'data: {"choices":[{"delta":{"content":"Tomorrow will be sunny. "}}]}\n\n'
            raise AssertionError("bench should stop before consuming the rest")

        async def aclose(self):
            self.closed = True

    async def run():
        body = Body()
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, stream=body)
        )) as client:
            provider = OpenAICompatibleProvider(name="test", model="test", base_url="https://test.invalid", client=client)
            result = await _sentences(Brain(provider), None, "weather tomorrow")
            assert result[0][0] == "Tomorrow will be sunny."
            assert body.closed

    asyncio.run(run())


def test_bench_does_not_split_decimal_across_stream_chunks():
    from tools.voice_bench import _sentences

    class Provider:
        name = model = "test"

        async def stream(self, messages, tools=None):
            for chunk in ("Tomorrow, 20.", "5 to 31.", "2 degrees."):
                yield chunk

    found = asyncio.run(_sentences(Brain(Provider()), None, "weather tomorrow"))
    assert found[0][0] == "Tomorrow, 20.5 to 31.2 degrees."
