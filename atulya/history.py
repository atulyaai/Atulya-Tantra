"""Local, append-only transcript storage for WebUI conversations.

This is an interaction archive, not assistant memory: entries are never used to
personalize prompts or recalled by the reasoning layer.
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from collections.abc import Iterator


_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_ROLES = {"user", "assistant", "notice"}
from atulya.dbrepair import ensure_created_at_default


class ConversationHistory:
    """Persist chat messages in a project-local SQLite database."""

    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "conversations.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._session() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS messages (
                    user_id TEXT NOT NULL DEFAULT 'admin',
                    conversation_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user','assistant','notice')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    PRIMARY KEY(user_id, conversation_id, message_id)
                )"""
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(messages)")}
            primary_key = [row[1] for row in sorted(
                (row for row in connection.execute("PRAGMA table_info(messages)") if row[5]),
                key=lambda row: row[5],
            )]
            if "user_id" not in columns or primary_key != ["user_id", "conversation_id", "message_id"]:
                connection.execute(
                    """CREATE TABLE messages_scoped (
                        user_id TEXT NOT NULL,
                        conversation_id TEXT NOT NULL,
                        message_id TEXT NOT NULL,
                        role TEXT NOT NULL CHECK(role IN ('user','assistant','notice')),
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                        PRIMARY KEY(user_id, conversation_id, message_id)
                    )"""
                )
                if "user_id" in columns:
                    connection.execute(
                        "INSERT INTO messages_scoped SELECT user_id,conversation_id,message_id,role,content,created_at FROM messages"
                    )
                else:
                    connection.execute(
                        """INSERT INTO messages_scoped
                           SELECT CASE WHEN conversation_id GLOB 'tg[0-9]*' THEN 'tg_' || substr(conversation_id,3)
                                       ELSE 'admin' END,
                                  conversation_id,message_id,role,content,created_at FROM messages"""
                    )
                connection.execute("DROP TABLE messages")
                connection.execute("ALTER TABLE messages_scoped RENAME TO messages")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS messages_by_conversation ON messages(user_id,conversation_id,created_at)"
            )
        with closing(sqlite3.connect(self.path, isolation_level=None)) as repair:
            ensure_created_at_default(repair, "messages")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _validate_ids(conversation_id: str, message_id: str) -> None:
        if not _ID.fullmatch(conversation_id) or not _ID.fullmatch(message_id):
            raise ValueError("Conversation identifiers are invalid")

    @staticmethod
    def _validate_user_id(user_id: str) -> None:
        if not _ID.fullmatch(user_id):
            raise ValueError("Conversation owner is invalid")

    def append(self, conversation_id: str, message_id: str, role: str, content: str, user_id: str = "admin") -> None:
        self._validate_ids(conversation_id, message_id)
        self._validate_user_id(user_id)
        if role not in _ROLES:
            raise ValueError("Message role is invalid")
        clean = content.strip()
        if not clean or len(clean) > 20_000:
            raise ValueError("Message content must contain 1 to 20000 characters")
        with self._session() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO messages(user_id,conversation_id,message_id,role,content) VALUES(?,?,?,?,?)",
                (user_id, conversation_id, message_id, role, clean),
            )

    def read(self, conversation_id: str, limit: int = 200, user_id: str = "admin") -> list[dict[str, str]]:
        self._validate_ids(conversation_id, "read")
        self._validate_user_id(user_id)
        with self._session() as connection:
            rows = connection.execute(
                "SELECT message_id,role,content,created_at FROM messages "
                "WHERE user_id=? AND conversation_id=? ORDER BY rowid DESC LIMIT ?",
                (user_id, conversation_id, min(max(limit, 1), 500)),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def search(self, query: str, limit: int = 8, user_id: str = "admin") -> list[dict[str, str]]:
        """Find this user's past messages containing every query word, newest first."""
        self._validate_user_id(user_id)
        terms = [term for term in query.lower().split() if len(term) > 2][:6]
        if not terms:
            return []
        escaped = [term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") for term in terms]
        clause = " AND ".join("lower(content) LIKE ? ESCAPE '\\'" for _ in escaped)
        with self._session() as connection:
            rows = connection.execute(
                f"SELECT conversation_id,role,content,created_at FROM messages WHERE user_id=? AND {clause} "
                "ORDER BY rowid DESC LIMIT ?",
                (user_id, *(f"%{term}%" for term in escaped), min(max(limit, 1), 20)),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete(self, conversation_id: str, user_id: str = "admin") -> int:
        """Delete one browser conversation archive and return its message count."""
        self._validate_ids(conversation_id, "delete")
        self._validate_user_id(user_id)
        with self._session() as connection:
            cursor = connection.execute(
                "DELETE FROM messages WHERE user_id=? AND conversation_id=?", (user_id, conversation_id)
            )
            return int(cursor.rowcount)
