"""FastAPI dashboard app."""

from __future__ import annotations

import logging
import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from atulya.sevak import api_account, api_agent, api_chat, api_home
from atulya.sevak.automation_runner import AutomationRunner
from atulya.yantra.mcp import MCPClientManager

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


async def _warm_llm(llm) -> None:
    try:
        await llm.warm_up()
    except Exception as exc:
        logger.warning("LLM warmup skipped: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from atulya.buddhi.llm import get_default_llm
    from atulya.yantra.core import AgentCore
    from atulya.sevak.api_agent import set_agent

    app.state.llm = get_default_llm()
    app.state.mcp_manager = MCPClientManager()
    app.state.mcp_errors = []
    await _connect_mcp_servers(app)
    api_agent._seed_default_jobs()
    app.state.automation_runner = AutomationRunner(api_agent.JOBS_FILE, app.state.llm)
    app.state.automation_task = asyncio.create_task(app.state.automation_runner.start())

    # Initialize Atulya Agent
    agent_core = AgentCore(llm_provider=app.state.llm)
    set_agent(agent_core)
    app.state.agent = agent_core

    # Reflexes: event-driven proactivity + self-monitoring. Reminders, health
    # changes and automation outcomes become events; trigger rules react; the
    # resulting notifications are relayed to connected clients.
    from atulya.buddhi import get_kernel
    from atulya.buddhi.triggers import TriggerEngine, connect_sensors
    from atulya.heartbeat import HeartbeatSystem
    from atulya.events import default_bus

    connect_sensors(default_bus)
    app.state.triggers = TriggerEngine(kernel=get_kernel(app.state.llm), events=default_bus)
    app.state.triggers.start()
    default_bus.subscribe("notification", _relay_notification)
    app.state.heartbeat = HeartbeatSystem(events=default_bus)
    app.state.heartbeat_task = asyncio.create_task(app.state.heartbeat.start())
    # Learned habits: "you usually … around now" when it hasn't happened yet today.
    from atulya.buddhi.profile import watch_habits

    app.state.habit_task = asyncio.create_task(watch_habits(get_kernel(app.state.llm).profiles, default_bus))
    from atulya.yantra.calendar_watch import watch_calendar

    from atulya.yantra.money import watch_bills

    app.state.calendar_task = asyncio.create_task(watch_calendar(default_bus))
    app.state.bills_task = asyncio.create_task(watch_bills(default_bus))
    # Senses: cameras and Home Assistant sensors publish what they perceive.
    from atulya.indriya import Senses

    app.state.senses = Senses(default_bus)
    await app.state.senses.start()

    app.state.llm_warm_task = asyncio.create_task(_warm_llm(app.state.llm))
    try:
        yield
    finally:
        app.state.triggers.stop()
        default_bus.unsubscribe("notification", _relay_notification)
        await app.state.heartbeat.stop()
        app.state.heartbeat_task.cancel()
        app.state.habit_task.cancel()
        app.state.calendar_task.cancel()
        app.state.bills_task.cancel()
        await app.state.senses.stop()
        await app.state.automation_runner.stop()
        app.state.automation_task.cancel()
        await app.state.mcp_manager.shutdown_all()
        await agent_core.shutdown()


async def _relay_notification(event) -> None:
    """Push a proactive notification (e.g. a due reminder) to connected clients."""
    from atulya.sevak.api_chat import broadcast_event

    payload = event.payload or {}
    logger.info("Atulya notification: %s — %s", payload.get("title"), payload.get("message"))
    await broadcast_event(str(payload.get("title") or "Atulya"), str(payload.get("message") or ""), event_type="info")


async def _connect_mcp_servers(app: FastAPI) -> None:
    config_path = Path(__file__).resolve().parents[1] / "yantra" / "mcp_servers.json"
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
# The web UI is same-origin and authenticates with a header, so it needs no
# CORS. ATULYA_CORS_ORIGINS lists other sites allowed to call the API.
from atulya.raksha.lockdown import cors_origins as _cors_origins  # noqa: E402

_CORS_ORIGINS = _cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _CORS_ORIGINS is None else _CORS_ORIGINS,
    allow_credentials=bool(_CORS_ORIGINS),  # never credentials with a wildcard
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(_rate_limiter)



for module in (api_account, api_chat, api_agent, api_home):
    app.include_router(module.router)


dist = Path(__file__).resolve().parents[2] / "drishti" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="web")


