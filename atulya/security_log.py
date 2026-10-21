"""Security audit log (PLAN M13-5, PLT-07): sign-ins, approvals, device jobs and admin changes.

Append-only SQLite. Each row stores the SHA-256 of the previous row's hash plus its own fields, so an
edited or deleted row breaks `verify()`. Rows never contain message text, passwords, tokens or file
contents: only who, what, which target and the outcome.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path

KINDS = ("auth", "admin", "approval", "device", "account")
_DEFAULT: "SecurityLog | None" = None
_LOCKS: dict[str, threading.Lock] = {}


class SecurityLog:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "security_log.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # One lock per file: every instance on the same log must append in order or the chain forks.
        self._lock = _LOCKS.setdefault(str(self.path.resolve()), threading.Lock())
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, at INTEGER, "
                       "kind TEXT, actor TEXT, action TEXT, target TEXT, outcome TEXT, ip TEXT, prev TEXT, hash TEXT)")

    @staticmethod
    def _digest(prev: str, fields: tuple) -> str:
        return hashlib.sha256((prev + json.dumps(fields, ensure_ascii=False)).encode("utf-8")).hexdigest()

    def record(self, kind: str, actor: str, action: str, *, target: str = "", outcome: str = "", ip: str = "") -> None:
        if kind not in KINDS:
            raise ValueError(f"unknown security event kind {kind}")
        fields = (int(time.time()), kind, str(actor)[:80], str(action)[:120], str(target)[:200],
                  str(outcome)[:60], str(ip)[:60])
        with self._lock, closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")  # other processes (CLI pairing) append to the same chain
            row = db.execute("SELECT hash FROM events ORDER BY id DESC LIMIT 1").fetchone()
            prev = row[0] if row else ""
            db.execute("INSERT INTO events(at,kind,actor,action,target,outcome,ip,prev,hash) VALUES(?,?,?,?,?,?,?,?,?)",
                       (*fields, prev, self._digest(prev, fields)))

    def recent(self, limit: int = 100, kind: str | None = None) -> list[dict]:
        query = "SELECT id,at,kind,actor,action,target,outcome,ip FROM events"
        params: tuple = ()
        if kind:
            query += " WHERE kind=?"
            params = (kind,)
        query += " ORDER BY id DESC LIMIT ?"
        with closing(sqlite3.connect(self.path)) as db:
            rows = db.execute(query, (*params, max(1, min(limit, 500)))).fetchall()
        keys = ("id", "at", "kind", "actor", "action", "target", "outcome", "ip")
        return [dict(zip(keys, row)) for row in rows]

    def verify(self) -> bool:
        """True when no row was edited, removed or reordered since it was written."""
        prev = ""
        with closing(sqlite3.connect(self.path)) as db:
            for row in db.execute("SELECT at,kind,actor,action,target,outcome,ip,prev,hash FROM events ORDER BY id"):
                fields, stored_prev, stored = tuple(row[:7]), row[7], row[8]
                if stored_prev != prev or self._digest(prev, fields) != stored:
                    return False
                prev = stored
        return True


def set_default(log: SecurityLog | None) -> None:
    global _DEFAULT
    _DEFAULT = log


def record_event(kind: str, actor: str, action: str, **details) -> None:
    """For code outside the web routes (Telegram, AgentHub). A no-op until the server sets the log."""
    if _DEFAULT is not None:
        try:
            _DEFAULT.record(kind, actor, action, **details)
        except Exception:  # auditing must never break the action itself
            pass


def classify(method: str, path: str, *, admin_route: bool) -> str | None:
    """Which kind of event a mutating request is, or None when it is not audited."""
    if method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return None
    if path.startswith("/api/auth/") and not admin_route:
        return "auth"
    if admin_route:
        return "admin"
    # /api/actions/* approvals are logged by their handler, with approve/deny and the tool name.
    if path.startswith("/api/devices"):
        return "device"
    if path in {"/api/profile/birth-date", "/api/profile/adult-content"}:
        return "account"
    return None
