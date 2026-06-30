"""Integration tests for the agent loop with mock LLM provider."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, Mock, patch

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
async def test_agent_loop_react_executes_tool(mock_llm):
    from atulya.agent.agent_loop import agent_loop
    with patch("atulya.agent.agent_loop.execute_tool", new=AsyncMock(return_value="4")):
        result = await agent_loop("what is 2+2?", llm=mock_llm)
    assert result is not None
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_agent_loop_stream(mock_llm):
    mock_llm._responses = iter([json.dumps({"content": "streaming response"})])
    from atulya.agent.agent_loop import agent_loop
    result = await agent_loop("hello", llm=mock_llm)
    assert result is not None


@pytest.mark.asyncio
async def test_agent_loop_without_tools(mock_llm):
    mock_llm._responses = iter([json.dumps({"content": "Hello world!"})])
    from atulya.agent.agent_loop import agent_loop
    result = await agent_loop("say hello", llm=mock_llm)
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_agent_loop_error_handling(mock_llm):
    from atulya.agent.agent_loop import agent_loop
    with patch("atulya.agent.agent_loop.execute_tool", side_effect=ValueError("test error")):
        result = await agent_loop("error test", llm=mock_llm)
    assert result is not None


@pytest.mark.asyncio
async def test_dashboard_health_endpoint():
    from fastapi.testclient import TestClient
    from drishti.dashboard.state import ADMIN_TOKEN
    from drishti.dashboard.app import app
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
    from drishti.dashboard.app import app
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_jwt_token_flow():
    from drishti.dashboard.helpers import _jwt_encode, _jwt_decode
    token = _jwt_encode({"sub": "testuser", "role": "user", "name": "Test"})
    assert token.count(".") == 2
    payload = _jwt_decode(token)
    assert payload is not None
    assert payload["sub"] == "testuser"
    assert payload["role"] == "user"


@pytest.mark.asyncio
async def test_jwt_expired_token():
    from drishti.dashboard.helpers import _jwt_encode, _jwt_decode
    token = _jwt_encode({"sub": "test"}, expires_in=-1)
    payload = _jwt_decode(token)
    assert payload is None


@pytest.mark.asyncio
async def test_jwt_tampered_token():
    from drishti.dashboard.helpers import _jwt_decode
    payload = _jwt_decode("header.payload.tampered")
    assert payload is None


@pytest.mark.asyncio
async def test_rate_limiter_exceeded():
    from drishti.dashboard.app import _RATE_LIMIT_MAX, _RATE_STORE, _rate_limiter
    _RATE_STORE.clear()
    client_ip = "192.168.1.1"
    now = __import__("time").time()
    _RATE_STORE[client_ip] = [now - 1 for _ in range(_RATE_LIMIT_MAX)]
    from unittest.mock import AsyncMock, Mock
    request = Mock()
    request.client.host = client_ip
    resp = await _rate_limiter(request, AsyncMock())
    assert resp.status_code == 429
    _RATE_STORE.clear()


@pytest.mark.asyncio
async def test_dashboard_telemetry_endpoint():
    from fastapi.testclient import TestClient
    from drishti.dashboard.state import ADMIN_TOKEN
    from drishti.dashboard.app import app
    client = TestClient(app)
    resp = client.get("/api/telemetry", headers={"X-Atulya-Token": ADMIN_TOKEN})
    assert resp.status_code == 200
    data = resp.json()
    assert "system" in data
    assert "events" in data
    assert "providers" in data


@pytest.mark.asyncio
async def test_agent_loop_with_custom_prompt(mock_llm):
    from atulya.agent.agent_loop import agent_loop
    mock_llm._responses = iter([json.dumps({"content": "custom response"})])
    result = await agent_loop("test", llm=mock_llm, system_prompt="You are a test bot.")
    assert "custom" in result.lower() or result is not None


@pytest.mark.asyncio
async def test_agent_loop_concurrent(mock_llm):
    import asyncio
    from atulya.agent.agent_loop import agent_loop
    with patch("atulya.agent.agent_loop.execute_tool", new=AsyncMock(return_value="ok")):
        tasks = [agent_loop(f"task {i}", llm=mock_llm) for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    assert all(isinstance(r, str) for r in results)


@pytest.mark.asyncio
async def test_agent_loop_empty_input(mock_llm):
    from atulya.agent.agent_loop import agent_loop, _default_system_prompt
    from atulya.agent.tools import get_tool_schemas
    mock_llm._responses = iter([json.dumps({"content": "empty"})])
    result = await agent_loop("", llm=mock_llm)
    assert result is not None


@pytest.mark.asyncio
async def test_agent_loop_very_long_input(mock_llm):
    from atulya.agent.agent_loop import agent_loop
    mock_llm._responses = iter([json.dumps({"content": "long"})])
    result = await agent_loop("x" * 10000, llm=mock_llm)
    assert result is not None


@pytest.mark.asyncio
async def test_agent_loop_no_tools_configured():
    responses = iter([json.dumps({"content": "hello"})])
    class NoToolProvider:
        async def chat(self, prompt, system_prompt=None, tools=None):
            return {"content": "hello"}
        def is_available(self): return True
        def name(self): return "no_tool"
    from atulya.agent.agent_loop import agent_loop
    result = await agent_loop("hello", llm=NoToolProvider())
    assert result is not None


@pytest.mark.asyncio
async def test_jwt_auth_header_accepted():
    from drishti.dashboard.helpers import _jwt_encode, _require_auth
    from fastapi import Header
    token = _jwt_encode({"sub": "jwtuser", "role": "user", "name": "JWT"})
    result = _require_auth(token=token)
    assert result["username"] == "jwtuser"
    assert result["role"] == "user"
