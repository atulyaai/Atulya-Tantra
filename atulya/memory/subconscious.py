"""Subconscious provider for background processing."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .orchestrator import MemoryProvider, MemoryEntry


class SubconsciousProvider(MemoryProvider):
    def __init__(self, data_dir: str | Path):
        self.db_path = Path(data_dir) / "subconscious.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    async def initialize(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id TEXT PRIMARY KEY, content TEXT, metadata TEXT,
                tags TEXT, created_at REAL, outcome TEXT
            )
        """)
        conn.commit()

    async def store(self, entry: MemoryEntry) -> str:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO decisions (id, content, metadata, tags, created_at, outcome) VALUES (?, ?, ?, ?, ?, ?)",
            (entry.id, entry.content, json.dumps(entry.metadata), json.dumps(entry.tags),
             entry.created_at, entry.metadata.get("outcome", "pending")),
        )
        conn.commit()
        return entry.id

    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, content, metadata, tags, created_at FROM decisions WHERE content LIKE ? LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
        return [
            MemoryEntry(id=r[0], provider="subconscious", content=r[1],
                       metadata=json.loads(r[2]) if r[2] else {},
                       tags=json.loads(r[3]) if r[3] else [], created_at=r[4])
            for r in rows
        ]

    async def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, content, metadata, tags, created_at FROM decisions ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            MemoryEntry(id=r[0], provider="subconscious", content=r[1],
                       metadata=json.loads(r[2]) if r[2] else {},
                       tags=json.loads(r[3]) if r[3] else [], created_at=r[4])
            for r in rows
        ]

    async def log_decision(self, decision_id: str, content: str, outcome: str = "success"):
        entry = MemoryEntry(id=decision_id, provider="subconscious", content=content,
                           metadata={"outcome": outcome})
        await self.store(entry)

    async def compact(self):
        conn = self._get_conn()
        conn.execute("VACUUM")
        conn.commit()

    async def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
