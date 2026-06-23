"""Task Brain - SQLite control plane for unified task ledger."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class TaskState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(Enum):
    ACP = "acp"
    SUBAGENT = "subagent"
    CRON = "cron"
    BACKGROUND = "background"
    MANUAL = "manual"


@dataclass
class TaskLedgerEntry:
    id: str
    title: str
    task_type: TaskType
    state: TaskState = TaskState.PENDING
    payload: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    completed_at: float = 0.0
    error: str = ""
    retries: int = 0
    max_retries: int = 3


class TaskBrain:
    def __init__(self, data_dir: str | Path = "assets"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "task_brain.db"
        self._lock = threading.RLock()
        temp_root = Path(tempfile.gettempdir()).resolve()
        try:
            self._persistent = not self.data_dir.resolve().is_relative_to(temp_root)
        except AttributeError:
            self._persistent = not str(self.data_dir.resolve()).startswith(str(temp_root))
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False) if self._persistent else None
        self._init_db()

    def _connect(self):
        return self._conn or sqlite3.connect(str(self.db_path), check_same_thread=False)

    def _finish(self, conn):
        if conn is not self._conn:
            conn.close()

    def _init_db(self):
        with self._lock:
            conn = self._connect()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, title TEXT, task_type TEXT, state TEXT,
                    payload TEXT, result TEXT, created_at REAL, started_at REAL,
                    completed_at REAL, error TEXT, retries INTEGER, max_retries INTEGER
                )
            """)
            conn.commit()
            self._finish(conn)

    def create_task(self, title: str, task_type: TaskType, payload: dict[str, Any] | None = None) -> str:
        task_id = str(uuid.uuid4())[:8]
        entry = TaskLedgerEntry(id=task_id, title=title, task_type=task_type, payload=payload or {})
        with self._lock:
            conn = self._connect()
            conn.execute(
                "INSERT INTO tasks (id, title, task_type, state, payload, result, created_at, started_at, completed_at, error, retries, max_retries) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (entry.id, entry.title, entry.task_type.value, entry.state.value,
                 json.dumps(entry.payload), json.dumps(entry.result), entry.created_at,
                 entry.started_at, entry.completed_at, entry.error, entry.retries, entry.max_retries),
            )
            conn.commit()
            self._finish(conn)
        return task_id

    def update_state(self, task_id: str, state: TaskState, result: dict[str, Any] | None = None, error: str = ""):
        now = time.time()
        with self._lock:
            conn = self._connect()
            if state == TaskState.RUNNING:
                conn.execute("UPDATE tasks SET state = ?, started_at = ? WHERE id = ?", (state.value, now, task_id))
            elif state in (TaskState.COMPLETED, TaskState.FAILED):
                conn.execute("UPDATE tasks SET state = ?, completed_at = ?, result = ?, error = ? WHERE id = ?",
                            (state.value, now, json.dumps(result or {}), error, task_id))
            else:
                conn.execute("UPDATE tasks SET state = ? WHERE id = ?", (state.value, task_id))
            conn.commit()
            self._finish(conn)

    def get_task(self, task_id: str) -> TaskLedgerEntry | None:
        with self._lock:
            conn = self._connect()
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            self._finish(conn)
        if row:
            return TaskLedgerEntry(
                id=row[0], title=row[1], task_type=TaskType(row[2]), state=TaskState(row[3]),
                payload=json.loads(row[4]), result=json.loads(row[5]), created_at=row[6],
                started_at=row[7], completed_at=row[8], error=row[9], retries=row[10], max_retries=row[11],
            )
        return None

    def get_pending_tasks(self) -> list[TaskLedgerEntry]:
        with self._lock:
            conn = self._connect()
            rows = conn.execute("SELECT * FROM tasks WHERE state = 'pending' ORDER BY created_at").fetchall()
            self._finish(conn)
        return [
            TaskLedgerEntry(id=r[0], title=r[1], task_type=TaskType(r[2]), state=TaskState(r[3]),
                           payload=json.loads(r[4]), result=json.loads(r[5]), created_at=r[6],
                           started_at=r[7], completed_at=r[8], error=r[9], retries=r[10], max_retries=r[11])
            for r in rows
        ]

    def get_stats(self) -> dict[str, Any]:
        stats = {}
        with self._lock:
            conn = self._connect()
            for state in TaskState:
                count = conn.execute("SELECT COUNT(*) FROM tasks WHERE state = ?", (state.value,)).fetchone()[0]
                stats[state.value] = count
            total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            self._finish(conn)
        return {"total": total, **stats}

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

