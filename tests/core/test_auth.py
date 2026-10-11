"""Passkey session and first-admin access checks."""
from __future__ import annotations

import asyncio
import sqlite3
from contextlib import closing
from pathlib import Path

import httpx

from atulya.auth import AuthStore, SESSION_COOKIE
from atulya.server import create_app
from atulya.settings import Settings


def test_auth_store_uses_one_time_challenges_and_hashed_sessions(project_temp_dir: Path) -> None:
    store = AuthStore(project_temp_dir)
    store.save_challenge("flow-id-123456789012", b"challenge", "login")
    assert store.consume_challenge("flow-id-123456789012", "login") == (b"challenge", "admin")
    assert store.consume_challenge("flow-id-123456789012", "login") is None

    token = store.create_session()
    assert store.user_for_session(token) == "admin"
    with closing(sqlite3.connect(store.path)) as db, db:
        stored_hash = db.execute("SELECT token_hash FROM sessions").fetchone()[0]
    assert token not in stored_hash
    assert store.user_for_session("invalid") is None
    store.revoke_session(token)
    assert store.user_for_session(token) is None


def test_invites_are_single_use_and_admin_can_revoke_without_orphaning_user_data(project_temp_dir: Path) -> None:
    store = AuthStore(project_temp_dir)
    user_id, invite = store.create_invitation("  Asha   Rao ")
    assert store.invitation(invite)["display_name"] == "Asha Rao"
    assert store.add_credential(b"member-key-1", b"public-1", 0, "[]", user_id=user_id,
                                display_name="Asha Rao", invite_token=invite)
    assert store.invitation(invite) is None
    assert not store.add_credential(b"member-key-2", b"public-2", 0, "[]", user_id=user_id,
                                    display_name="Asha Rao", invite_token=invite)
    assert store.add_credential(b"member-key-2", b"public-2", 0, "[]", user_id=user_id,
                                display_name="Asha Rao")
    session = store.create_session(user_id)
    assert store.user_for_session(session) == user_id
    assert store.revoke_credential(b"member-key-1")
    assert store.user_for_session(session) is None
    session = store.create_session(user_id)
    assert store.disable_user(user_id)
    assert store.user_for_session(session) is None
    assert not store.disable_user(user_id)


def test_private_api_requires_passkey_session_and_first_admin_setup_is_available(project_temp_dir: Path) -> None:
    settings = Settings(
        assistant_name="Atulya", host="127.0.0.1", port=8501,
        data_dir=project_temp_dir / "data", models_dir=project_temp_dir / "models",
        model_provider="", model_name="", model_base_url="", model_api_key="",
    )
    app = create_app(settings)

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            auth = await client.get("/api/auth/status")
            assert auth.status_code == 200
            assert auth.json() == {
                "setup_required": True, "setup_token_required": False, "setup_token_configured": False,
                "authenticated": False, "user": None, "is_admin": False,
            }
            assert (await client.get("/api/plugins")).status_code == 401

            options = await client.post("/api/auth/register/options")
            assert options.status_code == 200
            selection = options.json()["options"]["authenticatorSelection"]
            assert selection["residentKey"] == "required"
            assert selection["userVerification"] == "required"
            assert (await client.post("/api/auth/login/options")).status_code == 409

            token = app.state.auth_store.create_session()
            client.cookies.set(SESSION_COOKIE, token)
            assert (await client.get("/api/plugins")).status_code == 200

        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as ip_client:
            unsupported_ip_rp = await ip_client.post("/api/auth/register/options")
            assert unsupported_ip_rp.status_code == 400
            assert "localhost" in unsupported_ip_rp.json()["detail"]

    asyncio.run(exercise())


def test_admin_can_invite_and_disable_local_users(project_temp_dir: Path) -> None:
    settings = Settings(
        assistant_name="Atulya", host="127.0.0.1", port=8501,
        data_dir=project_temp_dir / "data", models_dir=project_temp_dir / "models",
        model_provider="", model_name="", model_base_url="", model_api_key="",
    )
    app = create_app(settings)
    store = app.state.auth_store
    assert store.add_credential(b"admin-key", b"admin-public", 0, "[]", first_only=True)
    admin_token = store.create_session("admin")

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as admin:
            admin.cookies.set(SESSION_COOKIE, admin_token)
            created = await admin.post("/api/auth/users", json={"display_name": "Asha"})
            assert created.status_code == 201
            invitation = created.json()
            options = await admin.post(
                "/api/auth/register/options",
                headers={"X-Atulya-Invite-Token": invitation["invitation_token"]},
            )
            assert options.status_code == 200
            assert options.json()["options"]["user"]["displayName"] == "Asha"
            user_id = invitation["user_id"]
            assert store.add_credential(
                b"asha-key", b"asha-public", 0, "[]", user_id=user_id, display_name="Asha",
                invite_token=invitation["invitation_token"],
            )
            user = httpx.AsyncClient(transport=transport, base_url="http://localhost")
            async with user:
                user.cookies.set(SESSION_COOKIE, store.create_session(user_id))
                assert (await user.get("/api/auth/users")).status_code == 403
                disabled = await admin.delete(f"/api/auth/users/{user_id}")
                assert disabled.status_code == 200
                assert (await user.get("/api/plugins")).status_code == 401

    asyncio.run(exercise())


def test_passkey_setup_uses_configured_https_public_origin(project_temp_dir: Path) -> None:
    settings = Settings(
        assistant_name="Atulya", host="127.0.0.1", port=8501,
        data_dir=project_temp_dir / "remote-data", models_dir=project_temp_dir / "models",
        model_provider="", model_name="", model_base_url="", model_api_key="",
        public_origin="https://jarvis.example.test",
        admin_setup_token="a-long-one-time-test-token",
    )
    app = create_app(settings)

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://jarvis.example.test") as client:
            denied = await client.post("/api/auth/register/options")
            assert denied.status_code == 403
            options = await client.post(
                "/api/auth/register/options", headers={"X-Atulya-Setup-Token": "a-long-one-time-test-token"}
            )
            assert options.status_code == 200
            assert options.json()["options"]["rp"]["id"] == "jarvis.example.test"
        async with httpx.AsyncClient(transport=transport, base_url="https://other.example.test") as client:
            rejected = await client.post("/api/auth/register/options")
            assert rejected.status_code == 400

    asyncio.run(exercise())



def test_device_links_add_a_passkey_to_the_same_account_once(project_temp_dir: Path) -> None:
    store = AuthStore(project_temp_dir)
    assert store.add_credential(b"first", b"key", 0, "[]", first_only=True)
    token = store.create_device_link("admin")
    assert store.device_link(token)["user_id"] == "admin"
    assert not store.add_credential(b"phone", b"key2", 0, "[]", user_id="u_other", device_token=token)
    assert store.add_credential(b"phone", b"key2", 0, "[]", user_id="admin", device_token=token)
    assert store.device_link(token) is None  # single use
    assert not store.add_credential(b"tablet", b"key3", 0, "[]", user_id="admin", device_token=token)
    assert store.device_link("not-a-real-token-value") is None
