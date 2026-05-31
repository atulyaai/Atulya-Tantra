"""Reflection provider for self-improvement."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .orchestrator import MemoryProvider, MemoryEntry


class ReflectionProvider(MemoryProvider):
    def __init__(self, data_dir: str | Path):
        self.db_path = Path(data_dir) / "reflections.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self):
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
                CREATE TABLE IF NOT EXISTS reflections (
                    id TEXT PRIMARY KEY,
                    content TEXT,
                    metadata TEXT,
                    tags TEXT,
                    created_at REAL,
                    category TEXT DEFAULT 'general'
                )
            """)
            conn.commit()
        await asyncio.to_thread(_do)

    async def store(self, entry: MemoryEntry) -> str:
        def _do():
            conn = self._get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO reflections (id, content, metadata, tags, created_at, category) VALUES (?, ?, ?, ?, ?, ?)",
                (entry.id, entry.content, json.dumps(entry.metadata), json.dumps(entry.tags),
                 entry.created_at, entry.metadata.get("category", "general")),
            )
            conn.commit()
            return entry.id
        return await asyncio.to_thread(_do)

    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        def _do():
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT id, content, metadata, tags, created_at FROM reflections WHERE content LIKE ? LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
            return [
                MemoryEntry(id=r[0], provider="reflection", content=r[1],
                           metadata=json.loads(r[2]) if r[2] else {},
                           tags=json.loads(r[3]) if r[3] else [], created_at=r[4])
                for r in rows
            ]
        return await asyncio.to_thread(_do)

    async def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        def _do():
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT id, content, metadata, tags, created_at FROM reflections ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [
                MemoryEntry(id=r[0], provider="reflection", content=r[1],
                           metadata=json.loads(r[2]) if r[2] else {},
                           tags=json.loads(r[3]) if r[3] else [], created_at=r[4])
                for r in rows
            ]
        return await asyncio.to_thread(_do)

    async def add_reflection(self, content: str, category: str = "general"):
        entry = MemoryEntry(
            id=f"ref_{int(time.time())}", provider="reflection", content=content,
            metadata={"category": category},
        )
        await self.store(entry)
        return entry.id

    async def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    async def get_insights(self) -> list[dict[str, Any]]:
        def _do():
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT id, content, metadata, tags, created_at FROM reflections WHERE category = 'insight' ORDER BY created_at DESC"
            ).fetchall()
            return [
                {"id": r[0], "content": r[1], "metadata": json.loads(r[2]) if r[2] else {},
                 "tags": json.loads(r[3]) if r[3] else [], "created_at": r[4]}
                for r in rows
            ]
        return await asyncio.to_thread(_do)
