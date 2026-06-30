"""Performance benchmarks for agent loop latency."""
from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = [pytest.mark.benchmark, pytest.mark.skipif("not config.getoption('--benchmark')")]


@pytest.fixture(scope="module")
def mock_provider():
    class Provider:
        async def chat(self, prompt, system_prompt=None, tools=None):
            return {"content": "Hello!"}

        def is_available(self):
            return True

        def name(self):
            return "benchmark"

    return Provider()


@pytest.mark.asyncio
async def test_agent_loop_latency(mock_provider):
    from atulya.agent.agent_loop import AgentLoop

    loop = AgentLoop(llm_provider=mock_provider, max_steps=3)
    n = 10
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        await loop.run("hello", tool_choice="none")
        times.append(time.perf_counter() - t0)
    avg = sum(times) / n
    print(f"\n  AgentLoop avg latency (n={n}): {avg*1000:.1f}ms")
    assert avg < 5.0, f"Avg latency {avg*1000:.1f}ms exceeds 5s threshold"


@pytest.mark.asyncio
async def test_tool_execution_latency():
    from atulya.agent.tools import calculate

    n = 100
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        await calculate(expression="2+2")
        times.append(time.perf_counter() - t0)
    avg = sum(times) / n
    print(f"\n  calculate avg latency (n={n}): {avg*1000:.3f}ms")
    assert avg < 1.0, f"Avg latency {avg*1000:.3f}ms exceeds 1s"


@pytest.mark.asyncio
async def test_mcp_http_latency():
    from yantra.mcp.external_client import MCPClientManager

    mgr = MCPClientManager()
    t0 = time.perf_counter()
    try:
        await mgr.add_http("test", "http://localhost:9999", timeout=1.0)
    except Exception:
        pass
    elapsed = time.perf_counter() - t0
    print(f"\n  MCP HTTP connection attempt: {elapsed*1000:.1f}ms")
    await mgr.shutdown_all()
    assert elapsed < 10.0, f"MCP HTTP took {elapsed*1000:.1f}ms (expected <10s)"


@pytest.mark.asyncio
async def test_jwt_encode_decode_latency():
    from drishti.dashboard.helpers import _jwt_encode, _jwt_decode

    n = 500
    encode_times = []
    decode_times = []
    for _ in range(n):
        t0 = time.perf_counter()
        token = _jwt_encode({"sub": "bench", "role": "user"})
        encode_times.append(time.perf_counter() - t0)
        t0 = time.perf_counter()
        _jwt_decode(token)
        decode_times.append(time.perf_counter() - t0)
    avg_encode = sum(encode_times) / n
    avg_decode = sum(decode_times) / n
    print(f"\n  JWT encode avg (n={n}): {avg_encode*1000:.3f}ms")
    print(f"  JWT decode avg (n={n}): {avg_decode*1000:.3f}ms")
    assert avg_encode < 0.05, f"JWT encode avg {avg_encode*1000:.3f}ms exceeds 50us"
    assert avg_decode < 0.05, f"JWT decode avg {avg_decode*1000:.3f}ms exceeds 50us"


@pytest.mark.asyncio
async def test_rate_limiter_overhead():
    from drishti.dashboard.app import _RATE_LIMIT_MAX, _RATE_STORE, _rate_limiter
    from unittest.mock import AsyncMock, Mock

    _RATE_STORE.clear()
    request = Mock()
    request.client.host = "10.0.0.1"

    n = 100
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        resp = await _rate_limiter(request, AsyncMock())
        times.append(time.perf_counter() - t0)
    avg = sum(times) / n
    print(f"\n  Rate limiter avg (n={n}): {avg*1000:.3f}ms")
    assert avg < 0.01, f"Rate limiter avg {avg*1000:.3f}ms exceeds 10us"
    assert resp is not None
    _RATE_STORE.clear()
