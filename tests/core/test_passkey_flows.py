"""Full passkey ceremonies against the real server code with a software authenticator.

The authenticator builds exactly what a phone's passkey provider returns (P-256 key, "none" attestation,
signed assertions), so these runs prove registration and sign-in work for the website origin over HTTPS and
for passkeys made inside the Android app (which report the app's signing key as their origin).
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path

import cbor2
import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from atulya.auth import SESSION_COOKIE
from atulya.server import create_app
from atulya.settings import Settings

SITE = "https://atulya.atulvij.com"
RP_ID = "atulya.atulvij.com"
SETUP_TOKEN = "a-long-one-time-test-token-for-passkeys"


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def unb64url(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def android_app_origin() -> str:
    links = json.loads((Path(__file__).resolve().parents[2] / "webui" / ".well-known" / "assetlinks.json").read_text())
    fingerprint = links[0]["target"]["sha256_cert_fingerprints"][0]
    return "android:apk-key-hash:" + b64url(bytes.fromhex(fingerprint.replace(":", "")))


class SoftPasskey:
    """One passkey on a pretend phone."""

    def __init__(self) -> None:
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(32)
        self.count = 0

    def _client_data(self, kind: str, challenge: str, origin: str) -> bytes:
        return json.dumps({"type": kind, "challenge": challenge, "origin": origin, "crossOrigin": False}).encode()

    def create(self, options: dict, origin: str) -> dict:
        numbers = self.key.public_key().public_numbers()
        cose = cbor2.dumps({1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, "big"), -3: numbers.y.to_bytes(32, "big")})
        auth_data = (hashlib.sha256(options["rp"]["id"].encode()).digest() + bytes([0x45]) + (0).to_bytes(4, "big")
                     + bytes(16) + len(self.credential_id).to_bytes(2, "big") + self.credential_id + cose)
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        client_data = self._client_data("webauthn.create", options["challenge"], origin)
        return {"id": b64url(self.credential_id), "rawId": b64url(self.credential_id), "type": "public-key",
                "response": {"clientDataJSON": b64url(client_data), "attestationObject": b64url(attestation),
                             "transports": ["internal", "hybrid"]}}

    def get(self, options: dict, origin: str) -> dict:
        self.count += 1
        auth_data = hashlib.sha256(options["rpId"].encode()).digest() + bytes([0x05]) + self.count.to_bytes(4, "big")
        client_data = self._client_data("webauthn.get", options["challenge"], origin)
        signature = self.key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        return {"id": b64url(self.credential_id), "rawId": b64url(self.credential_id), "type": "public-key",
                "response": {"clientDataJSON": b64url(client_data), "authenticatorData": b64url(auth_data),
                             "signature": b64url(signature), "userHandle": b64url(b"admin")}}


def make_app(data_dir: Path):
    return create_app(Settings(
        assistant_name="Atulya", host="127.0.0.1", port=8501,
        data_dir=data_dir, models_dir=data_dir / "models",
        model_provider="", model_name="", model_base_url="", model_api_key="",
        public_origin=SITE, admin_setup_token=SETUP_TOKEN,
    ))


async def register(client: httpx.AsyncClient, passkey: SoftPasskey, origin: str, headers: dict | None = None):
    options = await client.post("/api/auth/register/options", headers=headers or {})
    assert options.status_code == 200, options.text
    body = options.json()
    return await client.post("/api/auth/register/verify", headers=headers or {}, json={
        "flow_id": body["flow_id"], "credential": passkey.create(body["options"], origin)})


async def sign_in(client: httpx.AsyncClient, passkey: SoftPasskey, origin: str):
    options = await client.post("/api/auth/login/options")
    assert options.status_code == 200, options.text
    body = options.json()
    return await client.post("/api/auth/login/verify", json={
        "flow_id": body["flow_id"], "credential": passkey.get(body["options"], origin)})


def test_passkeys_work_on_the_https_site_and_inside_the_android_app(project_temp_dir: Path) -> None:
    app = make_app(project_temp_dir / "data")
    website_key, app_key = SoftPasskey(), SoftPasskey()

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=SITE) as client:
            # first administrator passkey, created on the website
            created = await register(client, website_key, SITE, {"X-Atulya-Setup-Token": SETUP_TOKEN})
            assert created.status_code == 200, created.text
            assert client.cookies.get(SESSION_COOKIE)

            # signed in: add a second passkey from inside the Android app (origin = app signing key)
            added = await register(client, app_key, android_app_origin())
            assert added.status_code == 200, added.text

        for passkey, origin in ((website_key, SITE), (app_key, android_app_origin())):
            async with httpx.AsyncClient(transport=transport, base_url=SITE) as fresh:
                signed_in = await sign_in(fresh, passkey, origin)
                assert signed_in.status_code == 200, (origin, signed_in.text)
                assert fresh.cookies.get(SESSION_COOKIE)
                profile = await fresh.get("/api/profile")
                assert profile.status_code == 200

    asyncio.run(exercise())


def test_passkeys_from_other_sites_or_apps_are_rejected(project_temp_dir: Path) -> None:
    app = make_app(project_temp_dir / "data")
    passkey = SoftPasskey()

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=SITE) as client:
            phishing = await register(client, passkey, "https://atulya-login.example.com",
                                      {"X-Atulya-Setup-Token": SETUP_TOKEN})
            assert phishing.status_code == 400
            other_app = await register(client, passkey, "android:apk-key-hash:" + b64url(os.urandom(32)),
                                       {"X-Atulya-Setup-Token": SETUP_TOKEN})
            assert other_app.status_code == 400
            assert (await register(client, passkey, SITE, {"X-Atulya-Setup-Token": SETUP_TOKEN})).status_code == 200
        async with httpx.AsyncClient(transport=transport, base_url=SITE) as fresh:
            stolen = await sign_in(fresh, passkey, "https://atulya-login.example.com")
            assert stolen.status_code == 401
            assert not fresh.cookies.get(SESSION_COOKIE)

    asyncio.run(exercise())
