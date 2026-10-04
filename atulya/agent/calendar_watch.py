"""Proactive calendar heads-up: publishes ``calendar.soon`` shortly before an event."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

LEAD_MINUTES = int(os.environ.get("ATULYA_CALENDAR_LEAD_MIN", "10"))


def _to_ts(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        text = str(value)
        if "T" not in text:
            return None  # all-day events don't get a countdown
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


async def upcoming_events(window_minutes: int) -> list[dict[str, Any]]:
    """Events (local calendar plus Google, when connected) starting within the window."""
    from atulya.agent import tools

    now = time.time()
    end = now + window_minutes * 60
    found = [{"id": e["id"], "title": e["title"], "ts": float(e["time"])}
             for e in tools._CALENDAR.values() if now < float(e["time"]) <= end]
    google = tools._google()
    if google is not None:
        try:
            for e in await google.list_events(1):
                ts = _to_ts(e.get("start"))
                if ts and now < ts <= end:
                    found.append({"id": e["id"], "title": e["title"], "ts": ts})
        except Exception as exc:  # noqa: BLE001 - the watcher must never die
            logger.debug("calendar watch (google) failed: %s", exc)
    return found


async def watch_calendar(events: Any, interval: float = 60.0, lead_minutes: int = LEAD_MINUTES) -> None:
    """Emit ``calendar.soon`` once per event when it is ``lead_minutes`` away or less."""
    announced: set[str] = set()
    while True:
        try:
            for e in await upcoming_events(lead_minutes):
                key = f"{e['id']}@{int(e['ts'])}"
                if key in announced:
                    continue
                announced.add(key)
                minutes = max(1, round((e["ts"] - time.time()) / 60))
                await events.emit("calendar.soon", {"id": e["id"], "title": e["title"], "minutes": minutes})
            if len(announced) > 500:
                announced.clear()
        except Exception as exc:  # noqa: BLE001
            logger.debug("calendar watch failed: %s", exc)
        await asyncio.sleep(interval)
