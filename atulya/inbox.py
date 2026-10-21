"""Phone alerts. A dedupe key keeps a retried routine from posting the same notice twice."""
from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from pathlib import Path


class Inbox:
    def __init__(self, data_dir: Path) -> None:
        self.path = Path(data_dir) / "inbox.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS notices (id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, "
                "title TEXT NOT NULL, body TEXT NOT NULL, kind TEXT NOT NULL, dedupe TEXT NOT NULL DEFAULT '', "
                "created INTEGER NOT NULL, delivered INTEGER NOT NULL DEFAULT 0)")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS inbox_dedupe ON notices(user_id, dedupe) WHERE dedupe != ''")

    def add(self, user_id: str, title: str, body: str, kind: str = "notice", dedupe: str = "") -> int:
        title, body, kind = title.strip()[:120], body.strip()[:2000], kind.strip()[:40] or "notice"
        dedupe = dedupe.strip()[:160]
        now = int(time.time())
        with closing(sqlite3.connect(self.path)) as db, db:
            if dedupe:
                row = db.execute("SELECT id FROM notices WHERE user_id=? AND dedupe=?", (user_id, dedupe)).fetchone()
                if row:
                    return int(row[0])
            cursor = db.execute(
                "INSERT INTO notices(user_id,title,body,kind,dedupe,created,delivered) VALUES(?,?,?,?,?,?,0)",
                (user_id, title, body, kind, dedupe, now))
            return int(cursor.lastrowid)

    def pull(self, user_id: str, limit: int = 5) -> list[dict]:
        """Unread phone alerts. Marking them delivered means the next poll does not repeat them."""
        with closing(sqlite3.connect(self.path)) as db, db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT id,title,body,kind,created FROM notices WHERE user_id=? AND delivered=0 "
                "ORDER BY id LIMIT ?", (user_id, max(1, min(limit, 10)))).fetchall()
            if rows:
                db.execute(
                    f"UPDATE notices SET delivered=1 WHERE id IN ({','.join('?' * len(rows))})",
                    [row["id"] for row in rows])
        return [dict(row) for row in rows]

    def recent(self, user_id: str, limit: int = 20) -> list[dict]:
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT id,title,body,kind,created,delivered FROM notices WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, max(1, min(limit, 50)))).fetchall()
        return [dict(row) for row in rows]
