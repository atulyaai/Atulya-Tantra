"""Encryption at rest for SQLite memory stores."""
from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path
from typing import Any


class EncryptedStorage:
    def __init__(self, key: str | None = None):
        self._key = key or os.environ.get("ATULYA_ENCRYPTION_KEY", "default-key-change-in-production")
        self._salt = hashlib.sha256(self._key.encode()).digest()[:16]

    def _derive_key(self, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", self._key.encode(), salt, 100000, dklen=32)

    def encrypt_value(self, value: str) -> str:
        """Simple XOR-based encryption for sensitive values."""
        key_bytes = hashlib.sha256(self._key.encode()).digest()
        value_bytes = value.encode()
        encrypted = bytes(v ^ key_bytes[i % len(key_bytes)] for i, v in enumerate(value_bytes))
        return encrypted.hex()

    def decrypt_value(self, encrypted: str) -> str:
        encrypted_bytes = bytes.fromhex(encrypted)
        key_bytes = hashlib.sha256(self._key.encode()).digest()
        decrypted = bytes(e ^ key_bytes[i % len(key_bytes)] for i, e in enumerate(encrypted_bytes))
        return decrypted.decode()

    def encrypt_db(self, db_path: str | Path):
        """Encrypt SQLite database by encrypting sensitive columns."""
        db_path = Path(db_path)
        if not db_path.exists():
            return
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        # Find tables with sensitive columns
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [r[1] for r in cursor.fetchall()]
            sensitive = [c for c in columns if any(kw in c.lower() for kw in ["key", "secret", "password", "token", "api"])]
            for col in sensitive:
                cursor.execute(f"SELECT rowid, {col} FROM {table} WHERE {col} IS NOT NULL")
                rows = cursor.fetchall()
                for rowid, value in rows:
                    if not value.startswith("enc:"):
                        encrypted = self.encrypt_value(value)
                        cursor.execute(f"UPDATE {table} SET {col} = ? WHERE rowid = ?", (f"enc:{encrypted}", rowid))
        conn.commit()
        conn.close()

    def decrypt_db(self, db_path: str | Path):
        """Decrypt SQLite database."""
        db_path = Path(db_path)
        if not db_path.exists():
            return
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [r[1] for r in cursor.fetchall()]
            sensitive = [c for c in columns if any(kw in c.lower() for kw in ["key", "secret", "password", "token", "api"])]
            for col in sensitive:
                cursor.execute(f"SELECT rowid, {col} FROM {table} WHERE {col} LIKE 'enc:%'")
                rows = cursor.fetchall()
                for rowid, value in rows:
                    decrypted = self.decrypt_value(value[4:])
                    cursor.execute(f"UPDATE {table} SET {col} = ? WHERE rowid = ?", (decrypted, rowid))
        conn.commit()
        conn.close()
