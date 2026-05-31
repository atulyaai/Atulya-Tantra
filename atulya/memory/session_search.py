"""Session search provider with FTS5."""
from __future__ import annotations

import asyncio
import json
import sqlite3
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

    def __del__(self):
        try:
            if self._conn:
                self._conn.close()
                self._conn = None
        except Exception:
            pass

    async def initialize(self):
        def _do():
            conn = self._get_conn()
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS sessions USING fts5(
                    id, content, metadata, tags, created_at,
                    tokenize='unicode61'
                )
            """)
            conn.commit()
        await asyncio.to_thread(_do)

    async def store(self, entry: MemoryEntry) -> str:
        def _do():
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO sessions (id, content, metadata, tags, created_at) VALUES (?, ?, ?, ?, ?)",
                (entry.id, entry.content, json.dumps(entry.metadata), json.dumps(entry.tags), entry.created_at),
            )
            conn.commit()
            return entry.id
        return await asyncio.to_thread(_do)

    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        def _do():
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT id, content, metadata, tags, created_at FROM sessions WHERE sessions MATCH ? LIMIT ?",
                (query, limit),
            ).fetchall()
            return [
                MemoryEntry(
                    id=r[0], provider="session_search", content=r[1],
                    metadata=json.loads(r[2]) if r[2] else {},
                    tags=json.loads(r[3]) if r[3] else [],
                    created_at=r[4],
                )
                for r in rows
            ]
        return await asyncio.to_thread(_do)

    async def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        def _do():
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT id, content, metadata, tags, created_at FROM sessions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [
                MemoryEntry(
                    id=r[0], provider="session_search", content=r[1],
                    metadata=json.loads(r[2]) if r[2] else {},
                    tags=json.loads(r[3]) if r[3] else [],
                    created_at=r[4],
                )
                for r in rows
            ]
        return await asyncio.to_thread(_do)

    async def compact(self):
        def _do():
            conn = self._get_conn()
            conn.execute("INSERT INTO sessions(sessions) VALUES('optimize')")
            conn.commit()
        await asyncio.to_thread(_do)

    async def stats(self) -> dict[str, Any]:
        def _do():
            conn = self._get_conn()
            count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            return {"total_sessions": count}
        return await asyncio.to_thread(_do)

    async def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
