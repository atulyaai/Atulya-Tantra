"""Encrypted daily backups of Atulya's data, kept locally and copied off-site to the owner's server.

    python -m atulya.cli backup            # make one now
    python -m atulya.cli backup --restore FILE   # restore (asks for the recovery key)

What is backed up: every SQLite database (copied with SQLite's online backup API, so it is
consistent while Atulya runs), the encrypted secrets file and push keys. The archive is
encrypted with AES-256-GCM using a random backup key. That key is stored in the encrypted
secrets store *and* shown once as a recovery key - without it a backup cannot be opened,
which also means a stolen backup is useless.
"""
from __future__ import annotations

import base64
import io
import json
import os
import secrets
import sqlite3
import subprocess
import tempfile
import time
import zipfile
from contextlib import closing
from pathlib import Path

MAGIC = b"ATULYA-BACKUP-1\n"
KEEP = 14


def _key(data_dir: Path) -> tuple[bytes, bool]:
    """Return (key, created_now)."""
    from atulya.secrets_store import set_secret

    stored = os.environ.get("ATULYA_BACKUP_KEY", "").strip()
    if stored:
        return base64.urlsafe_b64decode(stored + "=" * (-len(stored) % 4)), False
    key = secrets.token_bytes(32)
    encoded = base64.urlsafe_b64encode(key).decode().rstrip("=")
    set_secret(data_dir, "ATULYA_BACKUP_KEY", encoded)
    os.environ["ATULYA_BACKUP_KEY"] = encoded
    return key, True


def recovery_key() -> str:
    return os.environ.get("ATULYA_BACKUP_KEY", "")


def _archive(data_dir: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive, tempfile.TemporaryDirectory() as tmp:
        for database in sorted(data_dir.glob("*.sqlite3")):
            copy = Path(tmp) / database.name
            with closing(sqlite3.connect(database)) as source, closing(sqlite3.connect(copy)) as target:
                source.backup(target)  # consistent snapshot while the server is running
            archive.write(copy, database.name)
        for extra in ("secrets.enc", "telegram_members.json", "plugin_settings.json", "briefings.json",
                      "google_tokens.json", "routines.json", "maintenance-policy.json"):
            if (data_dir / extra).is_file():
                archive.write(data_dir / extra, extra)
        archive.writestr("manifest.json", json.dumps({"created": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                                      "files": archive.namelist()}))
    return buffer.getvalue()


def create(data_dir: Path) -> tuple[Path, bool]:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key, created = _key(data_dir)
    nonce = secrets.token_bytes(12)
    sealed = MAGIC + nonce + AESGCM(key).encrypt(nonce, _archive(data_dir), MAGIC)
    folder = data_dir / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"atulya-{time.strftime('%Y%m%d-%H%M%S')}.atb"
    path.write_bytes(sealed)
    for old in sorted(folder.glob("atulya-*.atb"))[:-KEEP]:
        old.unlink(missing_ok=True)
    return path, created


def decrypt(path: Path, key_text: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    blob = path.read_bytes()
    if not blob.startswith(MAGIC):
        raise ValueError("Not an Atulya backup")
    key = base64.urlsafe_b64decode(key_text.strip() + "=" * (-len(key_text.strip()) % 4))
    nonce = blob[len(MAGIC):len(MAGIC) + 12]
    return AESGCM(key).decrypt(nonce, blob[len(MAGIC) + 12:], MAGIC)


def restore(path: Path, key_text: str, data_dir: Path) -> list[str]:
    """Restore into data_dir; the current files are moved to data/before-restore-<time>/ first."""
    archive = zipfile.ZipFile(io.BytesIO(decrypt(path, key_text)))
    keep = data_dir / f"before-restore-{time.strftime('%Y%m%d-%H%M%S')}"
    keep.mkdir(parents=True)
    restored = []
    for name in archive.namelist():
        if name == "manifest.json" or "/" in name or "\\" in name:
            continue
        if (data_dir / name).exists():
            (data_dir / name).replace(keep / name)
        (data_dir / name).write_bytes(archive.read(name))
        restored.append(name)
    return restored


def copy_offsite(path: Path) -> str:
    """Copy the encrypted backup to the first server in ATULYA_SERVERS (name=user@host=keyfile)."""
    entries = [item.split("=") for item in os.environ.get("ATULYA_SERVERS", "").split(";") if item.count("=") == 2]
    if not entries:
        return "no server configured"
    _name, target, key = (part.strip() for part in entries[0])
    options = ["-i", key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
    try:
        subprocess.run(["ssh", *options, target, "mkdir -p ~/atulya-backups && ls -1t ~/atulya-backups/*.atb 2>/dev/null "
                        f"| tail -n +{KEEP} | xargs -r rm -f"], capture_output=True, timeout=30, check=True)
        subprocess.run(["scp", *options, str(path), f"{target}:atulya-backups/"], capture_output=True, timeout=120, check=True)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"off-site copy failed ({type(exc).__name__})"
    return f"copied to {target.split('@')[-1]}"
