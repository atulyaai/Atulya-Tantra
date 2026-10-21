"""Location-aware weather: which place is used, freshness of device locations, and the instant shortcut."""
from __future__ import annotations

import asyncio
from pathlib import Path

from atulya.profiles import ProfileStore
from tools.plugins import toolkit
from tools.plugins.registry import PluginContext


def _context(profiles: ProfileStore) -> PluginContext:
    return PluginContext("web", memory=None, calendar=None, user_id="admin", profile=profiles)


def test_device_location_is_kept_across_profile_edits_and_expires(project_temp_dir: Path) -> None:
    profiles = ProfileStore(project_temp_dir)
    profiles.set_location("admin", 28.6315, 77.2167, accuracy=35, source="browser")
    profiles.update("admin", {"preferred_name": "AJ"})  # editing preferences must not wipe the location
    found = profiles.location("admin")
    assert found and found["lat"] == 28.6315 and found["source"] == "browser"
    assert "_location" not in profiles.get("admin")  # never exposed as an editable preference
    assert profiles.location("admin", max_age=-1) is None  # stale positions are not used


def test_weather_uses_place_then_device_then_home_then_asks(project_temp_dir: Path, monkeypatch) -> None:
    from tools.plugins.information import weather

    calls: list[str] = []

    async def fake_find(name, near=None):
        return {"latitude": 1.0, "longitude": 2.0, "label": name.title()}

    async def fake_forecast(lat, lon, label, when):
        calls.append(f"{label}|{when}")
        return f"forecast for {label}"

    async def fake_address(lat, lon):
        return "Connaught Place, New Delhi"

    monkeypatch.setattr(weather, "find_place", fake_find)
    monkeypatch.setattr(weather, "forecast", fake_forecast)
    monkeypatch.setattr(weather, "address", fake_address)
    profiles = ProfileStore(project_temp_dir)
    ctx = _context(profiles)

    async def run(args):
        queued: list[str] = []
        toolkit.UI_ACTIONS.set(queued)
        return await toolkit._weather(args, ctx), queued

    reply, asked = asyncio.run(run({"when": "tomorrow"}))
    assert reply.startswith("NEEDS_LOCATION") and asked == ["share_location"]

    profiles.update("admin", {"city": "Pune"})
    reply, asked = asyncio.run(run({}))
    assert "forecast for Pune" in reply and asked == []  # saved city is sufficient for a forecast

    profiles.set_location("admin", 28.6, 77.2)
    reply, asked = asyncio.run(run({"when": "week"}))
    assert "Connaught Place" in reply and asked == []

    reply, _ = asyncio.run(run({"place": "Mumbai", "when": "today"}))
    assert reply == "forecast for Mumbai" and calls[-1] == "Mumbai|today"


def test_where_am_i_needs_a_recent_device_location(project_temp_dir: Path, monkeypatch) -> None:
    from tools.plugins.information import weather

    async def fake_address(lat, lon):
        return "Connaught Place, New Delhi"

    monkeypatch.setattr(weather, "address", fake_address)
    profiles = ProfileStore(project_temp_dir)
    ctx = _context(profiles)
    assert asyncio.run(toolkit._where_am_i({}, ctx)).startswith("NEEDS_LOCATION")
    profiles.set_location("admin", 28.6315, 77.2167, accuracy=35)
    reply = asyncio.run(toolkit._where_am_i({}, ctx))
    assert "Connaught Place" in reply and "35 m" in reply and "openstreetmap.org" in reply


def test_instant_weather_shortcut_leaves_timed_questions_to_the_model() -> None:
    from tools.plugins.information.commands import handle

    for text in ("weather in Delhi tomorrow", "weather in Mumbai this week", "weather in delhi kal"):
        assert asyncio.run(handle(text, None)) is None


def test_saved_places_home_and_office(project_temp_dir: Path, monkeypatch) -> None:
    from tools.plugins.information import weather

    looked_up: list[tuple] = []

    async def fake_find(name, near=None):
        looked_up.append((name, near))
        return {"latitude": 28.5492, "longitude": 77.2529, "label": "Nehru Place, Delhi, India"}

    async def fake_forecast(lat, lon, label, when):
        return f"forecast for {label} at {lat}"

    monkeypatch.setattr(weather, "find_place", fake_find)
    monkeypatch.setattr(weather, "forecast", fake_forecast)
    profiles = ProfileStore(project_temp_dir)
    ctx = _context(profiles)
    profiles.set_location("admin", 28.6315, 77.2167)
    assert "Saved 'office'" in asyncio.run(toolkit._save_place({"name": "my office", "place": "Nehru Place"}, ctx))
    assert looked_up[-1][1] == (28.6315, 77.2167)  # lookups prefer places near the user
    reply = asyncio.run(toolkit._weather({"place": "office", "when": "tomorrow"}, ctx))
    assert "office (Nehru Place" in reply and len(looked_up) == 1  # saved place used, no new lookup
    assert "office = Nehru Place" in profiles.get("admin")["_places_list"]
    profiles.update("admin", {"preferred_name": "AJ"})
    assert "office" in profiles.places("admin")  # preference edits keep saved places
    assert profiles.remove_place("admin", "office") and profiles.places("admin") == {}
