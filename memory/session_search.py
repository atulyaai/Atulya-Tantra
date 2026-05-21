"""Session search provider with FTS5."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .orchestrator import MemoryProvider, MemoryEntry


class SessionSearchProvider(MemoryProvider):
    def __init__(self, data_dir: str | Path):
        self.db_path = Path(data_dir) / "session_search.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _close_conn(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    async def initialize(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS sessions USING fts5(
                id, content, metadata, tags, created_at,
                tokenize='unicode61'
            )
        """)
        conn.commit()

    async def store(self, entry: MemoryEntry) -> str:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO sessions (id, content, metadata, tags, created_at) VALUES (?, ?, ?, ?, ?)",
            (entry.id, entry.content, json.dumps(entry.metadata), json.dumps(entry.tags), entry.created_at),
        )
        conn.commit()
        self._close_conn()
        return entry.id

    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, content, metadata, tags, created_at FROM sessions WHERE sessions MATCH ? LIMIT ?",
            (query, limit),
        ).fetchall()
        self._close_conn()
        return [
            MemoryEntry(
                id=r[0], provider="session_search", content=r[1],
                metadata=json.loads(r[2]) if r[2] else {},
                tags=json.loads(r[3]) if r[3] else [],
                created_at=r[4],
            )
            for r in rows
        ]

    async def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, content, metadata, tags, created_at FROM sessions ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        self._close_conn()
        return [
            MemoryEntry(
                id=r[0], provider="session_search", content=r[1],
                metadata=json.loads(r[2]) if r[2] else {},
                tags=json.loads(r[3]) if r[3] else [],
                created_at=r[4],
            )
            for r in rows
        ]

    async def compact(self):
        conn = self._get_conn()
        conn.execute("INSERT INTO sessions(sessions) VALUES('optimize')")
        conn.commit()
        self._close_conn()

    async def stats(self) -> dict[str, Any]:
        conn = self._get_conn()
        count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        self._close_conn()
        return {"total_sessions": count}
