"""Integration tests for the agent loop with mock LLM provider."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, Mock

import pytest


class MockProvider:
    def __init__(self):
        self._available = True
        self._responses = iter([
            json.dumps({"tool_calls": [{"function": {"name": "calculate", "arguments": {"expression": "2+2"}}}]}),
        ])

    def is_available(self) -> bool:
        return self._available

    def name(self) -> str:
        return "mock"

    async def chat(self, prompt: str, system_prompt: str | None = None, tools: list | None = None) -> dict:
        try:
            raw = next(self._responses)
        except StopIteration:
            raw = json.dumps({"content": "done"})
        return json.loads(raw)


@pytest.fixture
def mock_llm():
    return MockProvider()


@pytest.mark.asyncio
async def test_dashboard_health_endpoint():
    from fastapi.testclient import TestClient

    from atulya.dwar import ADMIN_TOKEN
    from atulya.sevak import app
    client = TestClient(app)
    resp = client.get("/api/health", headers={"X-Atulya-Token": ADMIN_TOKEN})
    assert resp.status_code == 200
    data = resp.json()
    assert "ok" in data
    assert "healthy" in data
    assert "warnings" in data


@pytest.mark.asyncio
async def test_dashboard_health_no_auth():
    from fastapi.testclient import TestClient

    from atulya.sevak import app
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_jwt_token_flow():
    from atulya.dwar import _jwt_decode, _jwt_encode
    token = _jwt_encode({"sub": "testuser", "role": "user", "name": "Test"})
    assert token.count(".") == 2
    payload = _jwt_decode(token)
    assert payload is not None
    assert payload["sub"] == "testuser"
    assert payload["role"] == "user"


@pytest.mark.asyncio
async def test_jwt_expired_token():
    from atulya.dwar import _jwt_decode, _jwt_encode
    token = _jwt_encode({"sub": "test"}, expires_in=-1)
    payload = _jwt_decode(token)
    assert payload is None


@pytest.mark.asyncio
async def test_jwt_tampered_token():
    from atulya.dwar import _jwt_decode
    payload = _jwt_decode("header.payload.tampered")
    assert payload is None


@pytest.mark.asyncio
async def test_rate_limiter_exceeded():
    from atulya.sevak import _RATE_LIMIT_MAX, _RATE_STORE, _rate_limiter
    _RATE_STORE.clear()
    client_ip = "192.168.1.1"
    now = __import__("time").time()
    _RATE_STORE[client_ip] = [now - 1 for _ in range(_RATE_LIMIT_MAX)]
    request = Mock()
    request.client.host = client_ip
    resp = await _rate_limiter(request, AsyncMock())
    assert resp.status_code == 429
    _RATE_STORE.clear()


@pytest.mark.asyncio
async def test_rate_limiter_expires_idle_clients_and_bounds_store(monkeypatch):
    import atulya.sevak as server

    server._RATE_STORE.clear()
    monkeypatch.setattr(server, "_RATE_STORE_MAX_CLIENTS", 1)
    server._RATE_STORE["stale"] = [server.time.time() - server._RATE_LIMIT_WINDOW - 1]
    request = Mock()
    request.client.host = "fresh"
    downstream = AsyncMock(return_value=object())

    result = await server._rate_limiter(request, downstream)

    assert result is downstream.return_value
    assert list(server._RATE_STORE) == ["fresh"]
    request.client.host = "another-client"
    rejected = await server._rate_limiter(request, downstream)
    assert rejected.status_code == 429
    assert list(server._RATE_STORE) == ["fresh"]
    server._RATE_STORE.clear()


@pytest.mark.asyncio
async def test_shutdown_cancels_and_awaits_background_task():
    import asyncio

    from atulya.sevak import _cancel_task

    cleaned_up = asyncio.Event()

    async def background_task():
        try:
            await asyncio.Future()
        finally:
            cleaned_up.set()

    task = asyncio.create_task(background_task())
    await asyncio.sleep(0)
    await _cancel_task(task)

    assert task.cancelled()
    assert cleaned_up.is_set()


def test_server_includes_each_api_route_once():
    from collections import Counter

    from fastapi.routing import APIRoute

    from atulya.sevak import app

    counts = Counter(
        (route.path, tuple(sorted(route.methods or ())))
        for route in app.routes
        if isinstance(route, APIRoute)
    )
    assert all(count == 1 for count in counts.values())
    assert counts[("/api/auth/login", ("POST",))] == 1


@pytest.mark.asyncio
async def test_dashboard_telemetry_endpoint():
    from fastapi.testclient import TestClient

    from atulya.dwar import ADMIN_TOKEN
    from atulya.sevak import app
    client = TestClient(app)
    resp = client.get("/api/telemetry", headers={"X-Atulya-Token": ADMIN_TOKEN})
    assert resp.status_code == 200
    data = resp.json()
    assert "system" in data
    assert "events" in data
    assert "providers" in data


@pytest.mark.asyncio
async def test_jwt_auth_header_accepted():
    from atulya.dwar import _jwt_encode, _require_auth
    token = _jwt_encode({"sub": "jwtuser", "role": "user", "name": "JWT"})
    result = _require_auth(token=token)
    assert result["username"] == "jwtuser"
    assert result["role"] == "user"
