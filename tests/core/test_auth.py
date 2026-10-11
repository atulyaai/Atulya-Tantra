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
                "setup_required": True, "setup_token_required": False, "setup_token_configured": False, "password_login": False,
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


def test_password_login_is_hashed_rate_limited_and_closes_first_setup(project_temp_dir: Path) -> None:
    store = AuthStore(project_temp_dir)
    assert store.credential_count() == 0
    store.set_password("admin", "a-long-test-password")
    assert store.credential_count() == 1  # first-time passkey setup is no longer open
    with closing(sqlite3.connect(project_temp_dir / "auth.sqlite3")) as db:
        raw = db.execute("SELECT hash FROM passwords").fetchone()[0]
    assert b"a-long-test-password" not in bytes(raw)
    assert store.check_password("admin", "a-long-test-password", "c1") == "ok"
    for _ in range(5):
        assert store.check_password("admin", "wrong", "c2") == "bad"
    assert store.check_password("admin", "a-long-test-password", "c2") == "locked"
    assert store.check_password("admin", "a-long-test-password", "c1") == "ok"


def test_password_guessing_from_many_clients_locks_the_account(project_temp_dir: Path) -> None:
    store = AuthStore(project_temp_dir)
    store.set_password("admin", "a-long-test-password")
    for attempt in range(20):
        assert store.check_password("admin", "wrong", f"ip{attempt}") == "bad"
    assert store.check_password("admin", "a-long-test-password", "fresh-ip") == "locked"


def test_secrets_are_encrypted_and_reloaded(project_temp_dir: Path, monkeypatch) -> None:
    from atulya.secrets_store import load_protected, protect, secrets_path

    env = project_temp_dir / ".env"
    env.write_text("ATULYA_PORT=8501\nOPENROUTER_API_KEY=sk-or-test-1234567890\n", encoding="utf-8")
    assert protect(env, project_temp_dir) == ["OPENROUTER_API_KEY"]
    assert "sk-or-test" not in env.read_text(encoding="utf-8")
    assert b"sk-or-test" not in secrets_path(project_temp_dir).read_bytes()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert load_protected(project_temp_dir) == 1
    import os
    assert os.environ["OPENROUTER_API_KEY"] == "sk-or-test-1234567890"


def test_login_by_code_is_single_use_limited_and_approvable(project_temp_dir: Path) -> None:
    from atulya.server import spoken_digits

    store = AuthStore(project_temp_dir)
    store.set_password("admin", "a-long-test-password")
    request_id, code = store.create_login_request("admin", "1.2.3.4", "phone")
    assert store.redeem_login(request_id, None) is None  # still pending
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert store.redeem_login(request_id, wrong) is None
    assert store.redeem_login(request_id, code) is None  # locked after 5 wrong tries

    request_id, code = store.create_login_request("admin", "5.6.7.8", "laptop")
    assert store.redeem_login(request_id, code) == "admin"
    assert store.redeem_login(request_id, code) is None  # single use

    request_id, _ = store.create_login_request("admin", "9.9.9.9", "tablet")
    assert not store.decide_login(request_id, "someone-else", True)
    assert store.decide_login(request_id, "admin", True)
    assert store.redeem_login(request_id, None) == "admin"
    assert store.create_login_request("ghost", "1.1.1.1", "x") is None
    assert spoken_digits("four seven 2, nau एक 0") == "472910"


def test_signup_waits_for_owner_approval(project_temp_dir: Path) -> None:
    import pytest

    store = AuthStore(project_temp_dir)
    with pytest.raises(ValueError, match="10 characters"):
        store.create_signup("Ravi", "ravi@example.com", "short", "password")
    with pytest.raises(ValueError, match="three"):
        store.create_signup("Ravi", "ravi@example.com", "alllowercaseletters", "password")
    user_id = store.create_signup("Ravi", "Ravi@Example.com", "Str0ng-Passphrase", "password")
    assert store.resolve_login("ravi@example.com") == user_id
    assert store.check_password(user_id, "Str0ng-Passphrase", "c") == "bad"   # pending: cannot sign in
    with pytest.raises(ValueError, match="already"):
        store.create_signup("Ravi 2", "ravi@example.com", "Str0ng-Passphrase", "password")
    assert [row["email"] for row in store.pending_signups()] == ["ravi@example.com"]
    assert store.decide_signup(user_id, True)
    assert store.check_password(user_id, "Str0ng-Passphrase", "c2") == "ok"
    assert store.pending_signups() == []


def test_successful_sign_in_forgives_strikes_but_not_active_bans(project_temp_dir: Path) -> None:
    store = AuthStore(project_temp_dir)
    for _ in range(8):
        store.strike_ip("1.2.3.4")
    store.clear_ip("1.2.3.4")
    assert not any(store.strike_ip("1.2.3.4") for _ in range(9))   # counter restarted
    for _ in range(10):
        store.strike_ip("5.6.7.8")
    store.clear_ip("5.6.7.8")
    assert store.ip_banned("5.6.7.8")                             # an active ban is not lifted by this
