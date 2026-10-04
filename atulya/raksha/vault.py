"""Encryption at rest for the files that hold your private data.

Turn it on by setting ``ATULYA_VAULT_PASSPHRASE`` in ``.env``. The key is derived from that passphrase (scrypt) and a
random salt kept in ``data/vault.salt``; the passphrase itself is never written anywhere. Files are encrypted with
Fernet (AES-128-CBC + HMAC), so a changed or corrupted file is detected rather than silently read.

Rules this module keeps:
  * No passphrase: files stay readable text, and ``status()`` says the vault is off. It never pretends.
  * A file that is encrypted but cannot be opened (no or wrong passphrase) raises ``VaultLocked``, and nothing may
    overwrite it. A wrong passphrase cannot destroy your data.
  * Plain files are encrypted the next time they are written (or all at once with ``encrypt_tree``).
  * Lose the passphrase and the data is gone; there is no recovery.
"""
from __future__ import annotations

import base64
import os
import secrets
from pathlib import Path

from cryptography.exceptions import InvalidTag  # noqa: F401  (re-exported for callers that catch it)
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"ATV1"
_cache: dict[tuple[str, bytes], Fernet] = {}


class VaultLocked(Exception):
    """An encrypted file could not be opened: the passphrase is missing, wrong, or the file was altered."""


def _salt_path() -> Path:
    return Path(os.environ.get("ATULYA_VAULT_DIR", "data")) / "vault.salt"


def enabled() -> bool:
    return bool(os.environ.get("ATULYA_VAULT_PASSPHRASE", ""))


def _fernet() -> Fernet:
    passphrase = os.environ.get("ATULYA_VAULT_PASSPHRASE", "")
    if not passphrase:
        raise VaultLocked("This data is encrypted. Set ATULYA_VAULT_PASSPHRASE in .env to open it.")
    salt_file = _salt_path()
    if not salt_file.exists():
        salt_file.parent.mkdir(parents=True, exist_ok=True)
        salt_file.write_bytes(secrets.token_bytes(16))
    salt = salt_file.read_bytes()
    if (passphrase, salt) not in _cache:
        key = Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(passphrase.encode("utf-8"))
        _cache.clear()
        _cache[(passphrase, salt)] = Fernet(base64.urlsafe_b64encode(key))
    return _cache[(passphrase, salt)]


def is_encrypted(blob: bytes) -> bool:
    return blob.startswith(MAGIC)


def decrypt_bytes(blob: bytes) -> bytes:
    try:
        return _fernet().decrypt(blob[len(MAGIC):])
    except InvalidToken as exc:
        raise VaultLocked("Wrong passphrase, or the file was changed.") from exc


def read_text(path: Path, encoding: str = "utf-8") -> str:
    blob = Path(path).read_bytes()
    return (decrypt_bytes(blob) if is_encrypted(blob) else blob).decode(encoding)


def write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write ``text`` (encrypted when the vault is on). Refuses to overwrite an encrypted file it cannot open."""
    path = Path(path)
    if path.exists():
        existing = path.read_bytes()
        if is_encrypted(existing):
            decrypt_bytes(existing)  # raises VaultLocked: never overwrite what we cannot read
    data = text.encode(encoding)
    if enabled():
        data = MAGIC + _fernet().encrypt(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    tmp.replace(path)


def status(root: Path | str = "data") -> dict[str, object]:
    root = Path(root)
    enc = plain = 0
    for f in root.rglob("*.json") if root.exists() else []:
        try:
            if is_encrypted(f.read_bytes()[:4]):
                enc += 1
            else:
                plain += 1
        except OSError:
            continue
    return {"on": enabled(), "encrypted_files": enc, "plain_files": plain}


# Files that hold private data. Everything else (settings, caches, tokens meant to be read by tools) stays as is.
PRIVATE = ("money.json", "calendar.json", "reminders.json", "email_config.json", "tracking.json", "chat_history.json", "fabric.json")


def encrypt_tree(root: Path | str = "data") -> int:
    """Encrypt every private file under ``root`` now. Returns how many were converted."""
    if not enabled():
        raise VaultLocked("Set ATULYA_VAULT_PASSPHRASE in .env first.")
    done = 0
    for f in Path(root).rglob("*.json"):
        if f.name in PRIVATE or f.parent.name == "profiles":
            blob = f.read_bytes()
            if not is_encrypted(blob):
                write_text(f, blob.decode("utf-8"))
                done += 1
    return done
