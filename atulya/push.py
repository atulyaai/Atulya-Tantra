"""Web Push notifications (VAPID): sign-in requests, approvals and alerts reach browsers even when closed.

Keys are generated once and the private key is kept encrypted with the other secrets
(atulya/secrets_store.py). Subscriptions are per user in data/push.sqlite3; dead ones
(HTTP 404/410 from the push service) are removed automatically.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path

logger = logging.getLogger(__name__)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


class PushService:
    def __init__(self, data_dir: Path, contact: str = "mailto:aj@atulvij.com") -> None:
        self.data_dir = data_dir
        self.contact = contact
        self.path = data_dir / "push.sqlite3"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS subscriptions (endpoint TEXT PRIMARY KEY, user_id TEXT NOT NULL, "
                       "data TEXT NOT NULL, created_at INTEGER NOT NULL)")
        self.public_key, self._private_pem = self._keys()

    def _keys(self) -> tuple[str, str]:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        from .secrets_store import set_secret

        pem = os.environ.get("ATULYA_VAPID_PRIVATE_KEY", "").replace("\\n", "\n")
        if not pem:
            key = ec.generate_private_key(ec.SECP256R1())
            pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()).decode()
            try:
                set_secret(self.data_dir, "ATULYA_VAPID_PRIVATE_KEY", pem.replace("\n", "\\n"))
            except (OSError, ValueError):
                logger.warning("Could not store the push key; subscriptions will need renewing after restart")
            os.environ["ATULYA_VAPID_PRIVATE_KEY"] = pem.replace("\n", "\\n")
        key = serialization.load_pem_private_key(pem.encode(), password=None)
        public = key.public_key().public_bytes(serialization.Encoding.X962,
                                               serialization.PublicFormat.UncompressedPoint)
        return _b64(public), pem

    def subscribe(self, user_id: str, subscription: dict) -> None:
        endpoint = str(subscription.get("endpoint", ""))
        if not endpoint.startswith("https://") or "keys" not in subscription:
            raise ValueError("Invalid push subscription")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT OR REPLACE INTO subscriptions(endpoint,user_id,data,created_at) VALUES(?,?,?,?)",
                       (endpoint, user_id, json.dumps(subscription), int(time.time())))

    # --- RFC 8291 (aes128gcm) + RFC 8292 (VAPID) with `cryptography` only; no extra packages ---
    def _vapid_header(self, endpoint: str) -> str:
        from urllib.parse import urlsplit

        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

        parts = urlsplit(endpoint)
        header = _b64(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
        claims = _b64(json.dumps({"aud": f"{parts.scheme}://{parts.netloc}", "exp": int(time.time()) + 12 * 3600,
                                  "sub": self.contact}, separators=(",", ":")).encode())
        key = serialization.load_pem_private_key(self._private_pem.encode(), password=None)
        r, s_value = decode_dss_signature(key.sign(f"{header}.{claims}".encode(), ec.ECDSA(hashes.SHA256())))
        signature = _b64(r.to_bytes(32, "big") + s_value.to_bytes(32, "big"))
        return f"vapid t={header}.{claims}.{signature}, k={self.public_key}"

    @staticmethod
    def encrypt(payload: bytes, p256dh: str, auth: str) -> bytes:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF

        def unb64(value: str) -> bytes:
            return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

        def hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
            return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)

        ua_public = unb64(p256dh)
        auth_secret = unb64(auth)
        server_key = ec.generate_private_key(ec.SECP256R1())
        as_public = server_key.public_key().public_bytes(serialization.Encoding.X962,
                                                         serialization.PublicFormat.UncompressedPoint)
        shared = server_key.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public))
        ikm = hkdf(auth_secret, shared, b"WebPush: info\x00" + ua_public + as_public, 32)
        salt = os.urandom(16)
        cek = hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
        nonce = hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
        ciphertext = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
        return salt + (4096).to_bytes(4, "big") + bytes([len(as_public)]) + as_public + ciphertext

    def send(self, user_id: str, title: str, body: str, url: str = "/") -> int:
        """Blocking; call in a thread. Returns how many devices accepted the notification."""
        import httpx

        with closing(sqlite3.connect(self.path)) as db:
            rows = db.execute("SELECT endpoint,data FROM subscriptions WHERE user_id=?", (user_id,)).fetchall()
        delivered, dead = 0, []
        payload = json.dumps({"title": title, "body": body[:240], "url": url}).encode()
        for endpoint, data in rows:
            try:
                keys = json.loads(data)["keys"]
                response = httpx.post(endpoint, content=self.encrypt(payload, keys["p256dh"], keys["auth"]), timeout=10,
                                      headers={"Content-Encoding": "aes128gcm", "TTL": "86400", "Urgency": "high",
                                               "Authorization": self._vapid_header(endpoint)})
                if response.status_code in {404, 410}:
                    dead.append(endpoint)
                elif response.status_code < 300:
                    delivered += 1
                else:
                    logger.info("Push delivery failed (%s)", response.status_code)
            except Exception as exc:
                logger.info("Push delivery failed (%s)", type(exc).__name__)
        if dead:
            with closing(sqlite3.connect(self.path)) as db, db:
                db.executemany("DELETE FROM subscriptions WHERE endpoint=?", [(item,) for item in dead])
        return delivered
