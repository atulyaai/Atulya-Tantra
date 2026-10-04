from __future__ import annotations

import base64
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class EncryptedStorage:
    def __init__(self, data_dir: str | Path, key: str | None = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._key = key or os.environ.get("ATULYA_ENCRYPTION_KEY") or self._load_or_create_key()

    def _key_path(self) -> Path:
        return self.data_dir / ".enc_key"

    def _load_or_create_key(self) -> str:
        key_path = self._key_path()
        if key_path.exists():
            return key_path.read_text().strip()
        try:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key().decode()
            key_path.write_text(key)
            return key
        except ImportError:
            logger.warning("cryptography not available, using base64 fallback")
            fallback = base64.urlsafe_b64encode(os.urandom(32)).decode()
            key_path.write_text(fallback)
            return fallback

    def _get_fernet(self):
        try:
            from cryptography.fernet import Fernet
            return Fernet(self._key.encode() if isinstance(self._key, str) else self._key)
        except ImportError:
            return None

    def encrypt(self, data: dict[str, Any], name: str) -> Path:
        with self._lock:
            path = self.data_dir / f"{name}.enc"
            f = self._get_fernet()
            payload = json.dumps(data).encode()
            if f:
                encrypted = f.encrypt(payload)
            else:
                encrypted = base64.urlsafe_b64encode(payload)
            path.write_bytes(encrypted)
            return path

    def decrypt(self, name: str) -> dict[str, Any] | None:
        path = self.data_dir / f"{name}.enc"
        if not path.exists():
            return None
        with self._lock:
            try:
                data = path.read_bytes()
                f = self._get_fernet()
                if f:
                    decrypted = f.decrypt(data)
                else:
                    decrypted = base64.urlsafe_b64decode(data)
                return json.loads(decrypted)
            except Exception as e:
                logger.error("Decryption failed for %s: %s", name, e)
                return None

    def delete(self, name: str) -> bool:
        path = self.data_dir / f"{name}.enc"
        if path.exists():
            path.unlink()
            return True
        return False

    def list_keys(self) -> list[str]:
        return sorted(set(p.stem for p in self.data_dir.glob("*.enc")))
