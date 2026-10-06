"""Standing skills: system status, vision, calendar, weather, home, senses, calculator and opening sites."""
from __future__ import annotations

import asyncio
import os
import re
import time
from pathlib import Path
from typing import Any



from atulya import actions as _d

# ── Tool: System / Proactive Skills ────────────────────────────────────────


@_d.tool("get_system_status", "Get system health metrics", {})
async def get_system_status() -> str:
    import psutil
    cpu = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage(".")
    return (
        f"CPU: {cpu}% | RAM: {ram.percent}% ({ram.available / 1024**3:.1f} GB free) | "
        f"Disk: {disk.percent}% ({disk.free / 1024**3:.1f} GB free)"
    )


@_d.tool("get_proactive_suggestions", "Get context-aware suggestions", {
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


@_d.tool("download_vision_model", "Download the vision model (LLaVA, ~4.5 GB)", {
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


@_d.tool("analyze_image", "Analyze an image file (vision model required)", {
    "image_path": {"type": "string", "description": "Path to image file"},
    "task": {"type": "string", "description": "Task: 'analyze', 'ocr', 'objects', 'scene'", "default": "analyze"},
})
async def analyze_image(image_path: str, task: str = "analyze") -> str:
    if not _VISION_AVAILABLE or not _VISION_MODEL_PATH:
        return "Vision model not loaded. Use download_vision_model first."
    try:
        from atulya.brain import LocalGGUFProvider
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


@_d.tool("calendar_add", "Add an event to the calendar", {
    "title": {"type": "string", "description": "Event title"},
    "date": {"type": "string", "description": "Date/time: '2025-12-25 14:00' or 'tomorrow 3pm'"},
    "duration_minutes": {"type": "integer", "description": "Duration in minutes (default 60)", "default": 60},
    "description": {"type": "string", "description": "Optional description", "default": ""},
})
async def calendar_add(title: str, date: str, duration_minutes: int = 60, description: str = "") -> str:
    try:
        evt_time = _d._parse_time(date) if not re.match(r"\d{4}-\d{2}-\d{2}", date) else time.mktime(time.strptime(date[:10], "%Y-%m-%d")) + (int(date[11:13]) * 3600 + int(date[14:16]) * 60 if len(date) > 10 else 0)
    except Exception:
        evt_time = None
    if not evt_time:
        return f"Could not parse date: '{date}'. Use YYYY-MM-DD HH:MM or natural language."
    google = _d._google()
    if google is not None:
        from atulya.web import GoogleError

        try:
            await google.create_event(title, evt_time, duration_minutes, description)
        except GoogleError as exc:
            return f"Couldn't add it to Google Calendar: {exc}"
        return f"Added to Google Calendar: '{title}' on {time.strftime('%a %d %b at %H:%M', time.localtime(evt_time))}."
    eid = f"evt_{int(time.time() * 1000)}"
    entry = {"id": eid, "title": title, "time": evt_time, "duration": duration_minutes, "description": description, "created_at": time.time()}
    _d._CALENDAR[eid] = entry
    _d._save_json("calendar.json", list(_d._CALENDAR.values()))
    return f"Event added: '{title}' on {time.ctime(evt_time)} (id: {eid})"


@_d.tool("calendar_list", "List upcoming calendar events", {
    "days": {"type": "integer", "description": "How many days ahead (default 7)", "default": 7},
})
async def calendar_list(days: int = 7) -> str:
    google = _d._google()
    if google is not None:
        from atulya.web import GoogleError, friendly_time

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
    upcoming = sorted([e for e in _d._CALENDAR.values() if now <= e["time"] <= cutoff], key=lambda x: x["time"])
    if not upcoming:
        return f"No events in the next {days} days."
    lines = []
    for i, e in enumerate(upcoming, 1):
        d = e.get("description", "")
        lines.append(f"{i}. {e['title']} — {time.ctime(e['time'])} ({e['duration']}min){' - '+d if d else ''}")
    return "\n".join(lines)


@_d.tool("calendar_remove", "Remove a calendar event by ID", {
    "event_id": {"type": "string", "description": "Event ID from calendar_add or calendar_list"},
})
async def calendar_remove(event_id: str) -> str:
    google = _d._google()
    if google is not None and event_id not in _d._CALENDAR:
        from atulya.web import GoogleError

        try:
            await google.delete_event(event_id)
        except GoogleError as exc:
            return f"Couldn't delete it from Google Calendar: {exc}"
        return "Event removed from Google Calendar."
    if event_id in _d._CALENDAR:
        title = _d._CALENDAR[event_id]["title"]
        del _d._CALENDAR[event_id]
        _d._save_json("calendar.json", list(_d._CALENDAR.values()))
        return f"Event '{title}' removed."
    return f"Event {event_id} not found."


# ── Tool: Weather Skills ──────────────────────────────────────────────────

@_d.tool("get_weather", "Get current weather for a location", {
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


@_d.tool("get_forecast", "Get weather forecast for a location", {
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


@_d.tool("home_list_devices", "List the devices in the connected Home Assistant hub", {})
async def home_list_devices() -> str:
    from atulya.devices import HomeAssistantBridge

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


@_d.tool("home_control", "Control a home automation device", {
    "device_id": {"type": "string", "description": "Device ID (use home_list_devices to see IDs)"},
    "action": {"type": "string", "description": "Action: 'on', 'off', 'lock', 'unlock', 'set_temperature', 'set_brightness'"},
    "value": {"type": "string", "description": "Optional value (e.g. temperature or brightness)", "default": ""},
})
async def home_control(device_id: str, action: str, value: str = "") -> str:
    # Real devices via Home Assistant only. Without a hub this says so, instead of pretending it worked.
    from atulya.devices import HomeAssistantBridge

    bridge = HomeAssistantBridge()
    if bridge.configured:
        try:
            result = await bridge.control(device_id, action, value)
        except Exception as exc:  # noqa: BLE001 - report the real failure, never fake success
            return f"Home Assistant couldn't do that: {exc}"
        if device_id in _HOME_DEVICES:
            _d._simulate_home_control(device_id, action, value)  # mirror state for the dashboard
        return result
    return _d._simulate_home_control(device_id, action, value) if simulated_home() else _NO_HUB


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

@_d.tool("camera_status", "What the cameras and door sensors have seen recently (is anyone at the door?)", {})
async def camera_status() -> str:
    from atulya.vision import current_senses

    senses = current_senses()
    if senses is None:
        return "No cameras are set up yet. Add one under Admin → Senses."
    return senses.describe()


# ── Tool: Calculator / Utility Skills ─────────────────────────────────────

@_d.tool("calculate", "Perform a calculation (safe math evaluation)", {
    "expression": {"type": "string", "description": "Math expression, e.g. '2 + 2 * 5'"},
})
async def calculate(expression: str) -> str:
    try:
        from atulya.settings import safe_math_eval
        result = safe_math_eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"Could not calculate '{expression}': {e}"


@_d.tool("current_time", "Get the current date and time", {
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


@_d.tool("open_website", "Open a well-known website on this computer, optionally searching it", {
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


