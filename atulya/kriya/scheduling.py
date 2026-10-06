"""Reminders and alarms: parsing when, the scheduler and cancellation."""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any, Callable



from atulya import kriya as _d

# ── Tool: Reminder / Scheduling Skills ────────────────────────────────────

_reminders: dict[str, dict[str, Any]] = {}
_scheduler_tasks: dict[str, asyncio.Task] = {}
_reminder_callbacks: list[Callable] = []


def register_reminder_callback(cb: Callable):
    _reminder_callbacks.append(cb)


def _parse_time(text: str) -> float | None:
    """Parse natural language time expressions."""
    text = text.lower().strip()
    # "at 5pm", "today at 6pm", "tonight at 9", "on monday at 10am" -> the time itself
    text = re.sub(r"^(?:(?:today|tonight|this evening)\s+)?(?:at|on|by)\s+", "", text)
    text = re.sub(r"^(?:today|tonight)\s+", "", text)
    now = time.time()
    t = time.localtime(now)

    m = re.match(r"in\s+(\d+)\s*(second|seconds|sec|secs|minute|minutes|min|mins|hour|hours|hr|hrs|day|days)", text)
    if m:
        amount, unit = int(m.group(1)), m.group(2)
        if unit.startswith("s"):
            return now + amount
        elif unit.startswith("mi"):
            return now + amount * 60
        elif unit.startswith("h"):
            return now + amount * 3600
        else:
            return now + amount * 86400

    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
    if m:
        hour, minute_str, ampm = int(m.group(1)), m.group(2), m.group(3)
        minute = int(minute_str) if minute_str else 0
        if ampm:
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
        target = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, hour, minute, 0, t.tm_wday, t.tm_yday, t.tm_isdst))
        if target < now:
            target += 86400
        return target

    # Handle "tomorrow at HH:MM" or "tomorrow at HHam/pm"
    m = re.match(r"tomorrow\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
    if m:
        hour, minute_str, ampm = int(m.group(1)), m.group(2), m.group(3)
        minute = int(minute_str) if minute_str else 0
        if ampm:
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
        target = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, hour, minute, 0, t.tm_wday, t.tm_yday, t.tm_isdst))
        return target + 86400

    # Handle "next monday" / "next tuesday" etc
    days = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
    m = re.match(r"(?:next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", text)
    if m:
        target_day = days[m.group(1)]
        days_ahead = target_day - t.tm_wday
        if days_ahead <= 0:
            days_ahead += 7
        target = now + days_ahead * 86400
        # Check for time after the weekday
        m2 = re.search(r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
        if m2:
            hour, minute_str, ampm = int(m2.group(1)), m2.group(2), m2.group(3)
            minute = int(minute_str) if minute_str else 0
            if ampm:
                if ampm == "pm" and hour < 12:
                    hour += 12
                elif ampm == "am" and hour == 12:
                    hour = 0
            target = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, hour, minute, 0, t.tm_wday, t.tm_yday, t.tm_isdst)) + days_ahead * 86400
        return target


@_d.tool("set_reminder", "Set a reminder or alarm", {
    "message": {"type": "string", "description": "What to remind about"},
    "time_str": {"type": "string", "description": "When: 'in 5 minutes', 'tomorrow at 9am', '30 min', '2:30pm'"},
})
async def set_reminder(message: str, time_str: str = "in 5 minutes") -> str:
    parsed = _parse_time(time_str)
    if not parsed:
        return f"Could not understand time: '{time_str}'. Try 'in 5 minutes', 'tomorrow at 9am', or '2:30pm'."
    rid = f"rem_{int(time.time() * 1000)}"
    entry = {"id": rid, "message": message, "scheduled_time": parsed, "created_at": time.time(), "status": "pending"}
    _reminders[rid] = entry
    _d._save_json("reminders.json", list(_reminders.values()))

    delay = parsed - time.time()
    if delay > 0:

        async def _fire():
            await asyncio.sleep(delay)
            entry["status"] = "done"
            _d._save_json("reminders.json", list(_reminders.values()))
            for cb in _reminder_callbacks:
                try:
                    await cb("reminder", entry)
                except Exception:
                    pass

        _scheduler_tasks[rid] = asyncio.create_task(_fire())
    else:
        entry["status"] = "done"
        _d._save_json("reminders.json", list(_reminders.values()))

    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(parsed))
    return f"Reminder set: '{message}' at {when} (id: {rid})"


@_d.tool("list_reminders", "List upcoming reminders", {
    "hours": {"type": "integer", "description": "How many hours ahead to look (default 24)", "default": 24},
})
async def list_reminders(hours: int = 24) -> str:
    now = time.time()
    cutoff = now + hours * 3600
    upcoming = [r for r in _reminders.values() if r["status"] == "pending" and now <= r["scheduled_time"] <= cutoff]
    if not upcoming:
        return "No upcoming reminders."
    lines = [f"{i+1}. {r['message']} (at {time.ctime(r['scheduled_time'])})" for i, r in enumerate(sorted(upcoming, key=lambda x: x["scheduled_time"]))]
    return "\n".join(lines)


@_d.tool("cancel_reminder", "Cancel a reminder by ID", {
    "reminder_id": {"type": "string", "description": "The reminder ID from set_reminder or list_reminders"},
})
async def cancel_reminder(reminder_id: str) -> str:
    if reminder_id in _reminders:
        _reminders[reminder_id]["status"] = "cancelled"
        _d._save_json("reminders.json", list(_reminders.values()))
        if reminder_id in _scheduler_tasks:
            _scheduler_tasks[reminder_id].cancel()
        return f"Reminder {reminder_id} cancelled."
    return f"Reminder {reminder_id} not found."


