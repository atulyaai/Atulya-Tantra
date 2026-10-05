"""Sevak (सेवक): the web server package."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from atulya import dwar as api_account
from atulya import dwar as api_agent
from atulya import dwar as api_chat
from atulya import dwar as api_home
from atulya.dwar import AutomationRunner
from atulya.raksha import cors_origins as _cors_origins
from atulya.setu import MCPClientManager

# ── sevak ────────────────────────────────────────────────────────────



# ── app ────────────────────────────────────────────────────────────
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


async def _poll_telegram(channel, llm) -> None:
    """Long-poll the configured, allowlisted Telegram bot for inbound messages."""
    while True:
        try:
            await channel.poll_and_reply(llm=llm)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Telegram polling failed")
        await asyncio.sleep(2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from atulya.dwar import set_agent
    from atulya.kriya import AgentCore
    from atulya.mastishk import get_default_llm

    app.state.llm = get_default_llm()
    app.state.mcp_manager = MCPClientManager()
    app.state.mcp_errors = []
    await _connect_mcp_servers(app)
    api_agent._seed_default_jobs()
    app.state.automation_runner = AutomationRunner(api_agent.JOBS_FILE, app.state.llm)
    app.state.automation_task = asyncio.create_task(app.state.automation_runner.start())

    app.state.telegram_task = None
    bot_token = os.environ.get("ATULYA_TELEGRAM_BOT_TOKEN", "").strip()
    allowlist = os.environ.get("ATULYA_TELEGRAM_ALLOWLIST", "").strip()
    if bot_token and allowlist:
        from atulya.sandesh import TelegramChannel

        app.state.telegram = TelegramChannel()
        await app.state.telegram.connect({"allowlist": allowlist})
        if not await app.state.telegram.configure_profile():
            logger.warning("Telegram profile setup was incomplete; bot replies remain enabled")
        app.state.telegram_task = asyncio.create_task(_poll_telegram(app.state.telegram, app.state.llm))
        logger.info("Telegram bot polling enabled for the configured allowlist")
    elif bot_token:
        logger.warning("Telegram bot token is set but ATULYA_TELEGRAM_ALLOWLIST is empty; polling is disabled")

    # Initialize Atulya Agent
    agent_core = AgentCore(llm_provider=app.state.llm)
    set_agent(agent_core)
    app.state.agent = agent_core

    # Reflexes: event-driven proactivity + self-monitoring. Reminders, health
    # changes and automation outcomes become events; trigger rules react; the
    # resulting notifications are relayed to connected clients.
    from atulya.adhar import HeartbeatSystem, default_bus
    from atulya.buddhi import TriggerEngine, connect_sensors, get_kernel

    connect_sensors(default_bus)
    app.state.triggers = TriggerEngine(kernel=get_kernel(app.state.llm), events=default_bus)
    app.state.triggers.start()
    default_bus.subscribe("notification", _relay_notification)
    app.state.heartbeat = HeartbeatSystem(events=default_bus)
    app.state.heartbeat_task = asyncio.create_task(app.state.heartbeat.start())
    # Learned habits: "you usually … around now" when it hasn't happened yet today.
    from atulya.buddhi import watch_habits

    app.state.habit_task = asyncio.create_task(watch_habits(get_kernel(app.state.llm).profiles, default_bus))
    from atulya.kriya import watch_bills, watch_calendar

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
        if app.state.telegram_task:
            app.state.telegram_task.cancel()
            await asyncio.gather(app.state.telegram_task, return_exceptions=True)
        await app.state.mcp_manager.shutdown_all()
        await agent_core.shutdown()


async def _relay_notification(event) -> None:
    """Push a proactive notification (e.g. a due reminder) to connected clients."""
    from atulya.dwar import broadcast_event

    payload = event.payload or {}
    logger.info("Atulya notification: %s — %s", payload.get("title"), payload.get("message"))
    await broadcast_event(str(payload.get("title") or "Atulya"), str(payload.get("message") or ""), event_type="info")


async def _connect_mcp_servers(app: FastAPI) -> None:
    config_path = Path(__file__).resolve().parent / "setu_servers.json"
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


dist = Path(__file__).resolve().parents[1] / "drishti" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="web")


# ── __main__ ────────────────────────────────────────────────────────────
__all__ = ["main"]


def _brain_report() -> None:
    """Say which brains found a key, so a missing or misspelled key is obvious at startup."""
    from atulya.mastishk import ProviderRouter

    names = [p.name() for p in ProviderRouter().providers if p.is_available() and p.name() != "No brain loaded"]
    print("  Brains ready: " + (", ".join(names) if names else "none. Add a key to .env (see .env.example)"))


def main() -> None:
    from atulya.adhar import load_env, migrate_all
    from atulya.raksha import bind_host

    migrate_all()  # an old `data` folder becomes `kosh`, once
    found = load_env()
    print("\n  Settings: " + (", ".join(str(p) for p in found) if found else "no .env file found next to start.bat"))
    _brain_report()

    host = bind_host("127.0.0.1")
    port = int(os.environ.get("ATULYA_PORT", 8501))

    import socket

    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            print(f"\n  Atulya is already running on port {port} (or another program is using it).")
            print(f"  Open http://127.0.0.1:{port}, close the other window first, or set ATULYA_PORT in .env.\n")
            raise SystemExit(1)

    scheme, ssl_args = "http", {}
    from atulya import raksha as https_mod

    if https_mod.https_enabled():
        cert_file, key_file = https_mod.ensure_certs()
        scheme, ssl_args = "https", {"ssl_certfile": cert_file, "ssl_keyfile": key_file}
    print("\n  Atulya")
    print(f"  Running on: {scheme}://{host}:{port}\n")
    if scheme == "https":
        print("  Your browser will warn once about the certificate (it is your own): choose Advanced > Continue.\n")
    from atulya import dwar as users
    users.seed_default_admin()
    
    print("  Starting Atulya. The first start can take a little longer while the screen is built...\n", flush=True)

    from uvicorn.config import Config
    from uvicorn.server import Server

    Server(Config(app, host=host, port=port, log_level="warning", **ssl_args)).run()


if __name__ == "__main__":
    main()

