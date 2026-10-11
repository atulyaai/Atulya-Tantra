"""Keep API keys and tokens encrypted at rest instead of plain text in .env.

    python -m atulya.cli secrets protect   # move secret values from .env into data/secrets.enc
    python -m atulya.cli secrets status

Windows: DPAPI (CryptProtectData), bound to the current Windows user — another user,
or the file copied to another PC, cannot decrypt it. Other systems: the file is
written with owner-only permissions (0600); install the OS keyring later for more.
At startup `load_protected()` puts the values into the process environment, so the
rest of Atulya keeps reading os.environ as before.
"""
from __future__ import annotations

import base64
import ctypes
import json
import os
import re
from pathlib import Path

SECRET_KEY = re.compile(r"(_API_KEY|_TOKEN|_SECRET|_PASSWORD)$")
ENTROPY = b"atulya-tantra-secrets-v1"


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data: bytes, protect: bool) -> bytes:
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    source = _Blob(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_char)))
    entropy = _Blob(len(ENTROPY), ctypes.cast(ctypes.create_string_buffer(ENTROPY, len(ENTROPY)), ctypes.POINTER(ctypes.c_char)))
    out = _Blob()
    call = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    # 0x1 = CRYPTPROTECT_UI_FORBIDDEN
    if not call(ctypes.byref(source), None, ctypes.byref(entropy), None, None, 0x1, ctypes.byref(out)):
        raise OSError("Windows could not " + ("encrypt" if protect else "decrypt") + " the secrets file")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


def _encode(values: dict[str, str]) -> bytes:
    raw = json.dumps(values).encode("utf-8")
    if os.name == "nt":
        return b"DPAPI:" + base64.b64encode(_dpapi(raw, True))
    return b"PLAIN:" + base64.b64encode(raw)


def _decode(blob: bytes) -> dict[str, str]:
    kind, _, payload = blob.partition(b":")
    raw = base64.b64decode(payload)
    if kind == b"DPAPI":
        raw = _dpapi(raw, False)
    return json.loads(raw.decode("utf-8"))


def secrets_path(data_dir: Path) -> Path:
    return data_dir / "secrets.enc"


def load_protected(data_dir: Path) -> int:
    """Add stored secrets to os.environ (never overriding a value already set). Returns count."""
    path = secrets_path(data_dir)
    if not path.is_file():
        return 0
    values = _decode(path.read_bytes())
    for key, value in values.items():
        if not os.environ.get(key):
            os.environ[key] = value
    return len(values)


def set_secret(data_dir: Path, key: str, value: str) -> None:
    """Add or replace one encrypted secret."""
    if not re.fullmatch(r"[A-Z0-9_]{2,64}", key) or not value.strip():
        raise ValueError("Use an UPPER_CASE name and a non-empty value")
    path = secrets_path(data_dir)
    stored = _decode(path.read_bytes()) if path.is_file() else {}
    stored[key] = value.strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_encode(stored))
    if _decode(path.read_bytes()) != stored:
        raise OSError("Encrypted secrets did not verify")


def protect(env_file: Path, data_dir: Path) -> list[str]:
    """Move secret-looking values from .env into the encrypted store; blank them in .env."""
    lines = env_file.read_text(encoding="utf-8").splitlines()
    path = secrets_path(data_dir)
    stored = _decode(path.read_bytes()) if path.is_file() else {}
    moved = []
    for index, line in enumerate(lines):
        match = re.match(r"^\s*([A-Z0-9_]+)\s*=\s*(.*)$", line)
        if not match or not SECRET_KEY.search(match.group(1)):
            continue
        value = match.group(2).strip().strip('"').strip("'")
        if value:
            stored[match.group(1)] = value
            lines[index] = f"{match.group(1)}=  # stored encrypted in data/secrets.enc"
            moved.append(match.group(1))
    if moved:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_encode(stored))
        if os.name != "nt":
            path.chmod(0o600)
        # Verify before touching .env, so a failed encryption can never lose a key.
        if _decode(path.read_bytes()) != stored:
            raise OSError("Encrypted secrets did not verify; .env was left unchanged")
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return moved
