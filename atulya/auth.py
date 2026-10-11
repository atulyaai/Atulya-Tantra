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
                CREATE TABLE IF NOT EXISTS passwords (
                    user_id TEXT PRIMARY KEY,
                    salt BLOB NOT NULL,
                    hash BLOB NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS signups (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    via TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'pending',
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS voice_unlock (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    device_hash TEXT NOT NULL,
                    phrase_salt BLOB NOT NULL,
                    phrase_hash BLOB NOT NULL,
                    label TEXT NOT NULL,
                    failures INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    last_used INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ip_strikes (
                    ip TEXT PRIMARY KEY,
                    strikes INTEGER NOT NULL,
                    first_at INTEGER NOT NULL,
                    blocked_until INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS login_aliases (
                    alias TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS login_failures (
                    key TEXT PRIMARY KEY,
                    count INTEGER NOT NULL,
                    first_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS login_requests (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    code_hash TEXT NOT NULL,
                    client TEXT NOT NULL,
                    label TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS device_links (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    used_at INTEGER
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
        """Sign-in methods that exist (passkeys + passwords). Zero means first-time setup is open."""
        with self._session() as db:
            return int(db.execute("SELECT (SELECT COUNT(*) FROM credentials) + (SELECT COUNT(*) FROM passwords)").fetchone()[0])

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

    # --- password fallback -----------------------------------------------
    # scrypt (n=2**14, r=8, p=1), per-user random salt; constant-time compare.
    @staticmethod
    def _password_hash(password: str, salt: bytes) -> bytes:
        return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)

    def set_password(self, user_id: str, password: str) -> None:
        if len(password) < 10:
            raise ValueError("Use at least 10 characters")
        salt = secrets.token_bytes(16)
        now = int(time.time())
        with self._session() as db:
            db.execute("INSERT OR IGNORE INTO users(id,display_name,role,created_at) VALUES(?,?,?,?)",
                       (user_id, "Admin" if user_id == ADMIN_ID else user_id,
                        "admin" if user_id == ADMIN_ID else "user", now))
            db.execute("INSERT OR REPLACE INTO passwords(user_id,salt,hash,updated_at) VALUES(?,?,?,?)",
                       (user_id, salt, self._password_hash(password, salt), now))

    def add_alias(self, alias: str, user_id: str) -> None:
        """Let a user sign in with another name, e.g. an email address."""
        alias = alias.strip().lower()
        if not re.fullmatch(r"[a-z0-9._%+-]{1,64}(@[a-z0-9.-]{1,190})?", alias):
            raise ValueError("Use a plain username or a valid email address")
        with self._session() as db:
            db.execute("INSERT OR REPLACE INTO login_aliases(alias,user_id) VALUES(?,?)", (alias, user_id))

    def resolve_login(self, name: str) -> str:
        name = name.strip().lower()
        with self._session() as db:
            row = db.execute("SELECT user_id FROM login_aliases WHERE alias=?", (name,)).fetchone()
        return str(row["user_id"]) if row else name

    # --- voice unlock on a trusted device -------------------------------------------
    # Two factors: a random device key kept only by that browser/app (possession) and a
    # spoken personal phrase (knowledge, scrypt-hashed after normalising). 5 wrong phrases
    # disable that device's voice unlock; unused for 30 days it expires.
    VOICE_UNLOCK_MAX_IDLE = 30 * 24 * 3600

    @staticmethod
    def normalize_phrase(text: str) -> str:
        words = re.findall(r"[^\W_]+", text.lower())
        return " ".join(words)

    def enroll_voice_unlock(self, user_id: str, phrase: str, label: str) -> tuple[str, str]:
        normalized = self.normalize_phrase(phrase)
        if len(normalized.split()) < 3 or len(normalized) < 12:
            raise ValueError("Choose a phrase of at least 3 words, e.g. 'saffron rocket at midnight'")
        unlock_id, device_secret = secrets.token_urlsafe(12), secrets.token_urlsafe(32)
        salt = secrets.token_bytes(16)
        now = int(time.time())
        with self._session() as db:
            db.execute("INSERT INTO voice_unlock(id,user_id,device_hash,phrase_salt,phrase_hash,label,created_at,"
                       "last_used) VALUES(?,?,?,?,?,?,?,?)",
                       (unlock_id, user_id, self._token_hash(device_secret), salt,
                        self._password_hash(normalized, salt), label[:80], now, now))
        return unlock_id, device_secret

    def check_voice_unlock(self, unlock_id: str, device_secret: str, spoken: str) -> str | None:
        now = int(time.time())
        with self._session() as db:
            row = db.execute("SELECT * FROM voice_unlock WHERE id=?", (unlock_id,)).fetchone()
            if (row is None or row["failures"] >= 5 or now - row["last_used"] > self.VOICE_UNLOCK_MAX_IDLE
                    or not secrets.compare_digest(self._token_hash(device_secret), row["device_hash"])):
                return None
            candidate = self._password_hash(self.normalize_phrase(spoken), bytes(row["phrase_salt"]))
            if not secrets.compare_digest(candidate, bytes(row["phrase_hash"])):
                db.execute("UPDATE voice_unlock SET failures=failures+1 WHERE id=?", (unlock_id,))
                return None
            if not db.execute("SELECT 1 FROM users WHERE id=? AND disabled_at IS NULL", (row["user_id"],)).fetchone():
                return None
            db.execute("UPDATE voice_unlock SET failures=0, last_used=? WHERE id=?", (now, unlock_id))
            return str(row["user_id"])

    def remove_voice_unlock(self, user_id: str, unlock_id: str | None = None) -> int:
        with self._session() as db:
            if unlock_id:
                return db.execute("DELETE FROM voice_unlock WHERE user_id=? AND id=?", (user_id, unlock_id)).rowcount
            return db.execute("DELETE FROM voice_unlock WHERE user_id=?", (user_id,)).rowcount

    # --- IP bans -----------------------------------------------------------------
    IP_STRIKE_LIMIT = 10
    IP_BAN_SECONDS = 3600
    IP_STRIKE_WINDOW = 24 * 3600  # slow attacks (a few tries an hour) still add up

    def strike_ip(self, ip: str) -> bool:
        """Count one failed/abusive auth attempt; returns True when the IP is now banned."""
        now = int(time.time())
        with self._session() as db:
            row = db.execute("SELECT strikes,first_at FROM ip_strikes WHERE ip=?", (ip,)).fetchone()
            if row is None or now - row["first_at"] > self.IP_STRIKE_WINDOW:
                db.execute("INSERT OR REPLACE INTO ip_strikes(ip,strikes,first_at,blocked_until) VALUES(?,1,?,0)",
                           (ip, now))
                return False
            strikes = row["strikes"] + 1
            until = now + self.IP_BAN_SECONDS if strikes >= self.IP_STRIKE_LIMIT else 0
            db.execute("UPDATE ip_strikes SET strikes=?, blocked_until=MAX(blocked_until,?) WHERE ip=?",
                       (strikes, until, ip))
            return bool(until)

    def ip_banned(self, ip: str) -> bool:
        with self._session() as db:
            row = db.execute("SELECT blocked_until FROM ip_strikes WHERE ip=?", (ip,)).fetchone()
        return bool(row and row["blocked_until"] > time.time())

    def banned_ips(self) -> list[sqlite3.Row]:
        with self._session() as db:
            return db.execute("SELECT ip,strikes,blocked_until FROM ip_strikes WHERE blocked_until>?",
                              (int(time.time()),)).fetchall()

    # --- self sign-up (owner approves) ------------------------------------------------
    COMMON_PASSWORDS = {"password123", "1234567890", "qwertyuiop", "iloveyou12", "password12", "admin12345"}

    @classmethod
    def password_problem(cls, password: str, email: str = "") -> str | None:
        if len(password) < 10:
            return "Use at least 10 characters."
        if password.lower() in cls.COMMON_PASSWORDS or (email and email.split("@")[0].lower() in password.lower()):
            return "That password is too easy to guess."
        kinds = sum(bool(re.search(pattern, password)) for pattern in (r"[a-z]", r"[A-Z]", r"\d", r"[^\w]"))
        if kinds < 3:
            return "Mix at least three of: lowercase, uppercase, numbers, symbols."
        return None

    def create_signup(self, name: str, email: str, password: str | None, via: str) -> str:
        """Create a pending (disabled) account; the owner approves it before it can sign in."""
        email = email.strip().lower()
        if not re.fullmatch(r"[a-z0-9._%+-]{1,64}@[a-z0-9.-]{1,190}\.[a-z]{2,}", email):
            raise ValueError("Enter a valid email address")
        if password is not None and (problem := self.password_problem(password, email)):
            raise ValueError(problem)
        with self._session() as db:
            if db.execute("SELECT 1 FROM login_aliases WHERE alias=?", (email,)).fetchone() or \
                    db.execute("SELECT 1 FROM signups WHERE email=?", (email,)).fetchone():
                raise ValueError("An account with that email already exists or is waiting for approval")
            user_id = "u_" + secrets.token_hex(16)
            now = int(time.time())
            db.execute("INSERT INTO users(id,display_name,role,created_at,disabled_at) VALUES(?,?,'user',?,?)",
                       (user_id, " ".join(name.split())[:80] or email, now, now))
            db.execute("INSERT INTO signups(user_id,email,via,created_at) VALUES(?,?,?,?)", (user_id, email, via, now))
            db.execute("INSERT INTO login_aliases(alias,user_id) VALUES(?,?)", (email, user_id))
        if password is not None:
            salt = secrets.token_bytes(16)
            with self._session() as db:
                db.execute("INSERT INTO passwords(user_id,salt,hash,updated_at) VALUES(?,?,?,?)",
                           (user_id, salt, self._password_hash(password, salt), int(time.time())))
        return user_id

    def pending_signups(self) -> list[sqlite3.Row]:
        with self._session() as db:
            return db.execute("SELECT s.user_id,s.email,s.via,s.created_at,u.display_name FROM signups s "
                              "JOIN users u ON u.id=s.user_id WHERE s.state='pending' ORDER BY s.created_at").fetchall()

    def decide_signup(self, user_id: str, approve: bool) -> bool:
        with self._session() as db:
            cursor = db.execute("UPDATE signups SET state=? WHERE user_id=? AND state='pending'",
                                ("approved" if approve else "denied", user_id))
            if cursor.rowcount and approve:
                db.execute("UPDATE users SET disabled_at=NULL WHERE id=?", (user_id,))
            return cursor.rowcount == 1

    def ensure_user(self, user_id: str, display_name: str, role: str = "user") -> None:
        with self._session() as db:
            db.execute("INSERT OR IGNORE INTO users(id,display_name,role,created_at) VALUES(?,?,?,?)",
                       (user_id, display_name[:80] or user_id, role, int(time.time())))

    def has_password(self) -> bool:
        with self._session() as db:
            return db.execute("SELECT 1 FROM passwords LIMIT 1").fetchone() is not None

    def check_password(self, user_id: str, password: str, client: str) -> str:
        """Returns 'ok', 'bad', or 'locked'.

        5 failures per user+client, or 20 per user from any mix of clients, lock password
        sign-in for 15 minutes (passkeys keep working, so a lock cannot shut the owner out).
        """
        key = f"{user_id}|{client}"
        account_key = f"{user_id}|*"
        now = int(time.time())
        with self._session() as db:
            db.execute("DELETE FROM login_failures WHERE ?-first_at>900", (now,))
            failure = db.execute("SELECT count FROM login_failures WHERE key=?", (key,)).fetchone()
            account = db.execute("SELECT count FROM login_failures WHERE key=?", (account_key,)).fetchone()
            if (failure and failure["count"] >= 5) or (account and account["count"] >= 20):
                return "locked"
            row = db.execute(
                "SELECT p.salt,p.hash FROM passwords p JOIN users u ON u.id=p.user_id "
                "WHERE p.user_id=? AND u.disabled_at IS NULL", (user_id,),
            ).fetchone()
            candidate = self._password_hash(password, bytes(row["salt"]) if row else b"0" * 16)
            if row and secrets.compare_digest(candidate, bytes(row["hash"])):
                db.execute("DELETE FROM login_failures WHERE key=?", (key,))
                return "ok"
            for failure_key in (key, account_key):
                db.execute(
                    "INSERT INTO login_failures(key,count,first_at) VALUES(?,1,?) "
                    "ON CONFLICT(key) DO UPDATE SET count=count+1", (failure_key, now))
            return "bad"

    # --- sign-in by approval or one-time code ------------------------------
    # A new device asks to sign in; the code goes to the user's other channels
    # (Telegram, email) and signed-in devices get an approve/deny card. Codes are
    # hashed, single-use, 5 minutes, 5 attempts; at most 3 open requests per user.
    def create_login_request(self, user_id: str, client: str, label: str) -> tuple[str, str] | None:
        now = int(time.time())
        with self._session() as db:
            if not db.execute("SELECT 1 FROM users WHERE id=? AND disabled_at IS NULL", (user_id,)).fetchone():
                return None
            db.execute("DELETE FROM login_requests WHERE expires_at<?", (now - 3600,))
            open_count = db.execute("SELECT COUNT(*) FROM login_requests WHERE user_id=? AND state='pending' "
                                    "AND expires_at>?", (user_id, now)).fetchone()[0]
            recent = db.execute("SELECT 1 FROM login_requests WHERE client=? AND created_at>?",
                                (client, now - 30)).fetchone()
            if open_count >= 3 or recent:
                raise ValueError("Too many sign-in requests. Wait a moment and try again.")
            request_id = secrets.token_urlsafe(18)
            code = f"{secrets.randbelow(10 ** 6):06d}"
            db.execute("INSERT INTO login_requests(id,user_id,code_hash,client,label,created_at,expires_at) "
                       "VALUES(?,?,?,?,?,?,?)", (request_id, user_id, self._token_hash(code), client, label[:80],
                                                 now, now + 300))
        return request_id, code

    def login_request(self, request_id: str) -> sqlite3.Row | None:
        with self._session() as db:
            return db.execute("SELECT * FROM login_requests WHERE id=?", (request_id,)).fetchone()

    def pending_logins(self, user_id: str) -> list[sqlite3.Row]:
        with self._session() as db:
            return db.execute("SELECT id,label,client,created_at FROM login_requests WHERE user_id=? AND "
                              "state='pending' AND expires_at>? ORDER BY created_at DESC",
                              (user_id, int(time.time()))).fetchall()

    def decide_login(self, request_id: str, approver: str, approve: bool) -> bool:
        with self._session() as db:
            cursor = db.execute("UPDATE login_requests SET state=? WHERE id=? AND user_id=? AND state='pending' "
                                "AND expires_at>?", ("approved" if approve else "denied", request_id, approver,
                                                     int(time.time())))
            return cursor.rowcount == 1

    def redeem_login(self, request_id: str, code: str | None) -> str | None:
        """Return the user id once: when approved, or when the code matches. Then the request is spent."""
        now = int(time.time())
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM login_requests WHERE id=?", (request_id,)).fetchone()
            if row is None or row["expires_at"] < now or row["state"] not in {"pending", "approved"}:
                return None
            if row["state"] == "approved":
                db.execute("UPDATE login_requests SET state='used' WHERE id=?", (request_id,))
                return str(row["user_id"])
            if code is None:
                return None
            if row["attempts"] >= 5:
                db.execute("UPDATE login_requests SET state='denied' WHERE id=?", (request_id,))
                return None
            if secrets.compare_digest(self._token_hash(code), row["code_hash"]):
                db.execute("UPDATE login_requests SET state='used' WHERE id=?", (request_id,))
                return str(row["user_id"])
            db.execute("UPDATE login_requests SET attempts=attempts+1 WHERE id=?", (request_id,))
            return None

    def create_device_link(self, user_id: str) -> str:
        """One-time, 10-minute code that lets a signed-in user add a passkey on another device/address."""
        token = secrets.token_urlsafe(24)
        now = int(time.time())
        with self._session() as db:
            db.execute("INSERT INTO device_links(token_hash,user_id,created_at,expires_at) VALUES(?,?,?,?)",
                       (self._token_hash(token), user_id, now, now + 600))
        return token

    def device_link(self, token: str | None) -> sqlite3.Row | None:
        if not token or len(token) > 128 or not token.isascii() or not all(
            character.isalnum() or character in "-_" for character in token
        ):
            return None
        with self._session() as db:
            return db.execute(
                "SELECT d.user_id,u.display_name FROM device_links d JOIN users u ON u.id=d.user_id "
                "WHERE d.token_hash=? AND d.used_at IS NULL AND d.expires_at>? AND u.disabled_at IS NULL",
                (self._token_hash(token), int(time.time())),
            ).fetchone()

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
        device_token: str | None = None,
    ) -> bool:
        now = int(time.time())
        with self._session() as db:
            db.execute("BEGIN IMMEDIATE")
            # The first credential creates the one local admin. Additional
            # credentials can only be added by an authenticated admin route.
            if first_only and db.execute(
                "SELECT 1 FROM credentials UNION ALL SELECT 1 FROM passwords LIMIT 1").fetchone():
                return False
            if device_token:
                link = db.execute(
                    "SELECT user_id FROM device_links WHERE token_hash=? AND used_at IS NULL AND expires_at>?",
                    (self._token_hash(device_token), now),
                ).fetchone()
                if link is None or link["user_id"] != user_id:
                    return False
                db.execute("UPDATE device_links SET used_at=? WHERE token_hash=?", (now, self._token_hash(device_token)))
            elif invite_token:
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
