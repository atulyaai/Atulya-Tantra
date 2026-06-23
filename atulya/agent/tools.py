"""Atulya Agent Tool System — plain functions + JSON schemas.

Every skill is a plain async function decorated with @tool.
Adding a new skill = one decorator + one function = ~5 minutes.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ── Tool Registry ──────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, dict[str, Any]] = {}
_DATA_DIR = Path(os.environ.get("ATULYA_AGENT_DATA_DIR", "assets/agent"))
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
        result = await info["fn"](**kwargs)
        return str(result) if result is not None else ""
    except Exception as e:
        logger.warning("Tool %s failed: %s", name, e)
        return f"Error executing {name}: {e}"


# ── Internal State Helpers ─────────────────────────────────────────────────

def _load_json(name: str) -> dict:
    p = _DATA_DIR / name
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


def _save_json(name: str, data: dict | list):
    p = _DATA_DIR / name
    p.write_text(json.dumps(data, indent=2, default=str))


# ── Tool: Reminder / Scheduling Skills ────────────────────────────────────

_reminders: dict[str, dict[str, Any]] = {}
_scheduler_tasks: dict[str, asyncio.Task] = {}
_reminder_callbacks: list[Callable] = []


def register_reminder_callback(cb: Callable):
    _reminder_callbacks.append(cb)


def _parse_time(text: str) -> float | None:
    """Parse natural language time expressions."""
    text = text.lower().strip()
    now = time.time()
    t = time.localtime(now)

    m = re.match(r"in\s+(\d+)\s*(second|seconds|sec|secs|minute|minutes|min|mins|hour|hours|hr|hrs|day|days)", text)
    if m:
        amount, unit = int(m.group(1)), m.group(2)
        if unit.startswith("s"):
            return now + amount
        elif unit.startswith("mi"):
            return now + amount * 60
        elif unit.startswith("h"):
            return now + amount * 3600
        else:
            return now + amount * 86400

    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
    if m:
        hour, minute_str, ampm = int(m.group(1)), m.group(2), m.group(3)
        minute = int(minute_str) if minute_str else 0
        if ampm:
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
        target = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, hour, minute, 0, t.tm_wday, t.tm_yday, t.tm_isdst))
        if target < now:
            target += 86400
        return target

    # Handle "tomorrow at HH:MM" or "tomorrow at HHam/pm"
    m = re.match(r"tomorrow\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
    if m:
        hour, minute_str, ampm = int(m.group(1)), m.group(2), m.group(3)
        minute = int(minute_str) if minute_str else 0
        if ampm:
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
        target = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, hour, minute, 0, t.tm_wday, t.tm_yday, t.tm_isdst))
        return target + 86400

    # Handle "next monday" / "next tuesday" etc
    days = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
    m = re.match(r"(?:next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", text)
    if m:
        target_day = days[m.group(1)]
        days_ahead = target_day - t.tm_wday
        if days_ahead <= 0:
            days_ahead += 7
        target = now + days_ahead * 86400
        # Check for time after the weekday
        m2 = re.search(r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
        if m2:
            hour, minute_str, ampm = int(m2.group(1)), m2.group(2), m2.group(3)
            minute = int(minute_str) if minute_str else 0
            if ampm:
                if ampm == "pm" and hour < 12:
                    hour += 12
                elif ampm == "am" and hour == 12:
                    hour = 0
            target = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, hour, minute, 0, t.tm_wday, t.tm_yday, t.tm_isdst)) + days_ahead * 86400
        return target


@tool("set_reminder", "Set a reminder or alarm", {
    "message": {"type": "string", "description": "What to remind about"},
    "time_str": {"type": "string", "description": "When: 'in 5 minutes', 'tomorrow at 9am', '30 min', '2:30pm'"},
})
async def set_reminder(message: str, time_str: str = "in 5 minutes") -> str:
    parsed = _parse_time(time_str)
    if not parsed:
        return f"Could not understand time: '{time_str}'. Try 'in 5 minutes', 'tomorrow at 9am', or '2:30pm'."
    rid = f"rem_{int(time.time() * 1000)}"
    entry = {"id": rid, "message": message, "scheduled_time": parsed, "created_at": time.time(), "status": "pending"}
    _reminders[rid] = entry
    _save_json("reminders.json", list(_reminders.values()))

    delay = parsed - time.time()
    if delay > 0:

        async def _fire():
            await asyncio.sleep(delay)
            entry["status"] = "done"
            _save_json("reminders.json", list(_reminders.values()))
            for cb in _reminder_callbacks:
                try:
                    await cb("reminder", entry)
                except Exception:
                    pass

        _scheduler_tasks[rid] = asyncio.create_task(_fire())
    else:
        entry["status"] = "done"
        _save_json("reminders.json", list(_reminders.values()))

    return f"Reminder set: '{message}' at {time} (id: {rid})"


@tool("list_reminders", "List upcoming reminders", {
    "hours": {"type": "integer", "description": "How many hours ahead to look (default 24)", "default": 24},
})
async def list_reminders(hours: int = 24) -> str:
    now = time.time()
    cutoff = now + hours * 3600
    upcoming = [r for r in _reminders.values() if r["status"] == "pending" and now <= r["scheduled_time"] <= cutoff]
    if not upcoming:
        return "No upcoming reminders."
    lines = [f"{i+1}. {r['message']} (at {time.ctime(r['scheduled_time'])})" for i, r in enumerate(sorted(upcoming, key=lambda x: x["scheduled_time"]))]
    return "\n".join(lines)


@tool("cancel_reminder", "Cancel a reminder by ID", {
    "reminder_id": {"type": "string", "description": "The reminder ID from set_reminder or list_reminders"},
})
async def cancel_reminder(reminder_id: str) -> str:
    if reminder_id in _reminders:
        _reminders[reminder_id]["status"] = "cancelled"
        _save_json("reminders.json", list(_reminders.values()))
        if reminder_id in _scheduler_tasks:
            _scheduler_tasks[reminder_id].cancel()
        return f"Reminder {reminder_id} cancelled."
    return f"Reminder {reminder_id} not found."


# ── Tool: Email Skills ─────────────────────────────────────────────────────

_EMAIL_CFG: dict[str, Any] = {}


def _load_email_config():
    global _EMAIL_CFG
    cfg = _load_json("email_config.json")
    if cfg:
        _EMAIL_CFG = cfg


@tool("configure_email", "Configure email account (IMAP/SMTP)", {
    "imap_server": {"type": "string", "description": "IMAP server address"},
    "imap_port": {"type": "integer", "description": "IMAP port (default 993)", "default": 993},
    "smtp_server": {"type": "string", "description": "SMTP server address"},
    "smtp_port": {"type": "integer", "description": "SMTP port (default 587)", "default": 587},
    "username": {"type": "string", "description": "Email username"},
    "password": {"type": "string", "description": "Email password (stored locally)"},
})
async def configure_email(imap_server: str, imap_port: int = 993, smtp_server: str = "", smtp_port: int = 587, username: str = "", password: str = "") -> str:
    cfg = {"imap_server": imap_server, "imap_port": imap_port, "smtp_server": smtp_server or imap_server, "smtp_port": smtp_port, "username": username, "password": password}
    _EMAIL_CFG.update(cfg)
    _save_json("email_config.json", _EMAIL_CFG)
    return f"Email configured for {username}."


@tool("send_email", "Send an email", {
    "to": {"type": "string", "description": "Recipient email address"},
    "subject": {"type": "string", "description": "Email subject"},
    "body": {"type": "string", "description": "Email body text"},
})
async def send_email(to: str, subject: str, body: str) -> str:
    if not _EMAIL_CFG.get("smtp_server"):
        return "Email not configured. Use configure_email first."
    try:
        import aiosmtplib
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["From"] = _EMAIL_CFG["username"]
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        await aiosmtplib.send(msg, hostname=_EMAIL_CFG["smtp_server"], port=_EMAIL_CFG["smtp_port"], username=_EMAIL_CFG["username"], password=_EMAIL_CFG["password"], use_tls=_EMAIL_CFG["smtp_port"] == 587)
        return f"Email sent to {to}: '{subject}'"
    except ImportError:
        return "aiosmtplib not installed. Install with: pip install aiosmtplib"
    except Exception as e:
        return f"Failed to send email: {e}"


@tool("fetch_emails", "Fetch recent emails from inbox", {
    "limit": {"type": "integer", "description": "Number of emails to fetch (default 5)", "default": 5},
})
async def fetch_emails(limit: int = 5) -> str:
    if not _EMAIL_CFG.get("imap_server"):
        return "Email not configured. Use configure_email first."
    try:
        import aioimaplib
        import email
        client = aioimaplib.IMAP4_SSL(_EMAIL_CFG["imap_server"], _EMAIL_CFG["imap_port"])
        await client.wait_hello_from_server()
        await client.login(_EMAIL_CFG["username"], _EMAIL_CFG["password"])
        await client.select("INBOX")
        _, data = await client.search("ALL")
        ids = data[0].split()[-limit:]
        lines = []
        for mid in ids:
            _, msg_data = await client.fetch(mid, "(RFC822)")
            for part in msg_data:
                if isinstance(part, tuple):
                    msg = email.message_from_bytes(part[1])
                    subj = msg["Subject"] or "(no subject)"
                    frm = msg["From"] or "unknown"
                    lines.append(f"From: {frm} | Subject: {subj}")
        await client.logout()
        return "\n".join(lines) if lines else "No emails found."
    except ImportError:
        return "aioimaplib not installed. Install with: pip install aioimaplib"
    except Exception as e:
        return f"Failed to fetch emails: {e}"


# ── Tool: System / Proactive Skills ────────────────────────────────────────


@tool("get_system_status", "Get system health metrics", {})
async def get_system_status() -> str:
    import psutil
    cpu = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage(".")
    return (
        f"CPU: {cpu}% | RAM: {ram.percent}% ({ram.available / 1024**3:.1f} GB free) | "
        f"Disk: {disk.percent}% ({disk.free / 1024**3:.1f} GB free)"
    )


@tool("get_proactive_suggestions", "Get context-aware suggestions", {
    "context": {"type": "string", "description": "Optional context hint", "default": ""},
})
async def get_proactive_suggestions(context: str = "") -> str:
    import psutil
    now = time.localtime()
    hour = now.tm_hour
    cpu = psutil.cpu_percent(interval=0.1)
    ram_gb = psutil.virtual_memory().available / 1024**3
    disk_gb = psutil.disk_usage(".").free / 1024**3
    suggestions = []
    if cpu > 80:
        suggestions.append("⚠ CPU high — close some apps?")
    if ram_gb < 2:
        suggestions.append(f"⚠ Low RAM ({ram_gb:.1f} GB free) — consider closing browsers.")
    if disk_gb < 5:
        suggestions.append(f"⚠ Low disk ({disk_gb:.1f} GB free) — clean temp files.")
    if 7 <= hour < 9:
        suggestions.append("☀ Good morning! Review today's schedule?")
    elif hour >= 23:
        suggestions.append("🌙 Late night. Set an alarm for tomorrow?")
    if not suggestions:
        suggestions.append("✓ All systems nominal.")
    return "\n".join(suggestions)


# ── Tool: Vision Skills ────────────────────────────────────────────────────

_VISION_MODEL_PATH: str | None = None
_VISION_AVAILABLE = False


@tool("download_vision_model", "Download the vision model (LLaVA, ~4.5 GB)", {
    "model_type": {"type": "string", "description": "Model type: 'llava' (default) or 'bakllava'", "default": "llava"},
})
async def download_vision_model(model_type: str = "llava") -> str:
    urls = {"llava": "https://huggingface.co/bartowski/llava-v1.6-mistral-7b-GGUF/resolve/main/llava-v1.6-mistral-7b-Q4_K_M.gguf"}
    dest = Path.home() / ".cache" / "atulya" / "models" / f"{model_type}-v1.6.gguf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return f"Model already exists at {dest}"
    url = urls.get(model_type)
    if not url:
        return f"Unknown model: {model_type}"
    import urllib.request
    try:
        urllib.request.urlretrieve(url, str(dest))
        global _VISION_MODEL_PATH, _VISION_AVAILABLE
        _VISION_MODEL_PATH = str(dest)
        _VISION_AVAILABLE = True
        return f"Model downloaded to {dest} ({(dest.stat().st_size / 1024 / 1024):.0f} MB)"
    except Exception as e:
        return f"Download failed: {e}"


@tool("analyze_image", "Analyze an image file (vision model required)", {
    "image_path": {"type": "string", "description": "Path to image file"},
    "task": {"type": "string", "description": "Task: 'analyze', 'ocr', 'objects', 'scene'", "default": "analyze"},
})
async def analyze_image(image_path: str, task: str = "analyze") -> str:
    if not _VISION_AVAILABLE or not _VISION_MODEL_PATH:
        return "Vision model not loaded. Use download_vision_model first."
    try:
        from atulya.local_provider import LocalGGUFProvider
        provider = LocalGGUFProvider(_VISION_MODEL_PATH)
        if not provider.is_available():
            return "Vision model not available."
        prompts = {"ocr": "Extract ALL text from this image.", "objects": "List ALL objects visible.", "scene": "Describe the scene.", "analyze": "Describe what you see in detail."}
        prompt = prompts.get(task, prompts["analyze"])
        result = await provider.chat(prompt, system_prompt="You analyze images precisely. Be specific.")
        return result or "No analysis returned."
    except Exception as e:
        return f"Analysis failed: {e}"


# ── Load persisted state on import ─────────────────────────────────────────

def _bootstrap():
    data = _load_json("reminders.json")
    if data:
        _reminders.clear()
        for item in data if isinstance(data, list) else []:
            _reminders[item["id"]] = item
    _load_email_config()


_bootstrap()
