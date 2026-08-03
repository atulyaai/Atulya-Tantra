"""SQLite persistence with a deliberately small, auditable schema."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


class AtulyaStore:
    def __init__(self, database_path: Path):
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(database_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def _migrate(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                    content TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    expires_at REAL,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id, id);
                CREATE TABLE IF NOT EXISTS actions (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                """
            )

    def add_message(self, *, session_id: str, user_id: str, role: str, content: str, trace_id: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO messages(session_id, user_id, role, content, trace_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, user_id, role, content, trace_id, time.time()),
            )

    def recent_messages(self, session_id: str, limit: int = 8) -> list[dict[str, str]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?", (session_id, limit)
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def add_memory(self, *, user_id: str, kind: str, content: str, source: str, confidence: float, expires_at: float | None = None) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "INSERT INTO memories(user_id, kind, content, source, confidence, expires_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, kind, content, source, confidence, expires_at, time.time()),
            )
            return int(cursor.lastrowid)

    def list_memories(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, kind, content, source, confidence, expires_at, created_at FROM memories "
                "WHERE user_id = ? AND (expires_at IS NULL OR expires_at > ?) ORDER BY id DESC LIMIT ?",
                (user_id, time.time(), limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_action(self, *, action_id: str, session_id: str, user_id: str, trace_id: str, action_type: str, payload: dict[str, Any], status: str) -> None:
        now = time.time()
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO actions VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)",
                (action_id, session_id, user_id, trace_id, action_type, json.dumps(payload), status, now, now),
            )

    def get_action(self, action_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
        if row is None:
            return None
        action = dict(row)
        action["payload"] = json.loads(action.pop("payload_json"))
        action["result"] = json.loads(action["result_json"]) if action["result_json"] else None
        action.pop("result_json")
        return action

    def update_action(self, action_id: str, *, status: str, result: dict[str, Any] | None = None) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE actions SET status = ?, result_json = ?, updated_at = ? WHERE id = ?",
                (status, json.dumps(result) if result is not None else None, time.time(), action_id),
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()
