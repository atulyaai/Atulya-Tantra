"""Explicit, local-only personal facts used to personalize chat."""
from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from pathlib import Path
from atulya.dbrepair import ensure_created_at_default


class PersonalMemory:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "personal_memory.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY, user_id TEXT NOT NULL DEFAULT 'admin', owner TEXT NOT NULL, fact TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                UNIQUE(user_id, owner, fact))""")
            columns = {row[1] for row in db.execute("PRAGMA table_info(facts)")}
            if "user_id" not in columns:
                db.execute("""CREATE TABLE facts_scoped (
                    id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, owner TEXT NOT NULL, fact TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    UNIQUE(user_id, owner, fact))""")
                db.execute(
                    """INSERT INTO facts_scoped
                       SELECT id,CASE WHEN owner GLOB 'tg[0-9]*' THEN 'tg_' || substr(owner,3) ELSE 'admin' END,
                              owner,fact,created_at FROM facts"""
                )
                db.execute("DROP TABLE facts")
                db.execute("ALTER TABLE facts_scoped RENAME TO facts")
            db.execute("CREATE INDEX IF NOT EXISTS facts_owner ON facts(user_id, owner, id DESC)")
        with closing(sqlite3.connect(self.path, isolation_level=None)) as repair:
            ensure_created_at_default(repair, "facts")

    @staticmethod
    def _owner(owner: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", owner):
            raise ValueError("Memory owner is invalid")
        return owner

    @staticmethod
    def _user_id(user_id: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", user_id):
            raise ValueError("Memory user is invalid")
        return user_id

    def remember(self, owner: str, fact: str, *, user_id: str) -> bool:
        owner = self._owner(owner)
        user_id = self._user_id(user_id)
        fact = fact.strip()
        if not fact or len(fact) > 500:
            raise ValueError("A memory must be 1 to 500 characters")
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            cur = db.execute("INSERT OR IGNORE INTO facts(user_id,owner,fact) VALUES(?,?,?)", (user_id, owner, fact))
            return cur.rowcount > 0

    def forget(self, owner: str, query: str, *, user_id: str) -> int:
        owner = self._owner(owner)
        user_id = self._user_id(user_id)
        query = query.strip()
        if not query:
            raise ValueError("Name the memory you want forgotten")
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            rows = db.execute("SELECT id,fact FROM facts WHERE user_id=? AND owner=?", (user_id, owner)).fetchall()
            ids = [int(row[0]) for row in rows if query.casefold() in str(row[1]).casefold()]
            if ids:
                db.executemany(
                    "DELETE FROM facts WHERE user_id=? AND owner=? AND id=?",
                    [(user_id, owner, item) for item in ids],
                )
            return len(ids)

    def list(self, owner: str, limit: int = 100, *, user_id: str) -> list[str]:
        owner = self._owner(owner)
        user_id = self._user_id(user_id)
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            rows = db.execute(
                "SELECT fact FROM facts WHERE user_id=? AND owner=? ORDER BY id DESC LIMIT ?",
                (user_id, owner, min(max(limit, 1), 100)),
            ).fetchall()
        return [str(row[0]) for row in rows]

    def relevant(self, owner: str, query: str, limit: int = 8, *, user_id: str) -> list[str]:
        facts = self.list(owner, user_id=user_id)
        words = {word for word in re.findall(r"[\w']+", query.lower()) if len(word) > 2}
        ranked = sorted(((sum(word in fact.lower() for word in words), i, fact) for i, fact in enumerate(facts)),
                        key=lambda item: (-item[0], item[1]))
        matches = [fact for score, _, fact in ranked if score]
        return matches[:limit]

    def update(self, owner: str, old_fact: str, new_fact: str, *, user_id: str) -> bool:
        owner = self._owner(owner)
        user_id = self._user_id(user_id)
        old_fact = old_fact.strip()
        new_fact = new_fact.strip()
        if not old_fact or not new_fact or len(new_fact) > 500:
            raise ValueError("Facts must be 1 to 500 characters")
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            rows = db.execute("SELECT id, fact FROM facts WHERE user_id=? AND owner=?", (user_id, owner)).fetchall()
            matching = [int(r[0]) for r in rows if old_fact.casefold() in str(r[1]).casefold()]
            if not matching:
                return False
            db.execute("UPDATE facts SET fact=? WHERE user_id=? AND owner=? AND id=?", (new_fact, user_id, owner, matching[0]))
            return True
