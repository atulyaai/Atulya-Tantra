"""Durable, account-scoped reminders delivered to an open Atulya page.

These deliberately do not claim background, Telegram, or OS notification delivery.
A reminder is marked shown only after the page acknowledges rendering it.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path


class WebReminderStore:
    delivery = "Open, signed-in Atulya page; overdue reminders appear when you return. No background notification."
    def __init__(self, data_dir: Path):
        self.path = data_dir / "web_reminders.sqlite3"
        data_dir.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, message TEXT NOT NULL,
                due_at TEXT NOT NULL, shown_at TEXT, cancelled_at TEXT)""")
            db.execute("CREATE INDEX IF NOT EXISTS reminders_owner_due ON reminders(user_id,due_at)")

    def add(self, user_id: str, message: str, due_at: datetime) -> dict:
        message = message.strip()
        if not message or len(message) > 1000:
            raise ValueError("Reminder text must contain 1 to 1000 characters")
        if due_at.tzinfo is None:
            raise ValueError("Include a timezone in the reminder time")
        if due_at <= datetime.now(timezone.utc):
            raise ValueError("Reminder time must be in the future")
        stamp = due_at.astimezone(timezone.utc).isoformat(timespec="seconds")
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            cur = db.execute("INSERT INTO reminders(user_id,message,due_at) VALUES(?,?,?)",
                             (user_id, message, stamp))
            return {"id": cur.lastrowid, "message": message, "due_at": stamp,
                    "shown_at": None, "cancelled_at": None}

    def list(self, user_id: str, *, due_only: bool = False) -> list[dict]:
        with closing(sqlite3.connect(self.path, timeout=5)) as db:
            db.row_factory = sqlite3.Row
            if due_only:
                rows = db.execute("SELECT * FROM reminders WHERE user_id=? AND shown_at IS NULL "
                                  "AND cancelled_at IS NULL AND due_at<=? ORDER BY due_at LIMIT 50",
                                  (user_id, datetime.now(timezone.utc).isoformat(timespec="seconds"))).fetchall()
            else:
                rows = db.execute("SELECT * FROM reminders WHERE user_id=? "
                                  "ORDER BY (shown_at IS NOT NULL OR cancelled_at IS NOT NULL), "
                                  "due_at DESC LIMIT 100", (user_id,)).fetchall()
        return [{k: row[k] for k in row.keys() if k != "user_id"} for row in rows]

    def cancel_all(self, user_id: str) -> int:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            result = db.execute("UPDATE reminders SET cancelled_at=? WHERE user_id=? AND cancelled_at IS NULL AND shown_at IS NULL", (now, user_id))
            return result.rowcount

    def update(self, user_id: str, reminder_id: int, *, shown: bool = False) -> bool:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            if shown:
                cur = db.execute("UPDATE reminders SET shown_at=? WHERE id=? AND user_id=? "
                                 "AND cancelled_at IS NULL AND shown_at IS NULL AND due_at<=?",
                                 (now, reminder_id, user_id, now))
            else:
                cur = db.execute("UPDATE reminders SET cancelled_at=? WHERE id=? AND user_id=? "
                                 "AND shown_at IS NULL AND cancelled_at IS NULL", (now, reminder_id, user_id))
            return cur.rowcount > 0

    def edit(self, user_id, reminder_id, message=None, due_at=None):
        if message is not None and (not message.strip() or len(message) > 1000):
            raise ValueError("Reminder text must contain 1 to 1000 characters")
        if due_at is not None and (due_at.tzinfo is None or due_at <= datetime.now(timezone.utc)):
            raise ValueError("Reminder time must be in the future and include a timezone")
        if message is None and due_at is None:
            raise ValueError("Specify new text or a new time")
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            cur = db.execute("UPDATE reminders SET message=COALESCE(?,message),due_at=COALESCE(?,due_at) "
                             "WHERE id=? AND user_id=? AND shown_at IS NULL AND cancelled_at IS NULL",
                             (message.strip() if message is not None else None,
                              due_at.astimezone(timezone.utc).isoformat(timespec="seconds") if due_at else None,
                              reminder_id, user_id))
            return cur.rowcount > 0

    def cancel(self, user_id, reminder_id):
        return self.update(user_id, reminder_id)


class TelegramReminderAccess:
    delivery = "Telegram message in this chat. Phone sound/vibration depends on your Telegram notification settings."

    def __init__(self, store, telegram_user_id, chat_id):
        self.store, self.user_id, self.chat_id = store, telegram_user_id, chat_id

    def add(self, _user_id, message, due_at):
        reminder_id = self.store.add(self.user_id, self.chat_id, message, due_at)
        return {"id": reminder_id, "message": message, "due_at": due_at.isoformat()}

    def list(self, _user_id):
        return self.store.list_for_user(self.user_id, 50)

    def edit(self, _user_id, reminder_id, message=None, due_at=None):
        return self.store.edit(self.user_id, reminder_id, message, due_at)

    def cancel(self, _user_id, reminder_id):
        return self.store.cancel(self.user_id, reminder_id)


async def create_reminder(args, ctx):
    if ctx is None or ctx.reminders is None:
        return "Web reminders are unavailable here. On Telegram use /remind 10m your message."
    import asyncio
    if args.get("delay_minutes") is not None:
        delay = float(args["delay_minutes"])
        if not 0 < delay <= 525600:
            raise ValueError("Delay must be between 0 and 525600 minutes")
        due = datetime.now(timezone.utc) + timedelta(minutes=delay)
    else:
        due = datetime.fromisoformat(str(args.get("due_at", "")).replace("Z", "+00:00"))
    item = await asyncio.to_thread(ctx.reminders.add, ctx.user_id, str(args.get("message", "")), due)
    return (f"Saved reminder #{item['id']}: {item['message']}, due {item['due_at']}. "
            f"Delivery: {ctx.reminders.delivery}")


async def list_reminders(args, ctx):
    if ctx is None or ctx.reminders is None:
        return "Web reminders are unavailable here. On Telegram use /reminders."
    import asyncio
    import json
    return json.dumps(await asyncio.to_thread(ctx.reminders.list, ctx.user_id))


async def edit_reminder(args, ctx):
    import asyncio
    due = datetime.fromisoformat(str(args["due_at"]).replace("Z", "+00:00")) if args.get("due_at") else None
    changed = await asyncio.to_thread(ctx.reminders.edit, ctx.user_id, int(args["id"]), args.get("message"), due)
    return f"Updated reminder #{args['id']}." if changed else "Reminder not changed: unavailable, already delivered, or delivery in progress. List reminders to check its status."


async def cancel_reminder(args, ctx):
    import asyncio
    changed = await asyncio.to_thread(ctx.reminders.cancel, ctx.user_id, int(args["id"]))
    return f"Cancelled reminder #{args['id']}." if changed else "Reminder not cancelled: unavailable, already delivered, or delivery in progress."
