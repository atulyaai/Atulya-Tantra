"""Encryption at rest for SQLite memory stores."""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


_SQL_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def _validate_identifier(name: str) -> str:
    if not _SQL_IDENTIFIER.fullmatch(name):
        raise ValueError(f"Unsafe SQLite identifier: {name!r}")
    return name


class EncryptedStorage:
    def __init__(self, key: str | None = None):
        resolved = key or os.environ.get("ATULYA_ENCRYPTION_KEY")
        if not resolved:
            raise ValueError(
                "EncryptedStorage requires a key via constructor argument or "
                "ATULYA_ENCRYPTION_KEY environment variable"
            )
        self._key = resolved
        self._master_key = self._key.encode("utf-8")

    def _derive_encryption_key(self, salt: bytes) -> bytes:
        return PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=390_000,
        ).derive(self._master_key)

    def encrypt_value(self, value: str) -> str:
        """Encrypt a value with AES-GCM using per-record salt and nonce."""
        salt = os.urandom(16)
        nonce = os.urandom(12)
        ciphertext = AESGCM(self._derive_encryption_key(salt)).encrypt(nonce, value.encode(), None)
        return "v2:" + (salt + nonce + ciphertext).hex()

    def decrypt_value(self, encrypted: str) -> str:
        if encrypted.startswith("v2:"):
            raw = bytes.fromhex(encrypted[3:])
            salt, nonce, cipher = raw[:16], raw[16:28], raw[28:]
            key = self._derive_encryption_key(salt)
        else:
            raw = bytes.fromhex(encrypted)
            salt, nonce, cipher = b"", raw[:12], raw[12:]
            key = hashlib.sha256(self._master_key).digest()
        decrypted = AESGCM(key).decrypt(nonce, cipher, None)
        return decrypted.decode("utf-8")

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
            table = _validate_identifier(table)
            cursor.execute(f"PRAGMA table_info(\"{table}\")")
            columns = [r[1] for r in cursor.fetchall()]
            sensitive = [c for c in columns if any(kw in c.lower() for kw in ["key", "secret", "password", "token", "api"])]
            for col in sensitive:
                col = _validate_identifier(col)
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
            table = _validate_identifier(table)
            cursor.execute(f"PRAGMA table_info(\"{table}\")")
            columns = [r[1] for r in cursor.fetchall()]
            sensitive = [c for c in columns if any(kw in c.lower() for kw in ["key", "secret", "password", "token", "api"])]
            for col in sensitive:
                col = _validate_identifier(col)
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
