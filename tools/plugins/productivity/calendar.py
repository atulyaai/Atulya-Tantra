"""Small local calendar store with per-browser ownership and reminder times."""
from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from atulya.dbrepair import ensure_created_at_default


class CalendarStore:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "calendar.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, user_id TEXT NOT NULL DEFAULT 'admin', owner TEXT NOT NULL, title TEXT NOT NULL,
                starts_at TEXT NOT NULL, reminder_minutes INTEGER NOT NULL DEFAULT 15,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            )""")
            columns = {row[1] for row in db.execute("PRAGMA table_info(events)")}
            if "user_id" not in columns:
                db.execute("""CREATE TABLE events_scoped (
                    id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, owner TEXT NOT NULL, title TEXT NOT NULL,
                    starts_at TEXT NOT NULL, reminder_minutes INTEGER NOT NULL DEFAULT 15,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                )""")
                db.execute(
                    """INSERT INTO events_scoped
                       SELECT id,CASE WHEN owner GLOB 'tg[0-9]*' THEN 'tg_' || substr(owner,3) ELSE 'admin' END,
                              owner,title,starts_at,reminder_minutes,created_at FROM events"""
                )
                db.execute("DROP TABLE events")
                db.execute("ALTER TABLE events_scoped RENAME TO events")
            db.execute("CREATE INDEX IF NOT EXISTS events_owner_start ON events(user_id, owner, starts_at)")
        with closing(sqlite3.connect(self.path, isolation_level=None)) as repair:
            ensure_created_at_default(repair, "events")

    @staticmethod
    def _owner(owner: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", owner):
            raise ValueError("Calendar owner is invalid")
        return owner

    @staticmethod
    def _user_id(user_id: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", user_id):
            raise ValueError("Calendar user is invalid")
        return user_id

    def add(self, owner: str, title: str, starts_at: datetime, reminder_minutes: int = 15,
            user_id: str = "admin") -> dict:
        owner = self._owner(owner)
        user_id = self._user_id(user_id)
        title = title.strip()
        if not title or len(title) > 300:
            raise ValueError("Event title must be 1 to 300 characters")
        if starts_at.tzinfo is None:
            raise ValueError("Event time must include a timezone")
        if starts_at.astimezone(timezone.utc) <= datetime.now(timezone.utc):
            raise ValueError("Meeting time must be in the future")
        if not 0 <= reminder_minutes <= 1440:
            raise ValueError("Reminder must be between 0 and 1440 minutes")
        timestamp = starts_at.astimezone(timezone.utc).isoformat(timespec="seconds")
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            cur = db.execute(
                "INSERT INTO events(user_id,owner,title,starts_at,reminder_minutes) VALUES(?,?,?,?,?)",
                (user_id, owner, title, timestamp, reminder_minutes),
            )
            event_id = int(cur.lastrowid)
        return {"id": event_id, "title": title, "starts_at": timestamp, "reminder_minutes": reminder_minutes}

    def list(self, owner: str, limit: int = 20, user_id: str = "admin") -> list[dict]:
        owner = self._owner(owner)
        user_id = self._user_id(user_id)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT id,title,starts_at,reminder_minutes FROM events "
                "WHERE user_id=? AND owner=? AND starts_at>=? ORDER BY starts_at LIMIT ?",
                (user_id, owner, now, min(max(limit, 1), 100)),
            ).fetchall()
        return [dict(row) for row in rows]

    def remove(self, owner: str, event_id: int, user_id: str = "admin") -> bool:
        owner = self._owner(owner)
        user_id = self._user_id(user_id)
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            cur = db.execute("DELETE FROM events WHERE user_id=? AND owner=? AND id=?", (user_id, owner, event_id))
            return cur.rowcount > 0

    def edit(self, owner: str, event_id: int, *, user_id: str = "admin", title: str | None = None,
             starts_at: datetime | None = None) -> bool:
        owner, user_id = self._owner(owner), self._user_id(user_id)
        if title is not None and (not title.strip() or len(title) > 300):
            raise ValueError("Event title must be 1 to 300 characters")
        if starts_at is not None and (starts_at.tzinfo is None or starts_at <= datetime.now(timezone.utc)):
            raise ValueError("Meeting time must be in the future and include a timezone")
        if title is None and starts_at is None:
            raise ValueError("Specify a new title or time")
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            cur = db.execute("UPDATE events SET title=COALESCE(?,title),starts_at=COALESCE(?,starts_at) "
                             "WHERE owner=? AND user_id=? AND id=?",
                             (title.strip() if title is not None else None,
                              starts_at.astimezone(timezone.utc).isoformat(timespec="seconds") if starts_at else None,
                              owner, user_id, event_id))
            return cur.rowcount > 0

    def due_reminder(self, owner: str, now: datetime | None = None, user_id: str = "admin") -> dict | None:
        owner = self._owner(owner)
        user_id = self._user_id(user_id)
        current = now or datetime.now(timezone.utc)
        horizon = current + timedelta(days=1)
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT id,title,starts_at,reminder_minutes FROM events "
                "WHERE user_id=? AND owner=? AND starts_at>=? AND starts_at<=? ORDER BY starts_at LIMIT 100",
                (user_id, owner, current.isoformat(timespec="seconds"), horizon.isoformat(timespec="seconds")),
            ).fetchall()
        for row in rows:
            event = dict(row)
            starts = datetime.fromisoformat(event["starts_at"])
            reminder_at = starts - timedelta(minutes=int(event["reminder_minutes"]))
            if reminder_at <= current < starts:
                return event
        return None
