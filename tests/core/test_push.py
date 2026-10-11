"""Web Push crypto: decrypt as a browser would (RFC 8291) and verify the VAPID token (RFC 8292)."""
from __future__ import annotations

import base64
import json
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from atulya.push import PushService


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def test_payload_decrypts_like_a_browser_and_vapid_signature_verifies(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("ATULYA_VAPID_PRIVATE_KEY", raising=False)
    service = PushService(tmp_path)
    browser = ec.generate_private_key(ec.SECP256R1())
    ua_public = browser.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    auth = os.urandom(16)

    body = service.encrypt(b'{"title":"hi"}', b64(ua_public), b64(auth))
    salt, keylen = body[:16], body[20]
    as_public, ciphertext = body[21:21 + keylen], body[21 + keylen:]
    shared = browser.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public))

    def hkdf(s, ikm, info, n):
        return HKDF(algorithm=hashes.SHA256(), length=n, salt=s, info=info).derive(ikm)
    ikm = hkdf(auth, shared, b"WebPush: info\x00" + ua_public + as_public, 32)
    plain = AESGCM(hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)).decrypt(
        hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12), ciphertext, None)
    assert plain == b'{"title":"hi"}\x02'

    header = service._vapid_header("https://fcm.googleapis.com/fcm/send/abc")
    token = header.split("t=")[1].split(",")[0]
    head, claims, signature = token.split(".")
    assert json.loads(unb64(claims))["aud"] == "https://fcm.googleapis.com"
    raw = unb64(signature)
    public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), unb64(service.public_key))
    public.verify(encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")),
                  f"{head}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))
