"""FastAPI dashboard app."""

from __future__ import annotations

import logging
import asyncio
import json
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from drishti.dashboard.helpers import _checkpoint_index, _load_cached_model
from drishti.dashboard.routes import auth, automation, chat, cortex, model, openai, system, train, voice
from drishti.dashboard.automation_runner import AutomationRunner
from yantra.mcp.external_client import MCPClientManager

logger = logging.getLogger(__name__)


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

    app.state.llm = get_default_llm()
    app.state.mcp_manager = MCPClientManager()
    app.state.mcp_errors = []
    await _connect_mcp_servers(app)
    app.state.automation_runner = AutomationRunner(automation.JOBS_FILE, app.state.llm)
    app.state.automation_task = asyncio.create_task(app.state.automation_runner.start())
    threading.Thread(target=_warm_latest_model, daemon=True).start()
    try:
        yield
    finally:
        await app.state.automation_runner.stop()
        app.state.automation_task.cancel()
        await app.state.mcp_manager.shutdown_all()


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

for module in (auth, system, model, train, chat, cortex, automation, openai, voice):
    app.include_router(module.router)


dist = Path(__file__).resolve().parents[1] / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="drishti")


