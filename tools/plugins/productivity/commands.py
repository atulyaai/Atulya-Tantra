"""Calendar command plugin shared across communication channels."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from tools.plugins.registry import PluginContext


def _parse_calendar_datetime(value: str) -> datetime:
    raw = value.strip()
    relative = re.fullmatch(r"(today|tomorrow)\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", raw, re.I)
    if relative:
        hour, minute = int(relative.group(2)), int(relative.group(3) or 0)
        suffix = (relative.group(4) or "").lower()
        if minute > 59 or hour > (12 if suffix else 23) or hour < (1 if suffix else 0):
            raise ValueError("That meeting time is invalid")
        if suffix:
            hour = hour % 12 + (12 if suffix == "pm" else 0)
        day = datetime.now().astimezone().date()
        if relative.group(1).lower() == "tomorrow":
            day += timedelta(days=1)
        return datetime(day.year, day.month, day.day, hour, minute).astimezone()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Use a date like 2026-10-20 15:00 or 'tomorrow at 3pm'.") from exc
    return parsed.astimezone() if parsed.tzinfo is None else parsed


async def handle(command: str, context: PluginContext) -> str | None:
    meeting = re.fullmatch(r"(?:add|schedule)\s+meeting\s*:\s*(.{1,300}?)\s*\|\s*(.{1,80})", command, re.I)
    if meeting:
        try:
            starts_at = _parse_calendar_datetime(meeting.group(2))
            event = context.calendar.add(context.owner_id, meeting.group(1), starts_at, 15, user_id=context.user_id)
        except ValueError as exc:
            return f"I couldn't add that meeting: {exc}"
        local_start = datetime.fromisoformat(event["starts_at"]).astimezone().strftime("%b %d at %I:%M %p %Z")
        return f"Meeting added: {event['title']} on {local_start}. I'll remind you 15 minutes before."
    if re.search(r"\b(my meetings|calendar|upcoming meetings)\b", command, re.I):
        events = context.calendar.list(context.owner_id, 10, user_id=context.user_id)
        if not events:
            return "You have no upcoming meetings saved."
        lines = [
            f"• {datetime.fromisoformat(item['starts_at']).astimezone().strftime('%b %d, %I:%M %p')} — {item['title']}"
            for item in events
        ]
        return "Your upcoming meetings:\n" + "\n".join(lines)
    return None
