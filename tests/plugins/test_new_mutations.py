import asyncio
from pathlib import Path
import pytest

from tools.plugins.personal.memory import PersonalMemory
from tools.plugins.productivity.routines import RoutineStore
from tools.plugins.information import google_api


def test_edit_fact_persistence_and_validation(tmp_path: Path):
    mem = PersonalMemory(tmp_path)
    assert mem.remember("owner", "Favorite food is dosa", user_id="admin") is True
    # Test updating existing fact
    assert mem.update("owner", "Favorite food", "Favorite food is biryani", user_id="admin") is True
    facts = mem.list("owner", user_id="admin")
    assert "Favorite food is biryani" in facts
    assert "Favorite food is dosa" not in facts

    # Test updating non-existent fact
    assert mem.update("owner", "nonexistent fact", "something new", user_id="admin") is False

    # Test invalid length validation
    with pytest.raises(ValueError):
        mem.update("owner", "Favorite food", "a" * 501, user_id="admin")


def test_edit_routine_persistence_and_validation(tmp_path: Path):
    store = RoutineStore(tmp_path)
    routine = store.add("morning_news", "08:00", days="weekdays", action="briefing")
    assert routine["when"] == "08:00"

    # Test edit when and action
    updated = store.edit("morning_news", when="09:30", days="all", action="weather")
    assert updated["when"] == "09:30"
    assert updated["days"] == "all"
    assert updated["action"] == "weather"

    # Verify persistence
    items = store.list_items()
    assert len(items) == 1
    assert items[0]["when"] == "09:30"

    # Test invalid time format
    with pytest.raises(ValueError, match="Time must be HH:MM"):
        store.edit("morning_news", when="25:99")

    # Test invalid days
    with pytest.raises(ValueError, match="Days must be"):
        store.edit("morning_news", days="invalid_days")

    # Test editing non-existent routine
    with pytest.raises(ValueError, match="No routine with that name or id"):
        store.edit("nonexistent_routine", when="10:00")


def test_calendar_update_and_delete_handlers(monkeypatch):
    calls = []

    async def fake_request(user_id, method, url, **kwargs):
        calls.append((method, url, kwargs))
        if method == "GET":
            return {"id": "evt123", "summary": "Old Summary"}
        if method == "PATCH":
            return {"id": "evt123", "summary": kwargs.get("json", {}).get("summary", "New Summary")}
        if method == "DELETE":
            return {}
        return {}

    monkeypatch.setattr(google_api, "_request", fake_request)

    # Test calendar_update
    result = asyncio.run(google_api.calendar_update("admin", "evt123", summary="Team Standup"))
    assert "Updated Google Calendar event evt123" in result
    assert calls[0][0] == "GET"
    assert calls[1][0] == "PATCH"
    assert calls[1][2]["json"]["summary"] == "Team Standup"

    # Test calendar_delete
    delete_result = asyncio.run(google_api.calendar_delete("admin", "evt123"))
    assert "Deleted Google Calendar event evt123" in delete_result
    assert calls[2][0] == "DELETE"

    # Test empty event_id validation
    with pytest.raises(ValueError, match="Provide a valid Google Calendar event ID"):
        asyncio.run(google_api.calendar_update("admin", ""))

    with pytest.raises(ValueError, match="Provide a valid Google Calendar event ID"):
        asyncio.run(google_api.calendar_delete("admin", ""))
