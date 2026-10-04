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
_DATA_DIR = Path(os.environ.get("ATULYA_AGENT_DATA_DIR", "kosh/agent"))
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
        from atulya.lekha import audit

        audit("tool", name=name, args=kwargs)
        result = await info["fn"](**kwargs)
        return str(result) if result is not None else ""
    except Exception as e:
        logger.warning("Tool %s failed: %s", name, e)
        return f"Error executing {name}: {e}"


# ── Internal State Helpers ─────────────────────────────────────────────────

def _load_json(name: str) -> dict:
    from atulya import raksha as vault

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
    from atulya import raksha as vault

    vault.write_text(_DATA_DIR / name, json.dumps(data, indent=2, default=str))


# ── Tool: Reminder / Scheduling Skills ────────────────────────────────────

_reminders: dict[str, dict[str, Any]] = {}
_scheduler_tasks: dict[str, asyncio.Task] = {}
_reminder_callbacks: list[Callable] = []


def register_reminder_callback(cb: Callable):
    _reminder_callbacks.append(cb)


def _parse_time(text: str) -> float | None:
    """Parse natural language time expressions."""
    text = text.lower().strip()
    # "at 5pm", "today at 6pm", "tonight at 9", "on monday at 10am" -> the time itself
    text = re.sub(r"^(?:(?:today|tonight|this evening)\s+)?(?:at|on|by)\s+", "", text)
    text = re.sub(r"^(?:today|tonight)\s+", "", text)
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

    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(parsed))
    return f"Reminder set: '{message}' at {when} (id: {rid})"


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
# With Google connected (Settings → Accounts) email and calendar use the
# requesting user's Gmail and Google Calendar; otherwise IMAP/SMTP and the
# built-in calendar.

_EMAIL_CFG: dict[str, Any] = {}


def _google():
    """The current user's connected Google account, or None."""
    try:
        from atulya.google import GoogleAccount

        account = GoogleAccount.for_current_user()
        return account if account.connected else None
    except Exception:  # noqa: BLE001 - never let an integration break the basics
        return None


def _sender_name(value: str) -> str:
    name = value.split("<", 1)[0].strip().strip('"')
    return name or value


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
    google = _google()
    if google is not None:
        from atulya.google import GoogleError

        try:
            await google.send_message(to, subject, body)
        except GoogleError as exc:
            return f"Couldn't send with Gmail: {exc}"
        return f"Email sent to {to}: '{subject}' (Gmail)"
    if not _EMAIL_CFG.get("smtp_server"):
        return "Email not configured. Use configure_email first."
    try:
        from email.message import EmailMessage

        import aiosmtplib
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
    "query": {"type": "string", "description": "Optional Gmail search, e.g. 'is:unread' or 'from:rahul'",
              "default": ""},
})
async def fetch_emails(limit: int = 5, query: str = "") -> str:
    google = _google()
    if google is not None:
        from atulya.google import GoogleError

        try:
            messages = await google.list_messages(query or "in:inbox", limit)
        except GoogleError as exc:
            return f"Couldn't read Gmail: {exc}"
        if not messages:
            return "No emails found." if query else "Your inbox is empty."
        lines = [f"{i}. {_sender_name(m['from'])} — {m['subject'] or '(no subject)'}"
                 + (" (unread)" if m["unread"] else "") for i, m in enumerate(messages, 1)]
        return "Latest emails:\n" + "\n".join(lines)
    if not _EMAIL_CFG.get("imap_server"):
        return "Email not configured. Use configure_email first."
    try:
        import email

        import aioimaplib
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
        from atulya.sthaniya import LocalGGUFProvider
        provider = LocalGGUFProvider(_VISION_MODEL_PATH)
        if not provider.is_available():
            return "Vision model not available."
        prompts = {"ocr": "Extract ALL text from this image.", "objects": "List ALL objects visible.", "scene": "Describe the scene.", "analyze": "Describe what you see in detail."}
        prompt = prompts.get(task, prompts["analyze"])
        result = await provider.chat(prompt, system_prompt="You analyze images precisely. Be specific.")
        return result or "No analysis returned."
    except Exception as e:
        return f"Analysis failed: {e}"


# ── Tool: Calendar Skills ─────────────────────────────────────────────────

_CALENDAR: dict[str, dict[str, Any]] = {}


@tool("calendar_add", "Add an event to the calendar", {
    "title": {"type": "string", "description": "Event title"},
    "date": {"type": "string", "description": "Date/time: '2025-12-25 14:00' or 'tomorrow 3pm'"},
    "duration_minutes": {"type": "integer", "description": "Duration in minutes (default 60)", "default": 60},
    "description": {"type": "string", "description": "Optional description", "default": ""},
})
async def calendar_add(title: str, date: str, duration_minutes: int = 60, description: str = "") -> str:
    try:
        evt_time = _parse_time(date) if not re.match(r"\d{4}-\d{2}-\d{2}", date) else time.mktime(time.strptime(date[:10], "%Y-%m-%d")) + (int(date[11:13]) * 3600 + int(date[14:16]) * 60 if len(date) > 10 else 0)
    except Exception:
        evt_time = None
    if not evt_time:
        return f"Could not parse date: '{date}'. Use YYYY-MM-DD HH:MM or natural language."
    google = _google()
    if google is not None:
        from atulya.google import GoogleError

        try:
            await google.create_event(title, evt_time, duration_minutes, description)
        except GoogleError as exc:
            return f"Couldn't add it to Google Calendar: {exc}"
        return f"Added to Google Calendar: '{title}' on {time.strftime('%a %d %b at %H:%M', time.localtime(evt_time))}."
    eid = f"evt_{int(time.time() * 1000)}"
    entry = {"id": eid, "title": title, "time": evt_time, "duration": duration_minutes, "description": description, "created_at": time.time()}
    _CALENDAR[eid] = entry
    _save_json("calendar.json", list(_CALENDAR.values()))
    return f"Event added: '{title}' on {time.ctime(evt_time)} (id: {eid})"


@tool("calendar_list", "List upcoming calendar events", {
    "days": {"type": "integer", "description": "How many days ahead (default 7)", "default": 7},
})
async def calendar_list(days: int = 7) -> str:
    google = _google()
    if google is not None:
        from atulya.google import GoogleError, friendly_time

        try:
            events = await google.list_events(days)
        except GoogleError as exc:
            return f"Couldn't read Google Calendar: {exc}"
        if not events:
            return f"Nothing on your calendar in the next {days} day{'s' if days != 1 else ''}."
        return "\n".join(f"{i}. {e['title']} — {friendly_time(e['start'])}" + (f" at {e['location']}" if e['location'] else "")
                         + f" (id: {e['id']})" for i, e in enumerate(events, 1))
    now = time.time()
    cutoff = now + days * 86400
    upcoming = sorted([e for e in _CALENDAR.values() if now <= e["time"] <= cutoff], key=lambda x: x["time"])
    if not upcoming:
        return f"No events in the next {days} days."
    lines = []
    for i, e in enumerate(upcoming, 1):
        d = e.get("description", "")
        lines.append(f"{i}. {e['title']} — {time.ctime(e['time'])} ({e['duration']}min){' - '+d if d else ''}")
    return "\n".join(lines)


@tool("calendar_remove", "Remove a calendar event by ID", {
    "event_id": {"type": "string", "description": "Event ID from calendar_add or calendar_list"},
})
async def calendar_remove(event_id: str) -> str:
    google = _google()
    if google is not None and event_id not in _CALENDAR:
        from atulya.google import GoogleError

        try:
            await google.delete_event(event_id)
        except GoogleError as exc:
            return f"Couldn't delete it from Google Calendar: {exc}"
        return "Event removed from Google Calendar."
    if event_id in _CALENDAR:
        title = _CALENDAR[event_id]["title"]
        del _CALENDAR[event_id]
        _save_json("calendar.json", list(_CALENDAR.values()))
        return f"Event '{title}' removed."
    return f"Event {event_id} not found."


# ── Tool: Weather Skills ──────────────────────────────────────────────────

@tool("get_weather", "Get current weather for a location", {
    "location": {"type": "string", "description": "City name or 'lat,lon' coordinates"},
})
async def get_weather(location: str) -> str:
    try:
        import json as _json
        import urllib.request
        q = urllib.request.quote(location)
        url = f"https://wttr.in/{q}?format=j1"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = _json.loads(resp.read())
        cc = data["current_condition"][0]
        temp = cc["temp_C"]
        desc = cc["weatherDesc"][0]["value"]
        humidity = cc["humidity"]
        wind = cc["windspeedKmph"]
        return f"Weather in {location}: {desc}, {temp}°C, humidity {humidity}%, wind {wind} km/h"
    except Exception as e:
        return f"Could not get weather for '{location}': {e}"


@tool("get_forecast", "Get weather forecast for a location", {
    "location": {"type": "string", "description": "City name"},
    "days": {"type": "integer", "description": "Number of days (1-3, default 3)", "default": 3},
})
async def get_forecast(location: str, days: int = 3) -> str:
    try:
        import json as _json
        import urllib.request
        q = urllib.request.quote(location)
        days = max(1, min(3, days))
        url = f"https://wttr.in/{q}?format=j1"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = _json.loads(resp.read())
        lines = [f"Forecast for {location}:"]
        for day in data["weather"][:days]:
            date = day["date"]
            maxtemp = day["maxtempC"]
            mintemp = day["mintempC"]
            desc = day["hourly"][0]["weatherDesc"][0]["value"]
            lines.append(f"  {date}: {desc}, {mintemp}–{maxtemp}°C")
        return "\n".join(lines)
    except Exception as e:
        return f"Could not get forecast for '{location}': {e}"


# ── Tool: Home Automation (Home Assistant only; no pretend devices) ─────────────────

_HOME_DEVICES: dict[str, dict[str, Any]] = {
    "living_room_light": {"name": "Living Room Light", "type": "light", "state": "off", "brightness": 0},
    "kitchen_light": {"name": "Kitchen Light", "type": "light", "state": "off", "brightness": 0},
    "bedroom_light": {"name": "Bedroom Light", "type": "light", "state": "off", "brightness": 0},
    "thermostat": {"name": "Thermostat", "type": "thermostat", "state": "off", "temperature": 22},
    "front_door": {"name": "Front Door", "type": "lock", "state": "locked"},
}


def simulated_home() -> bool:
    """Pretend lights/locks exist. Off in real use; only the test suite turns it on (ATULYA_SIMULATED_HOME=on)."""
    return os.environ.get("ATULYA_SIMULATED_HOME", "").strip().lower() in ("1", "on", "true", "yes")


_NO_HUB = ("No smart-home hub is connected, so I can't control lights, locks or heaters that way. "
           "Add real devices with “scan for devices” (TVs, plugs, lights and more), or set HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN.")


@tool("home_list_devices", "List the devices in the connected Home Assistant hub", {})
async def home_list_devices() -> str:
    from atulya.upakaran import HomeAssistantBridge

    hub = HomeAssistantBridge().configured
    if not hub and not simulated_home():
        return _NO_HUB
    lines = ["Home Devices (connected to Home Assistant):" if hub else "Home Devices (simulated):"]
    for did, dev in _HOME_DEVICES.items():
        extra = ""
        if dev["type"] == "light":
            extra = f" (brightness: {dev.get('brightness', 0)}%)"
        elif dev["type"] == "thermostat":
            extra = f" (temp: {dev.get('temperature', 22)}°C)"
        lines.append(f"  {did}: {dev['name']} — {dev['state']}{extra}")
    return "\n".join(lines)


@tool("home_control", "Control a home automation device", {
    "device_id": {"type": "string", "description": "Device ID (use home_list_devices to see IDs)"},
    "action": {"type": "string", "description": "Action: 'on', 'off', 'lock', 'unlock', 'set_temperature', 'set_brightness'"},
    "value": {"type": "string", "description": "Optional value (e.g. temperature or brightness)", "default": ""},
})
async def home_control(device_id: str, action: str, value: str = "") -> str:
    # Real devices via Home Assistant only. Without a hub this says so, instead of pretending it worked.
    from atulya.upakaran import HomeAssistantBridge

    bridge = HomeAssistantBridge()
    if bridge.configured:
        try:
            result = await bridge.control(device_id, action, value)
        except Exception as exc:  # noqa: BLE001 - report the real failure, never fake success
            return f"Home Assistant couldn't do that: {exc}"
        if device_id in _HOME_DEVICES:
            _simulate_home_control(device_id, action, value)  # mirror state for the dashboard
        return result
    return _simulate_home_control(device_id, action, value) if simulated_home() else _NO_HUB


def _simulate_home_control(device_id: str, action: str, value: str = "") -> str:
    if device_id not in _HOME_DEVICES:
        available = ", ".join(_HOME_DEVICES.keys())
        return f"Device '{device_id}' not found. Available: {available}"
    dev = _HOME_DEVICES[device_id]
    if dev["type"] == "lock":
        if action in ("lock", "unlock"):
            dev["state"] = action + "ed" if action == "lock" else action + "ed"
            return f"{dev['name']} is now {dev['state']}."
        return f"Invalid action '{action}' for a lock. Use 'lock' or 'unlock'."
    if dev["type"] == "thermostat":
        if action == "set_temperature" and value:
            try:
                dev["temperature"] = int(value)
                dev["state"] = "on"
                return f"{dev['name']} set to {dev['temperature']}°C."
            except ValueError:
                return f"Invalid temperature: '{value}'."
        if action in ("on", "off"):
            dev["state"] = action
            return f"{dev['name']} turned {action}."
        return f"Invalid action '{action}' for thermostat."
    if dev["type"] == "light":
        if action == "set_brightness" and value:
            try:
                dev["brightness"] = max(0, min(100, int(value)))
                dev["state"] = "on" if dev["brightness"] > 0 else "off"
                return f"{dev['name']} brightness set to {dev['brightness']}%."
            except ValueError:
                return f"Invalid brightness: '{value}'."
        if action in ("on", "off"):
            dev["state"] = action
            dev["brightness"] = 100 if action == "on" else 0
            return f"{dev['name']} turned {action}."
        return f"Invalid action '{action}' for a light."
    return f"Unknown device type: {dev['type']}."


# ── Tool: Senses (cameras, doorbells) ────────────────────────────────────

@tool("camera_status", "What the cameras and door sensors have seen recently (is anyone at the door?)", {})
async def camera_status() -> str:
    from atulya.indriya import current_senses

    senses = current_senses()
    if senses is None:
        return "No cameras are set up yet. Add one under Admin → Senses."
    return senses.describe()


# ── Tool: Calculator / Utility Skills ─────────────────────────────────────

@tool("calculate", "Perform a calculation (safe math evaluation)", {
    "expression": {"type": "string", "description": "Math expression, e.g. '2 + 2 * 5'"},
})
async def calculate(expression: str) -> str:
    try:
        from atulya.ganana import safe_math_eval
        result = safe_math_eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"Could not calculate '{expression}': {e}"


@tool("current_time", "Get the current date and time", {
    "timezone": {"type": "string", "description": "Optional timezone (e.g. 'UTC', 'Asia/Kolkata')", "default": ""},
})
async def current_time(timezone: str = "") -> str:
    try:
        if timezone:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(timezone)
            now = time.localtime(time.time() + tz.utcoffset(None).total_seconds() if hasattr(tz, 'utcoffset') else 0)
        else:
            now = time.localtime()
        # Said aloud, so phrase it the way a person would.
        clock = time.strftime("%I:%M %p", now).lstrip("0")
        day = time.strftime("%A, %d %B", now).replace(" 0", " ")
        return f"It's {clock} on {day}" + (f" ({timezone})." if timezone else ".")
    except Exception:
        return f"Current time: {time.ctime()}"


# ── Tool: Open a website ───────────────────────────────────────────────────

# Spoken name -> (display name, home page, search URL or None).
WEBSITES: dict[str, tuple[str, str, str | None]] = {
    "youtube": ("YouTube", "https://www.youtube.com", "https://www.youtube.com/results?search_query={q}"),
    "google": ("Google", "https://www.google.com", "https://www.google.com/search?q={q}"),
    "gmail": ("Gmail", "https://mail.google.com", None),
    "maps": ("Google Maps", "https://maps.google.com", "https://www.google.com/maps/search/{q}"),
    "google maps": ("Google Maps", "https://maps.google.com", "https://www.google.com/maps/search/{q}"),
    "wikipedia": ("Wikipedia", "https://www.wikipedia.org", "https://en.wikipedia.org/w/index.php?search={q}"),
    "github": ("GitHub", "https://github.com", "https://github.com/search?q={q}"),
    "spotify": ("Spotify", "https://open.spotify.com", "https://open.spotify.com/search/{q}"),
    "whatsapp": ("WhatsApp", "https://web.whatsapp.com", None),
    "linkedin": ("LinkedIn", "https://www.linkedin.com", None),
    "twitter": ("X", "https://x.com", None),
    "instagram": ("Instagram", "https://www.instagram.com", None),
    "netflix": ("Netflix", "https://www.netflix.com", None),
    "amazon": ("Amazon", "https://www.amazon.in", "https://www.amazon.in/s?k={q}"),
    "chatgpt": ("ChatGPT", "https://chatgpt.com", None),
}


@tool("open_website", "Open a well-known website on this computer, optionally searching it", {
    "site": {"type": "string", "description": "Site name, e.g. 'youtube', 'google', 'gmail'"},
    "query": {"type": "string", "description": "Optional search text, e.g. 'lofi music'", "default": ""},
})
async def open_website(site: str, query: str = "") -> str:
    import urllib.parse
    import webbrowser

    entry = WEBSITES.get(site.strip().lower())
    if entry is None:
        return f"I don't know a website called {site}."
    label, home, search = entry
    query = query.strip()
    url = search.format(q=urllib.parse.quote_plus(query)) if query and search else home
    # Only URLs built from the fixed list above are ever opened.
    opened = await asyncio.to_thread(webbrowser.open, url)
    if not opened:
        return f"I couldn't open a browser on this computer. Here's the link: {url}"
    return f"Searching {label} for {query}." if query and search else f"Opening {label}."


# ── Load persisted state on import ─────────────────────────────────────────

def _bootstrap():
    from atulya.raksha import VaultLocked

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


# Skill modules register their tools with @tool on import.
from atulya import dhan, jaal, sahayak, upakaran_kriya  # noqa: E402,F401
