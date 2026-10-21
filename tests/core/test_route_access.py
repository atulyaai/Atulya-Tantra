"""PLAN M12-1/M12-3: every route is classified; a normal user gets 403 on every admin route (before the
handler runs) and 404 on another account's devices; anonymous callers get 401."""
import asyncio
import re
from pathlib import Path

import httpx
import pytest

from atulya import server
from atulya.route_access import ROUTE_ACCESS, is_admin_route
from atulya.settings import Settings
from tools.plugins.system.agents import AgentHub


def _app(tmp: Path):
    settings = Settings(assistant_name="Atulya", host="127.0.0.1", port=8501, data_dir=tmp / "data",
                        models_dir=tmp / "models", model_provider="", model_name="", model_base_url="",
                        model_api_key="")
    return server.create_app(settings), settings.data_dir


def _routes(app):
    for route in app.routes:
        for method in sorted(getattr(route, "methods", None) or ()):
            if method != "HEAD":
                yield method, route.path


def test_every_route_is_classified(project_temp_dir):
    app, _ = _app(project_temp_dir)
    routes = set(_routes(app))
    assert routes, "no routes found"
    missing = sorted(routes - set(ROUTE_ACCESS))
    assert not missing, f"classify these routes in atulya/route_access.py: {missing}"
    stale = sorted(set(ROUTE_ACCESS) - routes)
    assert not stale, f"routes listed but not registered: {stale}"


def _fill(path: str) -> str:
    return re.sub(r"\{[^/]+\}", "x1", path)


def _request(app, method, path, cookie=None):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            if cookie:
                client.cookies.set("atulya_session", cookie)
            return await client.request(method, path, json={})

    return asyncio.run(run())


ADMIN_ROUTES = sorted(key for key, access in ROUTE_ACCESS.items() if access == "admin")


@pytest.fixture(scope="module")
def app_and_sessions(tmp_path_factory):
    app, data_dir = _app(tmp_path_factory.mktemp("routes"))
    store = app.state.auth_store
    return app, data_dir, store.create_session("admin"), store.create_session("bob")


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_route_refuses_user_and_anonymous(app_and_sessions, method, path):
    app, _data, _admin, bob = app_and_sessions
    assert is_admin_route(method, _fill(path))
    assert _request(app, method, _fill(path), bob).status_code == 403
    assert _request(app, method, _fill(path)).status_code == 401


def test_admin_still_reaches_admin_routes(app_and_sessions):
    app, _data, admin, _bob = app_and_sessions
    for method, path in (("GET", "/api/auth/users"), ("GET", "/api/activity"), ("GET", "/api/maintenance")):
        assert _request(app, method, path, admin).status_code not in (401, 403), path


def test_user_routes_are_not_blocked_for_users(app_and_sessions):
    app, _data, _admin, bob = app_and_sessions
    for method, path in (("GET", "/api/profile"), ("GET", "/api/devices"), ("GET", "/api/conversations")):
        assert _request(app, method, path, bob).status_code == 200, path


def test_devices_are_private_to_their_owner(app_and_sessions):
    app, data_dir, admin, bob = app_and_sessions
    hub = AgentHub(data_dir)
    hub.pair("admin", "Owner Laptop", ["ping"])
    hub.pair("bob", "Bob Phone", ["ping"])
    listing = _request(app, "GET", "/api/devices", bob).json()
    assert [d["name"] for d in listing["devices"]] == ["Bob Phone"]
    assert "Bob Phone" not in str(_request(app, "GET", "/api/devices", admin).json())
    assert _request(app, "POST", "/api/devices/Owner Laptop/test", bob).status_code == 404
    assert _request(app, "DELETE", "/api/devices/Owner Laptop", bob).status_code == 404
    assert [d["name"] for d in hub.devices("admin")] == ["Owner Laptop"]  # untouched
    assert hub.jobs("admin") == []
    assert _request(app, "POST", "/api/devices/Bob Phone/test", bob).status_code == 202


def test_voice_loop_pairing_is_admin_only(app_and_sessions):
    app, _data, admin, bob = app_and_sessions

    def pair(cookie, name):
        async def run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
                client.cookies.set("atulya_session", cookie)
                return await client.post("/api/devices/pair", json={"name": name, "abilities": ["voice_loop"]})
        return asyncio.run(run())

    assert pair(bob, "Bob PC").status_code == 403
    assert pair(admin, "Desk PC").status_code == 201
