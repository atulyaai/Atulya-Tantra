"""FastAPI dashboard app."""

from __future__ import annotations

import logging
import asyncio
import json
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from drishti.dashboard.helpers import _checkpoint_index, _load_cached_model
from drishti.dashboard.routes import agent, auth, automation, chat, cortex, create, devices, model, notifications, openai, system, train, upload, voice, ws
from drishti.dashboard.automation_runner import AutomationRunner
from yantra.mcp.external_client import MCPClientManager

logger = logging.getLogger(__name__)

# ── Rate Limiting ─────────────────────────────────────────────────────────

_RATE_LIMIT_WINDOW = 60
_RATE_LIMIT_MAX = 100
_RATE_STORE: dict[str, list[float]] = {}


async def _rate_limiter(request: Request, call_next):
    client = request.client.host if request.client else "unknown"
    now = time.time()
    window_start = now - _RATE_LIMIT_WINDOW
    hits = [t for t in _RATE_STORE.get(client, []) if t > window_start]
    if len(hits) >= _RATE_LIMIT_MAX:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again later."})
    hits.append(now)
    _RATE_STORE[client] = hits
    return await call_next(request)


# ── Lifespan ──────────────────────────────────────────────────────────────


def _warm_latest_model() -> None:
    try:
        path = _checkpoint_index().get("latest")
        if path:
            _load_cached_model(path)
    except Exception as exc:
        logger.warning("Dashboard model warmup skipped: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from atulya.llm import get_default_llm
    from atulya.agent import AgentCore
    from drishti.dashboard.routes.agent import set_agent

    app.state.llm = get_default_llm()
    app.state.mcp_manager = MCPClientManager()
    app.state.mcp_errors = []
    await _connect_mcp_servers(app)
    app.state.automation_runner = AutomationRunner(automation.JOBS_FILE, app.state.llm)
    app.state.automation_task = asyncio.create_task(app.state.automation_runner.start())

    # Initialize Atulya Agent
    agent_core = AgentCore(llm_provider=app.state.llm)
    set_agent(agent_core)
    app.state.agent = agent_core

    threading.Thread(target=_warm_latest_model, daemon=True).start()
    try:
        yield
    finally:
        await app.state.automation_runner.stop()
        app.state.automation_task.cancel()
        await app.state.mcp_manager.shutdown_all()
        await agent_core.shutdown()


async def _connect_mcp_servers(app: FastAPI) -> None:
    config_path = Path(__file__).resolve().parents[2] / "config" / "mcp_servers.json"
    if not config_path.exists():
        return
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        app.state.mcp_errors.append(f"mcp config read failed: {exc}")
        return
    for server in payload.get("servers", []):
        if not server.get("enabled"):
            continue
        try:
            name = str(server["name"])
            transport = str(server.get("transport") or "stdio")
            timeout = float(server.get("timeout") or 5.0)
            if transport == "http":
                await app.state.mcp_manager.add_http(name, str(server["url"]), timeout=timeout)
            else:
                await app.state.mcp_manager.add_stdio(
                    name,
                    str(server["command"]),
                    args=list(server.get("args") or []),
                    env=dict(server.get("env") or {}),
                    timeout=timeout,
                )
        except Exception as exc:
            app.state.mcp_errors.append(f"{server.get('name', 'unknown')}: {exc}")


app = FastAPI(title="Atulya Tantra Dashboard", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(_rate_limiter)

for module in (auth, system, model, train, chat, cortex, automation, openai, voice, upload, devices, ws, notifications, agent, create):
    app.include_router(module.router)


dist = Path(__file__).resolve().parents[1] / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="drishti")


