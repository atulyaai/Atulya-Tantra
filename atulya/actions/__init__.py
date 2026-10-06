"""Actions: everything Atulya can do: the assistant tools, the intent router, money, music and media, tracking, the briefing, PC control, device tools, the agent loop and the audit log."""
from __future__ import annotations

import asyncio
import csv
import hashlib
import hmac
import io
import ipaddress
import json
import logging
import os
import platform
import re
import sys
import secrets
import socket
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import uuid
import webbrowser
import httpx
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from atulya import devices as learn

# This file used to be several modules (money, briefing, tracking, ...). They
# were merged into this one. `_t` is how any module in here reaches back to
# it (`_d._t._load_json(...)`); `tracking` and `tools` are the names those
# parts were imported under before the merge. None of the three is a file any
# more, so none can shadow a real submodule. The two aliases that no code
# ever imported went away with the rename.
_t = tracking = tools = sys.modules[__name__]

from atulya.devices import DeviceError, discover, get_hub

# ── ledger ────────────────────────────────────────────────────────────
_SECRET_KEYS = ("password", "token", "secret", "key")


def _path() -> Path:
    base = Path(os.environ.get("ATULYA_AGENT_DATA_DIR", "data/agent"))
    base.mkdir(parents=True, exist_ok=True)
    return base / "audit.jsonl"


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("***" if any(s in k.lower() for s in _SECRET_KEYS) else _clean(v)) for k, v in value.items()}
    if isinstance(value, str) and len(value) > 300:
        return value[:300] + "…"
    return value


_audit_lock = threading.Lock()
_GENESIS = "0" * 64


def _digest(prev: str, record: dict[str, Any]) -> str:
    body = json.dumps(record, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256((prev + body).encode("utf-8")).hexdigest()


def _tail_hash(path: Path) -> str:
    """The hash of the last chained line (each line also carries the hash of the one before it)."""
    try:
        for line in reversed(path.read_text(encoding="utf-8").splitlines()):
            if line.strip():
                return str(json.loads(line).get("h") or _GENESIS)
    except Exception:  # noqa: BLE001
        pass
    return _GENESIS


def audit(event: str, **fields: Any) -> None:
    """Record one event in a hash chain, so a changed or deleted line is detectable; never raises."""
    try:
        record = {"t": round(time.time(), 1), "event": event, **_clean(fields)}
        with _audit_lock:
            path = _path()
            prev = _tail_hash(path)
            line = json.dumps({**record, "prev": prev, "h": _digest(prev, record)}, ensure_ascii=False)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except Exception:  # noqa: BLE001 - auditing must never break an action
        pass


def verify_audit() -> dict[str, Any]:
    """Re-check the whole chain. Lines written before chaining existed are skipped."""
    path = _path()
    try:
        lines = [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    except FileNotFoundError:
        return {"ok": True, "checked": 0, "bad_line": None}
    prev, checked = _GENESIS, 0
    for number, line in enumerate(lines, 1):
        try:
            record = json.loads(line)
        except ValueError:
            return {"ok": False, "checked": checked, "bad_line": number}
        if "h" not in record:  # from before the chain started
            continue
        claimed_prev, claimed = record.pop("prev", None), record.pop("h")
        if claimed_prev != prev or _digest(prev, record) != claimed:
            return {"ok": False, "checked": checked, "bad_line": number}
        prev, checked = claimed, checked + 1
    return {"ok": True, "checked": checked, "bad_line": None}


def recent(limit: int = 20) -> list[dict[str, Any]]:
    try:
        lines = _path().read_text(encoding="utf-8").splitlines()[-limit:]
        return [json.loads(x) for x in lines]
    except Exception:  # noqa: BLE001
        return []


# ── actions ────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── Tool Registry ──────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, dict[str, Any]] = {}
_DATA_DIR = Path(os.environ.get("ATULYA_AGENT_DATA_DIR", "data/agent"))
_DATA_DIR.mkdir(parents=True, exist_ok=True)


def tool(name: str, description: str, parameters: dict[str, Any]):
    """Decorator that registers a plain function as an Atulya Agent tool.

    Usage:
        @tool("send_email", "Send an email", {
            "to": {"type": "string", "description": "Recipient"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
        })
        async def send_email(to: str, subject: str, body: str) -> str:
            ...
    """
    def decorator(fn: Callable) -> Callable:
        TOOL_REGISTRY[name] = {
            "description": description,
            "parameters": {
                pname: {**pschema, "required": True}
                for pname, pschema in parameters.items()
            },
            "fn": fn,
        }

        @wraps(fn)
        async def wrapper(*args, **kwargs):
            return await fn(*args, **kwargs)

        return wrapper
    return decorator


def get_tool_schemas() -> list[dict[str, Any]]:
    """Return tools as OpenAI-compatible JSON schemas for the agent loop."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": info["description"],
                "parameters": {
                    "type": "object",
                    "properties": info["parameters"],
                    "required": list(info["parameters"].keys()),
                },
            },
        }
        for name, info in TOOL_REGISTRY.items()
    ]


async def execute_tool(name: str, **kwargs) -> str:
    """Execute a registered tool and return its output text."""
    info = TOOL_REGISTRY.get(name)
    if not info:
        return f"Error: unknown tool '{name}'"
    try:

        audit("tool", name=name, args=kwargs)
        result = await info["fn"](**kwargs)
        return str(result) if result is not None else ""
    except Exception as e:
        logger.warning("Tool %s failed: %s", name, e)
        return f"Error executing {name}: {e}"


# ── Internal State Helpers ─────────────────────────────────────────────────

def _load_json(name: str) -> dict:
    from atulya import security as vault

    p = _DATA_DIR / name
    if p.exists():
        try:
            return json.loads(vault.read_text(p))
        except vault.VaultLocked:
            raise  # never pretend an encrypted file is empty: the next save would overwrite it
        except Exception:
            return {}
    return {}


def _save_json(name: str, data: dict | list):
    from atulya import security as vault

    vault.write_text(_DATA_DIR / name, json.dumps(data, indent=2, default=str))



# Skill modules register their tools with @tool on import.
from . import scheduling
from .scheduling import *  # noqa: F401,F403
from . import email
from .email import *  # noqa: F401,F403
from . import news
from .news import *  # noqa: F401,F403
from . import mqtt
from .mqtt import *  # noqa: F401,F403
from . import watch
from .watch import *  # noqa: F401,F403
from . import assistant
from .assistant import *  # noqa: F401,F403
from . import intent
from .intent import *  # noqa: F401,F403
from . import money
from .money import *  # noqa: F401,F403
from . import briefing
from .briefing import *  # noqa: F401,F403
from . import computer
from .computer import *  # noqa: F401,F403
from . import devices
from .devices import *  # noqa: F401,F403
from . import agent
from .agent import *  # noqa: F401,F403
from . import messaging
from .messaging import *  # noqa: F401,F403

# Private helpers that tests and the agent loop reach through the package.
from .scheduling import _parse_time, _reminder_callbacks, _reminders, _scheduler_tasks  # noqa: F401
from .email import _EMAIL_CFG, _EMAIL_STATE_FILE, _EMAIL_WINDOW, _SEEN_KEEP, _email_state, _google  # noqa: F401
from .email import _load_email_config, _new_emails, _new_gmail, _new_imap, _save_email_state, _sender_name  # noqa: F401
from .news import _NEWS_FEEDS_FILE, _NEWS_KEEP, _NEWS_STATE_FILE, _NEWS_WINDOW, _feed_entries, _new_news  # noqa: F401
from .news import _news_feeds, _news_state, _save_news_feeds, _save_news_state  # noqa: F401
from .mqtt import _MQTT_CONFIG_FILE, _MQTT_STATE_FILE, _mqtt_config, _mqtt_state, _save_mqtt_config, _save_mqtt_state  # noqa: F401
from .watch import _FEEDBACK_FILE, _FEEDBACK_KEEP, _WATCHDOG_CONFIG_FILE, _WATCHDOG_STATE_FILE, _feedback_entries, _save_watchdog_config  # noqa: F401
from .watch import _save_watchdog_state, _watchdog_config, _watchdog_state  # noqa: F401
from .assistant import _CALENDAR, _HOME_DEVICES, _NO_HUB, _VISION_AVAILABLE, _VISION_MODEL_PATH, _simulate_home_control  # noqa: F401
from .intent import _AMT, _CONTACT_ADD, _DEVICE_ALIASES, _MEDIA_KEYS, _MESSAGE_VERB, _POLITE  # noqa: F401
from .intent import _WHEN_RE, _contact_intent, _device_admin_intent, _device_intent, _extract_location, _match_device  # noqa: F401
from .intent import _media_intent, _message_intent, _money_intent, _schedule_intent, _website_intent  # noqa: F401
from .money import _ACCT_RE, _AMOUNT_COLS, _AMT_RE, _CATEGORIES, _CREDIT_RE, _DATE_COLS  # noqa: F401
from .money import _DATE_RES, _DEBIT_COLS, _DEBIT_RE, _DESC_COLS, _MERCHANT_RES, _MONEYISH  # noqa: F401
from .money import _SKIP_RE, _alert_date, _alert_reply, _brain_ask, _budget_note, _due_date  # noqa: F401
from .money import _load, _numbers, _parse_when, _period, _save, _sigs  # noqa: F401
from .money import _store_alert, _token_file  # noqa: F401
from .briefing import _PRICE, _VIDEO_ID, _VK, _fetch, _find_youtube_video, _is_public_url  # noqa: F401
from .briefing import _load_watchlist, _press, _to_ts  # noqa: F401
from .computer import _gui, _not_allowed, _on_computer  # noqa: F401
from .devices import _first_param  # noqa: F401
from .messaging import _CHANNEL_WORDS, _HA_ENTITY_ID_RE, _HA_SERVICE_PART_RE, _contacts, _save_contacts, _twilio_say_twiml  # noqa: F401

# ── Load persisted state on import ─────────────────────────────────────────

def _bootstrap():
    from atulya.security import VaultLocked

    try:
        data = _load_json("reminders.json")
        if data:
            _reminders.clear()
            for item in data if isinstance(data, list) else []:
                _reminders[item["id"]] = item
        events = _load_json("calendar.json")  # saved on every change; without this a restart forgot the calendar
        for item in events if isinstance(events, list) else []:
            if isinstance(item, dict) and "id" in item and "time" in item:
                _CALENDAR[item["id"]] = item
        _load_email_config()
    except VaultLocked as exc:  # start anyway; the encrypted files stay untouched until the passphrase is right
        logger.error("Private data is locked: %s", exc)


_bootstrap()

