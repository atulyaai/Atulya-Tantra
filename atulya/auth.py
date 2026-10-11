"""Single-device passkey account and opaque server-side session storage."""
from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator


ADMIN_ID = "admin"
SESSION_COOKIE = "atulya_session"
SESSION_MAX_AGE = 7 * 24 * 60 * 60
CHALLENGE_MAX_AGE = 5 * 60
INVITE_MAX_AGE = 24 * 60 * 60


class AuthStore:
    """Store WebAuthn public credentials and hashed session tokens in SQLite."""

    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "auth.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._session() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS credentials (
                    credential_id BLOB PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    public_key BLOB NOT NULL,
                    sign_count INTEGER NOT NULL DEFAULT 0,
                    transports TEXT NOT NULL DEFAULT '[]',
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS challenges (
                    flow_id TEXT PRIMARY KEY,
                    challenge BLOB NOT NULL,
                    ceremony TEXT NOT NULL CHECK(ceremony IN ('register','login')),
                    user_id TEXT NOT NULL DEFAULT 'admin',
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin','user')),
                    created_at INTEGER NOT NULL,
                    disabled_at INTEGER
                );
                CREATE TABLE IF NOT EXISTS invitations (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL UNIQUE,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    used_at INTEGER
                );
            """)
            challenge_columns = {row[1] for row in db.execute("PRAGMA table_info(challenges)")}
            if "user_id" not in challenge_columns:
                db.execute("ALTER TABLE challenges ADD COLUMN user_id TEXT NOT NULL DEFAULT 'admin'")
            db.execute(
                """INSERT OR IGNORE INTO users(id,display_name,role,created_at)
                   SELECT DISTINCT user_id,CASE WHEN user_id='admin' THEN 'Admin' ELSE user_id END,
                          CASE WHEN user_id='admin' THEN 'admin' ELSE 'user' END,MIN(created_at)
                   FROM credentials GROUP BY user_id"""
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        db = self._connect()
        try:
            with db:
                yield db
        finally:
            db.close()

    def credential_count(self) -> int:
        with self._session() as db:
            return int(db.execute("SELECT COUNT(*) FROM credentials").fetchone()[0])

    def credentials(self) -> list[sqlite3.Row]:
        with self._session() as db:
            return db.execute(
                "SELECT credential_id,public_key,sign_count,transports FROM credentials ORDER BY created_at"
            ).fetchall()

    def credential(self, credential_id: bytes) -> sqlite3.Row | None:
        with self._session() as db:
            return db.execute("SELECT * FROM credentials WHERE credential_id=?", (credential_id,)).fetchone()

    def user(self, user_id: str) -> sqlite3.Row | None:
        with self._session() as db:
            return db.execute("SELECT * FROM users WHERE id=? AND disabled_at IS NULL", (user_id,)).fetchone()

    def is_admin(self, user_id: str) -> bool:
        user = self.user(user_id)
        return bool(user and user["role"] == "admin")

    def users(self) -> list[sqlite3.Row]:
        with self._session() as db:
            return db.execute(
                "SELECT u.id,u.display_name,u.role,u.created_at,COUNT(c.credential_id) AS credential_count "
                "FROM users u LEFT JOIN credentials c ON c.user_id=u.id "
                "WHERE u.disabled_at IS NULL GROUP BY u.id ORDER BY u.created_at,u.id"
            ).fetchall()

    def credential_summaries(self) -> list[sqlite3.Row]:
        with self._session() as db:
            return db.execute(
                "SELECT credential_id,user_id,created_at FROM credentials ORDER BY user_id,created_at"
            ).fetchall()

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("ascii")).hexdigest()

    def create_invitation(self, display_name: str) -> tuple[str, str]:
        name = " ".join(display_name.split())
        if not name or len(name) > 80:
            raise ValueError("Display name must contain 1 to 80 characters")
        user_id = "u_" + secrets.token_hex(16)
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        with self._session() as db:
            db.execute("INSERT INTO users(id,display_name,role,created_at) VALUES(?,?, 'user', ?)",
                       (user_id, name, now))
            db.execute("INSERT INTO invitations(token_hash,user_id,created_at,expires_at) VALUES(?,?,?,?)",
                       (self._token_hash(token), user_id, now, now + INVITE_MAX_AGE))
        return user_id, token

    def invitation(self, token: str | None) -> sqlite3.Row | None:
        if not token or len(token) > 128 or not token.isascii() or not all(
            character.isalnum() or character in "-_" for character in token
        ):
            return None
        now = int(time.time())
        with self._session() as db:
            return db.execute(
                "SELECT i.user_id,u.display_name FROM invitations i JOIN users u ON u.id=i.user_id "
                "WHERE i.token_hash=? AND i.used_at IS NULL AND i.expires_at>? AND u.disabled_at IS NULL",
                (self._token_hash(token), now),
            ).fetchone()

    def add_credential(
        self, credential_id: bytes, public_key: bytes, sign_count: int, transports: str,
        *, user_id: str = ADMIN_ID, display_name: str = "Admin", first_only: bool = False,
        invite_token: str | None = None,
    ) -> bool:
        now = int(time.time())
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            # The first credential creates the one local admin. Additional
            # credentials can only be added by an authenticated admin route.
            if first_only and db.execute("SELECT 1 FROM credentials LIMIT 1").fetchone():
                return False
            if invite_token:
                invitation = db.execute(
                    "SELECT user_id FROM invitations WHERE token_hash=? AND used_at IS NULL AND expires_at>?",
                    (self._token_hash(invite_token), now),
                ).fetchone()
                if (
                    invitation is None
                    or invitation["user_id"] != user_id
                    or db.execute("SELECT 1 FROM credentials WHERE user_id=? LIMIT 1", (user_id,)).fetchone()
                ):
                    return False
            elif user_id != ADMIN_ID and not db.execute(
                "SELECT 1 FROM users WHERE id=? AND disabled_at IS NULL", (user_id,)
            ).fetchone():
                return False
            if user_id == ADMIN_ID:
                role = "admin"
            else:
                role = "user"
            db.execute(
                "INSERT OR IGNORE INTO users(id,display_name,role,created_at) VALUES(?,?,?,?)",
                (user_id, display_name, role, now),
            )
            if not db.execute("SELECT 1 FROM users WHERE id=? AND disabled_at IS NULL", (user_id,)).fetchone():
                return False
            inserted = db.execute(
                "INSERT OR IGNORE INTO credentials(credential_id,user_id,public_key,sign_count,transports,created_at) "
                "VALUES(?,?,?,?,?,?)", (credential_id, user_id, public_key, sign_count, transports, now),
            )
            if inserted.rowcount == 1 and invite_token:
                db.execute("UPDATE invitations SET used_at=? WHERE user_id=?", (now, user_id))
            return inserted.rowcount == 1

    def save_challenge(self, flow_id: str, challenge: bytes, ceremony: str, user_id: str = ADMIN_ID) -> None:
        now = int(time.time())
        with self._session() as db:
            db.execute("DELETE FROM challenges WHERE created_at<?", (now - CHALLENGE_MAX_AGE,))
            db.execute(
                "INSERT INTO challenges(flow_id,challenge,ceremony,user_id,created_at) VALUES(?,?,?,?,?)",
                (flow_id, challenge, ceremony, user_id, now),
            )

    def consume_challenge(self, flow_id: str, ceremony: str) -> tuple[bytes, str] | None:
        now = int(time.time())
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT challenge,user_id FROM challenges WHERE flow_id=? AND ceremony=? AND created_at>=?",
                (flow_id, ceremony, now - CHALLENGE_MAX_AGE),
            ).fetchone()
            db.execute("DELETE FROM challenges WHERE flow_id=?", (flow_id,))
            return (bytes(row["challenge"]), str(row["user_id"])) if row else None

    def create_session(self, user_id: str = ADMIN_ID) -> str:
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        with self._session() as db:
            db.execute("DELETE FROM sessions WHERE expires_at<=?", (now,))
            db.execute(
                "INSERT OR IGNORE INTO users(id,display_name,role,created_at) VALUES(?,?,?,?)",
                (user_id, "Admin" if user_id == ADMIN_ID else user_id,
                 "admin" if user_id == ADMIN_ID else "user", now),
            )
            db.execute(
                "INSERT INTO sessions(token_hash,user_id,created_at,expires_at) VALUES(?,?,?,?)",
                (self._token_hash(token), user_id, now, now + SESSION_MAX_AGE),
            )
        return token

    def user_for_session(self, token: str | None) -> str | None:
        if not token or len(token) > 128 or not token.isascii() or not all(
            character.isalnum() or character in "-_" for character in token
        ):
            return None
        now = int(time.time())
        with self._session() as db:
            row = db.execute(
                "SELECT s.user_id FROM sessions s JOIN users u ON u.id=s.user_id "
                "WHERE s.token_hash=? AND s.expires_at>? AND u.disabled_at IS NULL",
                (self._token_hash(token), now),
            ).fetchone()
        return str(row["user_id"]) if row else None

    def revoke_session(self, token: str | None) -> None:
        if not token or len(token) > 128 or not token.isascii() or not all(
            character.isalnum() or character in "-_" for character in token
        ):
            return
        with self._session() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (self._token_hash(token),))

    def disable_user(self, user_id: str) -> bool:
        if user_id == ADMIN_ID or not re.fullmatch(r"u_[a-f0-9]{32}", user_id):
            return False
        now = int(time.time())
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute("UPDATE users SET disabled_at=? WHERE id=? AND disabled_at IS NULL", (now, user_id))
            if cursor.rowcount:
                db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
                db.execute("DELETE FROM credentials WHERE user_id=?", (user_id,))
                db.execute("DELETE FROM invitations WHERE user_id=?", (user_id,))
            return cursor.rowcount == 1

    def revoke_credential(self, credential_id: bytes) -> bool:
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT user_id FROM credentials WHERE credential_id=?", (credential_id,)).fetchone()
            if row is None:
                return False
            user_id = str(row["user_id"])
            count = int(db.execute("SELECT COUNT(*) FROM credentials WHERE user_id=?", (user_id,)).fetchone()[0])
            if count <= 1:
                return False
            db.execute("DELETE FROM credentials WHERE credential_id=?", (credential_id,))
            db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
            return True


def new_flow_id() -> str:
    return secrets.token_urlsafe(24)


def new_challenge() -> bytes:
    return secrets.token_bytes(32)
