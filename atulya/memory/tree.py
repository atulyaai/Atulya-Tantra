"""Memory tree with hierarchical L0â†'L1â†'L2 summaries."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


class MemoryTree:
    def __init__(self, data_dir: str | Path = "assets/memory"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "memory_tree.db"
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS l0_entries (
                id TEXT PRIMARY KEY, content TEXT, metadata TEXT,
                topic TEXT, created_at REAL
            );
            CREATE TABLE IF NOT EXISTS l1_summaries (
                topic TEXT PRIMARY KEY, summary TEXT, entry_count INTEGER,
                created_at REAL, updated_at REAL
            );
            CREATE TABLE IF NOT EXISTS l2_global (
                id INTEGER PRIMARY KEY, summary TEXT, created_at REAL
            );
        """)
        conn.commit()

    def add_entry(self, content: str, topic: str = "general", metadata: dict | None = None) -> str:
        entry_id = f"l0_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO l0_entries (id, content, metadata, topic, created_at) VALUES (?, ?, ?, ?, ?)",
            (entry_id, content, json.dumps(metadata or {}), topic, time.time()),
        )
        conn.commit()
        self._update_l1(topic)
        return entry_id

    def _update_l1(self, topic: str):
        conn = self._get_conn()
        rows = conn.execute("SELECT content FROM l0_entries WHERE topic = ? ORDER BY created_at DESC LIMIT 1000", (topic,)).fetchall()
        if not rows:
            return
        combined = " ".join(r[0][:200] for r in rows)
        summary = combined[:1000] + "..." if len(combined) > 1000 else combined
        conn.execute(
            "INSERT OR REPLACE INTO l1_summaries (topic, summary, entry_count, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (topic, summary, len(rows), time.time(), time.time()),
        )
        conn.commit()
        self._update_l2()

    def _update_l2(self):
        conn = self._get_conn()
        rows = conn.execute("SELECT topic, summary FROM l1_summaries ORDER BY updated_at DESC LIMIT 500").fetchall()
        if not rows:
            return
        combined = " ".join(f"{topic}: {summary[:200]}" for topic, summary in rows)
        global_summary = combined[:2000] + "..." if len(combined) > 2000 else combined
        conn.execute("DELETE FROM l2_global")
        conn.execute(
            "INSERT OR REPLACE INTO l2_global (id, summary, created_at) VALUES (1, ?, ?)",
            (global_summary, time.time()),
        )
        conn.commit()

    def get_l0_entries(self, topic: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        conn = self._get_conn()
        if topic:
            rows = conn.execute("SELECT id, content, metadata, topic, created_at FROM l0_entries WHERE topic = ? ORDER BY created_at DESC LIMIT ?", (topic, limit)).fetchall()
        else:
            rows = conn.execute("SELECT id, content, metadata, topic, created_at FROM l0_entries ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [{"id": r[0], "content": r[1], "metadata": json.loads(r[2]), "topic": r[3], "created_at": r[4]} for r in rows]

    def get_l1_summary(self, topic: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        row = conn.execute("SELECT topic, summary, entry_count, updated_at FROM l1_summaries WHERE topic = ?", (topic,)).fetchone()
        if row:
            return {"topic": row[0], "summary": row[1], "entry_count": row[2], "updated_at": row[3]}
        return None

    def get_l2_global(self) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute("SELECT id, summary, created_at FROM l2_global ORDER BY created_at DESC LIMIT 5").fetchall()
        return [{"id": r[0], "summary": r[1], "created_at": r[2]} for r in rows]

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute("SELECT id, content, metadata, topic, created_at FROM l0_entries WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?", (f"%{query}%", limit)).fetchall()
        return [{"id": r[0], "content": r[1], "metadata": json.loads(r[2]), "topic": r[3], "created_at": r[4]} for r in rows]

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def __del__(self):
        try:
            self.close()
        except (AttributeError, TypeError):
            pass

    def stats(self) -> dict[str, Any]:
        conn = self._get_conn()
        l0_count = conn.execute("SELECT COUNT(*) FROM l0_entries").fetchone()[0]
        l1_count = conn.execute("SELECT COUNT(*) FROM l1_summaries").fetchone()[0]
        l2_count = conn.execute("SELECT COUNT(*) FROM l2_global").fetchone()[0]
        return {"l0_entries": l0_count, "l1_summaries": l1_count, "l2_global": l2_count}
