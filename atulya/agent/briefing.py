"""The morning briefing: time, weather, calendar, reminders and what you're tracking."""
from __future__ import annotations

from atulya.agent import tools as _t
from atulya.agent.tools import tool


@tool("morning_briefing", "Give a spoken briefing: time, weather, calendar, reminders and tracked items", {
    "location": {"type": "string", "description": "City for the weather (optional)", "default": ""},
})
async def morning_briefing(location: str = "") -> str:
    from atulya.agent import tracking

    parts = [await _t.current_time()]
    if location.strip():
        parts.append(await _t.get_weather(location))
    parts.append("Calendar: " + await _t.calendar_list(1))
    parts.append("Reminders: " + await _t.list_reminders(24))
    tracked = await tracking.track_check() if tracking._load() else ""
    if tracked:
        parts.append("Tracking:\n" + tracked)
    return "\n".join(p for p in parts if p)
