"""Sevak (सेवक): the web server package."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from atulya import dwar as api
from atulya.dwar import AutomationRunner
from atulya.raksha import cors_origins as _cors_origins
from atulya.setu import get_manager as _mcp_manager

# ── sevak ────────────────────────────────────────────────────────────



# ── app ────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── Rate Limiting ─────────────────────────────────────────────────────────

_RATE_LIMIT_WINDOW = 60
_RATE_LIMIT_MAX = 100
_RATE_STORE_MAX_CLIENTS = 10_000
_RATE_STORE: OrderedDict[str, list[float]] = OrderedDict()

# Guessing a password, a pairing code or a one-hour session token is a
# different game from browsing, and the bucket above is sized for somebody
# who is busy rather than somebody who is guessing:100 attempts a minute at
# a login is a meaningful head start. These paths are counted against the
# path as well as the address, so hammering one of them is over quickly and
# the rest of the server keeps its full budget.
_CREDENTIAL_MAX = 10
_CREDENTIAL_PREFIXES = ("/api/auth/", "/api/pairing/", "/api/miniapp/session")
_CREDENTIAL_STORE: OrderedDict[str, list[float]] = OrderedDict()


def _count_one(store: OrderedDict, key: str, now: float, window_start: float, maximum: int):
    """Count one call against a bucket, or say why it may not proceed."""
    # Requests move their key to the end, so the front is always the oldest
    # and expired clients can be evicted without scanning the whole store.
    while store:
        _, oldest_hits = next(iter(store.items()))
        if oldest_hits and oldest_hits[-1] > window_start:
            break
        store.pop(next(iter(store)))
    hits = [t for t in store.get(key, []) if t > window_start]
    if len(hits) >= maximum:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again later."})
    if key not in store and len(store) >= _RATE_STORE_MAX_CLIENTS:
        return JSONResponse(status_code=429, content={"detail": "Rate limit capacity reached. Try again later."})
    hits.append(now)
    store[key] = hits
    store.move_to_end(key)
    return None


async def _rate_limiter(request: Request, call_next):
    client = request.client.host if request.client else "unknown"
    now = time.time()
    window_start = now - _RATE_LIMIT_WINDOW
    path = request.url.path
    checks = [(client, _RATE_STORE, _RATE_LIMIT_MAX)]
    if path.startswith(_CREDENTIAL_PREFIXES):
        checks.append((f"{path}|{client}", _CREDENTIAL_STORE, _CREDENTIAL_MAX))
    for key, store, maximum in checks:
        refused = _count_one(store, key, now, window_start, maximum)
        if refused is not None:
            return refused
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


async def _poll_all_channels(registry, llm) -> None:
    """Poll every configured channel (WhatsApp, Signal, Email, Slack, Discord …).

    Only channels that have a config in kosh/channels/channels.json are
    connected; the rest are silently skipped.  Inbound messages go through
    ``channel.handle_message`` so the same brain and tools answer on any surface.
    """
    from atulya.sandesh import ChannelMessage

    while True:
        try:
            for name in list(registry._channels):
                if name == "telegram":
                    continue  # has its own dedicated poll task
                ch = registry._channels[name]
                cfg = registry._configs.get(name, {})
                if not cfg:
                    continue  # not configured for this user
                try:
                    if not ch.connected:
                        await ch.connect(cfg)
                    if not ch.connected:
                        continue
                    for msg in await ch.receive():
                        if isinstance(msg, ChannelMessage):
                            await ch.handle_message(msg, llm=llm)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.debug("channel %s poll failed", name, exc_info=True)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("multi-channel polling failed")
        await asyncio.sleep(3)


async def _cancel_task(task: asyncio.Task | None) -> None:
    """Cancel a background task and wait for its cleanup to finish."""
    if task is None:
        return
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from atulya.dwar import set_agent
    from atulya.kriya import AgentCore
    from atulya.mastishk import get_default_llm

    app.state.llm = get_default_llm()
    # One manager for the whole process: the brain reads its tools from here
    # via build_unified_registry(), so an entry enabled in setu_servers.json
    # actually reaches the model instead of being discovered and dropped.
    app.state.mcp_manager = _mcp_manager()
    app.state.mcp_errors = app.state.mcp_manager.errors  # same list, readable either way
    await _connect_mcp_servers(app)
    api._seed_default_jobs()
    app.state.automation_runner = AutomationRunner(api.JOBS_FILE, app.state.llm)
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
        # Armed here so a due reminder can reach a pocket, not just a browser.
        _PROACTIVE["channel"] = app.state.telegram
        _PROACTIVE["targets"] = [t.strip() for t in allowlist.split(",") if t.strip()]
        logger.info("Telegram bot polling enabled for the configured allowlist")
    elif bot_token:
        logger.warning("Telegram bot token is set but ATULYA_TELEGRAM_ALLOWLIST is empty; polling is disabled")

    # ── Every other channel (WhatsApp, Signal, Email, Slack, Discord …) ──────
    # The classes exist in sandesh.py; start the registry poller so any channel
    # the user configured in kosh/channels/channels.json is actually reached.
    app.state.channel_registry = None
    app.state.channel_task = None
    try:
        from atulya.sandesh import create_default_registry as _create_channels

        app.state.channel_registry = _create_channels(
            os.environ.get("ATULYA_CHANNELS_DIR", "kosh/channels")
        )
        # Telegram has its own long-poll task above; including it here would
        # deliver every message twice.
        configured = [
            n for n, cfg in app.state.channel_registry._configs.items()
            if cfg and n != "telegram"
        ]
        if configured:
            app.state.channel_task = asyncio.create_task(
                _poll_all_channels(app.state.channel_registry, app.state.llm)
            )
            logger.info("multi-channel polling enabled: %s", ", ".join(configured))
        else:
            logger.info("no extra channels configured (WhatsApp/Signal/Email … idle)")
    except Exception:
        logger.exception("multi-channel setup failed")

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
    from atulya.kriya import watch_bills, watch_calendar, watch_email, watch_news, watch_mqtt, watch_filesystem

    app.state.calendar_task = asyncio.create_task(watch_calendar(default_bus))
    app.state.bills_task = asyncio.create_task(watch_bills(default_bus))
    # Email: idles on its own until a mailbox is configured, then announces new
    # mail through the same triggers as every other event.
    app.state.email_task = asyncio.create_task(watch_email(default_bus))
    # News: same bargain -- no feeds subscribed means nothing is ever fetched.
    app.state.news_task = asyncio.create_task(watch_news(default_bus))
    # MQTT: idles if no broker configured; otherwise republishes messages as events.
    app.state.mqtt_task = asyncio.create_task(watch_mqtt(default_bus))
    # Watchdog: file system changes become events.
    app.state.watchdog_task = asyncio.create_task(watch_filesystem(default_bus))
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
        app.state.email_task.cancel()
        app.state.news_task.cancel()
        app.state.mqtt_task.cancel()
        app.state.watchdog_task.cancel()
        if getattr(app.state, "channel_task", None):
            app.state.channel_task.cancel()
            await asyncio.gather(app.state.channel_task, return_exceptions=True)
        await app.state.senses.stop()
        await app.state.automation_runner.stop()
        app.state.automation_task.cancel()
        await _cancel_task(app.state.llm_warm_task)
        if app.state.telegram_task:
            app.state.telegram_task.cancel()
            await asyncio.gather(app.state.telegram_task, return_exceptions=True)
        _PROACTIVE["channel"] = None  # the next startup decides again
        await app.state.mcp_manager.shutdown_all()
        await agent_core.shutdown()


# Set by the lifespan: the one channel Atulya may speak on without being
# spoken to first. Telegram only lets a bot message a chat somebody has
# already written to, so the allowlist doubles as the list of people who have.
# A dict rather than two globals so the lifespan can arm and disarm it without
# a `global` declaration scattered through a hundred-line function.
_PROACTIVE: dict = {"channel": None, "targets": []}


def _push_enabled() -> bool:
    return os.environ.get("ATULYA_TELEGRAM_PUSH", "on").strip().lower() not in ("off", "0", "false", "no")


async def _announce_on_telegram(title: str, message: str) -> None:
    """Speak first, rather than only ever answering.

    A dashboard client hears this over its socket; a phone in your pocket does
    not, so the same words go to Telegram as plain text. A send that fails is
    dropped -- a phone that has blocked the bot must not stop a reminder from
    reaching everybody else -- and an empty message is not worth a tap.
    """
    channel = _PROACTIVE.get("channel")
    if channel is None or not _push_enabled() or not message:
        return
    text = f"{title}: {message}" if title and title.lower() != message.lower() else message
    for chat_id in _PROACTIVE.get("targets") or []:
        try:
            await channel.send(text[:4000], chat_id=chat_id)
        except Exception as exc:  # noqa: BLE001 - one bad chat must not break the relay
            logger.debug("telegram push to %s failed: %s", chat_id, exc)


async def _relay_notification(event) -> None:
    """Push a proactive notification (e.g. a due reminder) to connected clients."""
    from atulya.dwar import broadcast_event

    payload = event.payload or {}
    title = str(payload.get("title") or "Atulya")
    message = str(payload.get("message") or "")
    logger.info("Atulya notification: %s — %s", title, message)
    await broadcast_event(title, message, event_type="info")
    await _announce_on_telegram(title, message)


async def _connect_mcp_servers(app: FastAPI) -> None:
    app.state.mcp_errors.clear()  # the manager outlives one lifespan; a restart starts clean
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

# Same-origin dashboard needs no CORS at all, so the default is "none". A
# wildcard here would let any web page read /api/auth/local and steal the admin
# token, so ATULYA_CORS_ORIGINS must list origins explicitly to open this up.
_CORS_ORIGINS = _cors_origins() or []
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=bool(_CORS_ORIGINS),  # never credentials with a wildcard
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(_rate_limiter)



app.include_router(api.router)


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
    # `dwar` was imported at module scope, before .env was in the environment,
    # so its ADMIN_TOKEN was minted at random. Refresh it now that .env is read,
    # or the ATULYA_DASHBOARD_TOKEN you configured would never be accepted.
    api.sync_admin_token()
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

