"""Regression tests for the October 2026 security review."""
import asyncio
import sqlite3
from contextlib import closing
from pathlib import Path

import httpx
import pytest

from atulya import server
from atulya.auth import AuthStore
from atulya.push import PushService
from atulya.settings import Settings
from tests.conftest import authenticate_test_admin
from tools import device_companion
from tools.plugins.information import search
from tools.plugins.toolkit import TOOLS


def make_settings(path: Path) -> Settings:
    return Settings(assistant_name="Atulya", host="127.0.0.1", port=8501,
                    data_dir=path / "data", models_dir=path / "models",
                    model_provider="", model_name="", model_base_url="", model_api_key="")


# --- read_url never reaches this server, its network or the cloud metadata service ---------------

@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8501/api/auth/users", "http://localhost/", "http://169.254.169.254/opc/v2/instance/",
    "http://10.0.0.5/", "http://192.168.1.1/", "http://[::1]/", "file:///etc/passwd", "http://user:pw@example.com/",
])
def test_read_url_refuses_internal_addresses(url):
    reply = asyncio.run(search.read_page(url))
    assert reply.startswith("I won't read that address")


def test_read_url_checks_every_redirect_hop(monkeypatch):
    async def public_target(url):
        return (None, "internal and private addresses are never read") if "metadata" in url else ("93.184.216.34", None)

    class Hop:
        is_redirect = True
        headers = {"location": "http://metadata.example/latest"}
        next_request = None

    calls = []

    class Client:
        async def get(self, url, follow_redirects=False, **kwargs):
            calls.append(url)
            assert kwargs["headers"]["Host"] == "public.example"
            assert kwargs["extensions"]["sni_hostname"] == "public.example"
            return Hop()

    monkeypatch.setattr(search, "_public_target", public_target)
    monkeypatch.setattr(search, "_client", lambda: Client())
    reply = asyncio.run(search.read_page("http://public.example/"))
    assert calls == ["http://93.184.216.34/"]  # only the validated public address is contacted
    assert reply.startswith("I won't read that address")


# --- push notifications only go to real browser push services ------------------------------------

def test_push_subscriptions_only_accept_browser_push_services(project_temp_dir):
    service = PushService.__new__(PushService)
    service.path = project_temp_dir / "push.sqlite3"
    with closing(sqlite3.connect(service.path)) as db, db:
        db.execute("CREATE TABLE subscriptions(endpoint TEXT PRIMARY KEY, user_id TEXT, data TEXT, created_at INTEGER)")
    keys = {"keys": {"p256dh": "x", "auth": "y"}}
    service.subscribe("admin", {"endpoint": "https://fcm.googleapis.com/fcm/send/abc", **keys})
    service.subscribe("admin", {"endpoint": "https://jmt17.google.com/fcm/send/abc", **keys})
    for bad in ("https://127.0.0.1:8501/x", "https://169.254.169.254/x", "https://evil.example/google.com",
                "https://fcm.googleapis.com.evil.example/x", "http://fcm.googleapis.com/x"):
        with pytest.raises(ValueError):
            service.subscribe("admin", {"endpoint": bad, **keys})


# --- PC companion: no shell, no hidden files, no folder unless granted ---------------------------

def test_companion_open_app_never_uses_a_shell(monkeypatch):
    from tools.plugins.system import actions

    opened = []
    monkeypatch.setattr(actions, "open_app", lambda name: opened.append(name) or f"Opened {name}.")
    assert device_companion.execute("open_app", "notepad & del C:\\important", None) == "Opened notepad & del C:\\important."
    assert opened == ["notepad & del C:\\important"]  # matched by name against installed apps only


def test_companion_files_stay_inside_the_granted_folder_and_skip_hidden(project_temp_dir):
    granted = project_temp_dir / "shared"
    (granted / ".secret").mkdir(parents=True)
    (granted / ".env").write_text("TOKEN=1")
    (granted / "notes.txt").write_text("hello")
    (granted / ".secret" / "key.txt").write_text("k")
    (project_temp_dir / "outside.txt").write_text("no")
    assert device_companion.execute("list_files", ".", str(granted)) == "notes.txt"
    assert device_companion.execute("read_file", "notes.txt", str(granted)) == "hello"
    for path in (".env", ".secret/key.txt", "../outside.txt"):
        with pytest.raises(ValueError):
            device_companion.execute("read_file", path, str(granted))
    with pytest.raises(ValueError):
        device_companion.execute("list_photos", "", None)  # Pictures is never read without a grant


# --- device and camera actions need the owner's approval ------------------------------------------

def test_device_camera_cast_and_smart_home_tools_require_approval():
    tools = {tool.name: tool for tool in TOOLS}
    for name in ("ask_device", "visual_inspect", "cast_to_tv", "smart_home_control"):
        assert tools[name].confirm, name
    assert not tools["ask_device"].low_risk and not tools["visual_inspect"].low_risk
    assert "photo" in tools["visual_inspect"].describe({"device": "Laptop"})
    assert "send_sms" in tools["ask_device"].describe({"device": "Phone", "command": "send_sms", "detail": "{}"})


# --- signed-in devices, sign out everywhere, alerts only for new sign-ins -------------------------

def test_sessions_record_device_and_can_be_signed_out(project_temp_dir):
    store = AuthStore(project_temp_dir)
    phone = store.create_session("admin")
    laptop = store.create_session("admin")
    assert store.describe_session(phone, "Android phone (1.2.3.4)", "1.2.3.4", "passkey") == ("admin", True)
    assert store.describe_session(laptop, "Windows PC (5.6.7.8)", "5.6.7.8", "password") == ("admin", True)
    again = store.create_session("admin")
    assert store.describe_session(again, "Android phone (1.2.3.4)", "1.2.3.4", "passkey") == ("admin", False)

    listed = store.sessions_for("admin", phone)
    assert len(listed) == 3 and sum(item["current"] for item in listed) == 1
    assert {item["method"] for item in listed} == {"passkey", "password"}
    assert all(len(item["id"]) == 16 and phone not in str(item) for item in listed)  # token never exposed

    laptop_id = next(item["id"] for item in listed if item["method"] == "password")
    assert not store.revoke_session_id("someone-else", laptop_id)
    assert store.revoke_session_id("admin", laptop_id) and store.user_for_session(laptop) is None
    assert store.revoke_other_sessions("admin", phone) == 1
    assert store.user_for_session(phone) == "admin" and store.user_for_session(again) is None


def _client(app):
    # No lifespan: background services (Telegram polling, backups, model warm-up) stay off in tests.
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("203.0.113.9", 4000)),
                             base_url="http://localhost")


def test_session_api_and_security_headers(project_temp_dir):
    app = server.create_app(make_settings(project_temp_dir))

    async def run():
        async with _client(app) as client:
            assert (await client.get("/api/auth/sessions")).status_code == 401
            authenticate_test_admin(client, app)
            other = app.state.auth_store.create_session("admin")
            response = await client.get("/api/auth/sessions")
            assert response.status_code == 200 and len(response.json()["sessions"]) == 2
            for header in ("x-content-type-options", "referrer-policy", "content-security-policy", "permissions-policy"):
                assert header in response.headers
            assert "frame-ancestors 'self' https://web.telegram.org" in response.headers["content-security-policy"]
            assert (await client.post("/api/auth/sessions/sign-out-others")).json() == {"signed_out": 1}
            assert app.state.auth_store.user_for_session(other) is None
            assert (await client.get("/api/auth/sessions")).status_code == 200  # this device stays signed in

    asyncio.run(run())


def test_asking_for_a_sign_in_code_is_not_a_failed_attempt(project_temp_dir):
    app = server.create_app(make_settings(project_temp_dir))
    store = app.state.auth_store
    store.ensure_user("admin", "Admin", "admin")

    def strikes():
        with closing(sqlite3.connect(store.path)) as db:
            row = db.execute("SELECT COALESCE(SUM(strikes), 0) FROM ip_strikes").fetchone()
        return row[0]

    async def run():
        async with _client(app) as client:
            assert (await client.post("/api/auth/login-requests", json={"username": "admin"})).status_code == 200
            assert strikes() == 0  # asking for a code is normal use, never a failed attempt
            # Tapping again within 30 seconds hits the cooldown (that one counts).
            assert (await client.post("/api/auth/login-requests", json={"username": "admin"})).status_code == 429
            assert strikes() == 1

    asyncio.run(run())
