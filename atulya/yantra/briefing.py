"""The morning briefing: time, weather, calendar, reminders and what you're tracking."""
from __future__ import annotations

from atulya.yantra import tools as _t
from atulya.yantra.tools import tool


@tool("morning_briefing", "Give a spoken briefing: time, weather, calendar, reminders and tracked items", {
    "location": {"type": "string", "description": "City for the weather (optional)", "default": ""},
})
async def morning_briefing(location: str = "") -> str:
    from atulya.yantra import tracking

    parts = [await _t.current_time()]
    if location.strip():
        parts.append(await _t.get_weather(location))
    parts.append("Calendar: " + await _t.calendar_list(1))
    parts.append("Reminders: " + await _t.list_reminders(24))
    tracked = await tracking.track_check() if tracking._load() else ""
    if tracked:
        parts.append("Tracking:\n" + tracked)
    return "\n".join(p for p in parts if p)


@tool("what_can_you_do", "Tell the user, briefly, what Atulya can do", {})
async def what_can_you_do() -> str:
    from atulya.yantra.pc_control import enabled as pc_enabled

    pc = "I can open apps and type for you when PC control is switched on." if pc_enabled() else \
        "PC control is off, but you can switch it on."
    return (
        "I can tell you the time and weather, set reminders, and manage your calendar and email. "
        "I can play music, pause, skip and change the volume, and track prices for you. "
        "Ask for your morning briefing any time. I can control smart home devices, see through a camera, "
        "and remember what you tell me. " + pc + " I always ask before doing anything risky."
    )
