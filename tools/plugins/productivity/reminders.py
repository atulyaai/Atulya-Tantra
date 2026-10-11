"""Private, persistent reminders shared by the local UI and Telegram channel."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path


class ReminderStore:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "reminders.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    message TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    delivered_at TEXT,
                    claimed_until TEXT,
                    next_attempt_at TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    failed_at TEXT
                )"""
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(reminders)")}
            for name, declaration in (
                ("claimed_until", "TEXT"),
                ("next_attempt_at", "TEXT"),
                ("retry_count", "INTEGER NOT NULL DEFAULT 0"),
                ("failed_at", "TEXT"),
            ):
                if name not in columns:
                    connection.execute(f"ALTER TABLE reminders ADD COLUMN {name} {declaration}")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS reminders_due ON reminders(delivered_at,failed_at,due_at)"
            )
            connection.commit()

    def add(self, user_id: str, chat_id: str, message: str, due_at: datetime) -> int:
        clean = message.strip()
        if not user_id.isdigit() or not chat_id.lstrip("-").isdigit():
            raise ValueError("Reminder owner is invalid")
        if not clean or len(clean) > 1000:
            raise ValueError("Reminder text must contain 1 to 1000 characters")
        if due_at.tzinfo is None:
            raise ValueError("Reminder time must include a timezone")
        timestamp = due_at.astimezone(timezone.utc).isoformat(timespec="seconds")
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            cursor = connection.execute(
                "INSERT INTO reminders(user_id,chat_id,message,due_at) VALUES(?,?,?,?)",
                (user_id, chat_id, clean, timestamp),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def list_for_user(self, user_id: str, limit: int = 10) -> list[dict[str, str | int]]:
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT id,message,due_at FROM reminders WHERE user_id=? AND delivered_at IS NULL AND failed_at IS NULL "
                "ORDER BY due_at LIMIT ?", (user_id, max(1, min(limit, 50))),
            ).fetchall()
        return [dict(row) for row in rows]

    def next_due(self) -> dict[str, str | int] | None:
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT id,message,due_at FROM reminders "
                "WHERE delivered_at IS NULL AND failed_at IS NULL ORDER BY due_at LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def claim_due(self, now: datetime | None = None) -> list[dict[str, str | int]]:
        moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        current = moment.isoformat(timespec="seconds")
        lease_until = (moment + timedelta(minutes=2)).isoformat(timespec="seconds")
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT id,user_id,chat_id,message,due_at,retry_count FROM reminders "
                "WHERE delivered_at IS NULL AND failed_at IS NULL AND due_at<=? "
                "AND (claimed_until IS NULL OR claimed_until<=?) "
                "AND (next_attempt_at IS NULL OR next_attempt_at<=?) "
                "AND retry_count<5 ORDER BY due_at LIMIT 100", (current, current, current),
            ).fetchall()
            if rows:
                connection.executemany(
                    "UPDATE reminders SET claimed_until=?,retry_count=retry_count+1 WHERE id=?",
                    ((lease_until, int(row["id"])) for row in rows),
                )
            connection.commit()
        return [dict(row) for row in rows]

    def mark_delivered(self, reminder_id: int, delivered_at: datetime | None = None) -> None:
        timestamp = (delivered_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="seconds")
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            connection.execute(
                "UPDATE reminders SET delivered_at=?,claimed_until=NULL,next_attempt_at=NULL "
                "WHERE id=? AND delivered_at IS NULL",
                (timestamp, reminder_id),
            )
            connection.commit()

    def retry_failed(self, reminder_id: int, now: datetime | None = None) -> None:
        """Release a failed delivery with backoff, and stop after five attempts."""
        moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        current = moment.isoformat(timespec="seconds")
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT retry_count FROM reminders WHERE id=?", (reminder_id,)).fetchone()
            if row is None:
                return
            attempts = int(row["retry_count"])
            failed_at = current if attempts >= 5 else None
            next_attempt = None if failed_at else (moment + timedelta(minutes=min(2 ** (attempts - 1), 60))).isoformat(timespec="seconds")
            connection.execute(
                "UPDATE reminders SET claimed_until=NULL,next_attempt_at=?,failed_at=? "
                "WHERE id=? AND delivered_at IS NULL",
                (next_attempt, failed_at, reminder_id),
            )
            connection.commit()

    def mark_failed(self, reminder_id: int, failed_at: datetime | None = None) -> None:
        timestamp = (failed_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="seconds")
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            connection.execute(
                "UPDATE reminders SET failed_at=?,claimed_until=NULL,next_attempt_at=NULL "
                "WHERE id=? AND delivered_at IS NULL",
                (timestamp, reminder_id),
            )
            connection.commit()
