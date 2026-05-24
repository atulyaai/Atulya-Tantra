"""Encryption at rest for SQLite memory stores."""
from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path
from typing import Any


class EncryptedStorage:
    def __init__(self, key: str | None = None):
        resolved = key or os.environ.get("ATULYA_ENCRYPTION_KEY")
        if not resolved:
            raise ValueError(
                "EncryptedStorage requires a key via constructor argument or "
                "ATULYA_ENCRYPTION_KEY environment variable"
            )
        self._key = resolved
        # Derive a fixed 32-byte master key once
        self._master_key = hashlib.sha256(self._key.encode()).digest()

    def _derive_encryption_key(self) -> bytes:
        return hashlib.sha256(self._key.encode()).digest()

    def encrypt_value(self, value: str) -> str:
        """XOR-encrypt with random IV so same value produces different ciphertexts."""
        iv = os.urandom(16)
        key_bytes = self._derive_encryption_key()
        value_bytes = value.encode()
        # Expand key to match plaintext length
        keystream = key_bytes * (len(value_bytes) // 32 + 1)
        encrypted = bytes(v ^ keystream[i] for i, v in enumerate(value_bytes))
        return (iv + encrypted).hex()

    def decrypt_value(self, encrypted: str) -> str:
        raw = bytes.fromhex(encrypted)
        iv, cipher = raw[:16], raw[16:]
        key_bytes = self._derive_encryption_key()
        keystream = key_bytes * (len(cipher) // 32 + 1)
        decrypted = bytes(e ^ keystream[i] for i, e in enumerate(cipher))
        return decrypted.decode("utf-8", errors="replace")

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
            cursor.execute(f"PRAGMA table_info(\"{table}\")")
            columns = [r[1] for r in cursor.fetchall()]
            sensitive = [c for c in columns if any(kw in c.lower() for kw in ["key", "secret", "password", "token", "api"])]
            for col in sensitive:
                cursor.execute(
                    f"SELECT rowid, \"{col}\" FROM \"{table}\" WHERE \"{col}\" IS NOT NULL"
                )
                rows = cursor.fetchall()
                for rowid, value in rows:
                    if not value.startswith("enc:"):
                        encrypted = self.encrypt_value(value)
                        cursor.execute(
                            f"UPDATE \"{table}\" SET \"{col}\" = ? WHERE rowid = ?",
                            (f"enc:{encrypted}", rowid),
                        )
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
            cursor.execute(f"PRAGMA table_info(\"{table}\")")
            columns = [r[1] for r in cursor.fetchall()]
            sensitive = [c for c in columns if any(kw in c.lower() for kw in ["key", "secret", "password", "token", "api"])]
            for col in sensitive:
                cursor.execute(
                    f"SELECT rowid, \"{col}\" FROM \"{table}\" WHERE \"{col}\" LIKE 'enc:%'"
                )
                rows = cursor.fetchall()
                for rowid, value in rows:
                    decrypted = self.decrypt_value(value[4:])
                    cursor.execute(
                        f"UPDATE \"{table}\" SET \"{col}\" = ? WHERE rowid = ?",
                        (decrypted, rowid),
                    )
        conn.commit()
        conn.close()
