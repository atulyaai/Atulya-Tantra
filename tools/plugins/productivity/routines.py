"""Persistent time-of-day routines. Survives process restarts.

A routine fires once per local day, only inside a 20-minute window after its
clock time, so a restart does not replay the whole morning and does not fire
early.
"""
from __future__ import annotations

import json
from functools import wraps
import re
import secrets
import threading
from datetime import datetime
from pathlib import Path

_WHEN = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
DAYS = {"all", "weekdays", "weekends"}
ACTIONS = {"message", "briefing", "weather", "rain", "calendar"}
WINDOW_MINUTES = 20
_LOCK = threading.RLock()


def _locked(method):
    @wraps(method)
    def call(*args, **kwargs):
        with _LOCK:
            return method(*args, **kwargs)
    return call


class RoutineStore:
    def __init__(self, data_dir: Path) -> None:
        self._path = Path(data_dir) / "routines.json"

    def _load(self) -> list[dict]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict) and item.get("id")]

    def _save(self, items: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps({"items": items}, indent=2), encoding="utf-8")
        temporary.replace(self._path)

    def list_items(self) -> list[dict]:
        return self._load()

    @_locked
    def add(self, name: str, when: str, days: str = "all", action: str = "message", message: str = "") -> dict:
        match = _WHEN.fullmatch(when.strip())
        if not match:
            raise ValueError("Time must be HH:MM, for example 08:00.")
        days_key = (days or "all").strip().lower()
        action_key = (action or "message").strip().lower()
        if days_key not in DAYS:
            raise ValueError("Days must be all, weekdays, or weekends.")
        if action_key not in ACTIONS:
            raise ValueError("Action must be message, briefing, weather, rain, or calendar.")
        body = message.strip()[:500]
        if action_key == "message" and not body:
            raise ValueError("A message routine needs the text to send.")
        label = name.strip()[:80]
        if not label:
            raise ValueError("Name is required.")
        item = {
            "id": secrets.token_urlsafe(6),
            "name": label,
            "when": f"{int(match.group(1)):02d}:{match.group(2)}",
            "days": days_key,
            "action": action_key,
            "message": body,
            "enabled": True,
            "last_fired": "",
        }
        items = self._load()
        items.append(item)
        self._save(items)
        return item

    @_locked
    def remove(self, query: str) -> int:
        needle = query.strip()
        lowered = needle.lower()
        items = self._load()
        kept = [
            item for item in items
            if item.get("id") != needle and str(item.get("name", "")).lower() != lowered
        ]
        removed = len(items) - len(kept)
        if removed == 0:
            raise ValueError("No routine with that name or id.")
        self._save(kept)
        return removed

    def due(self, now: datetime | None = None) -> list[dict]:
        """Routines whose clock time is 0–20 minutes ago and not yet fired today."""
        now = now or datetime.now().astimezone()
        today = now.date().isoformat()
        weekday = now.weekday() < 5
        now_mins = now.hour * 60 + now.minute
        ready: list[dict] = []
        for item in self._load():
            if not item.get("enabled") or item.get("last_fired") == today:
                continue
            when = str(item.get("when") or "")
            if not _WHEN.fullmatch(when):
                continue
            hour, minute = (int(part) for part in when.split(":"))
            delta = now_mins - (hour * 60 + minute)
            if not 0 <= delta <= WINDOW_MINUTES:
                continue
            days = item.get("days") or "all"
            if days == "weekdays" and not weekday:
                continue
            if days == "weekends" and weekday:
                continue
            ready.append(dict(item))
        return ready

    @_locked
    def mark_fired(self, routine_id: str, day: str | None = None) -> None:
        day = day or datetime.now().astimezone().date().isoformat()
        items = self._load()
        for item in items:
            if item.get("id") == routine_id:
                item["last_fired"] = day
        self._save(items)

    @staticmethod
    def format_list(items: list[dict]) -> str:
        if not items:
            return "No routines yet. Ask me to add one, for example weekday 8:00 briefing."
        lines = ["Routines:"]
        for item in items:
            lines.append(
                f"• {item.get('name')} ({item.get('id')}) — {item.get('days')} at {item.get('when')}, "
                f"{item.get('action')}"
                + (f": {item.get('message')}" if item.get("action") == "message" and item.get("message") else "")
                + ("" if item.get("enabled", True) else " [off]")
            )
        return "\n".join(lines)


    def set_enabled(self, routine_id: str, enabled: bool) -> bool:
        with _LOCK:
            items = self._load()
            for item in items:
                if item["id"] == routine_id:
                    item["enabled"] = enabled
                    self._save(items)
                    return True
            return False

    def still_enabled(self, routine_id: str) -> bool:
        return any(item["id"] == routine_id and item.get("enabled") for item in self._load())

    @_locked
    def ensure_defaults(self) -> None:
        """Initialize an empty store; never subscribe the owner without a request."""
        if not self._path.exists():
            self._save([])
