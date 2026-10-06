"""Price tracking, the morning briefing, calendar watching and media control."""
from __future__ import annotations

import asyncio
import ipaddress
import os
import platform
import re
import socket
import time
import urllib.parse
import urllib.request
import uuid
import webbrowser
from datetime import datetime
from typing import Any



from atulya import actions as _d

# ── assistant ────────────────────────────────────────────────────────────
# ── tracking ────────────────────────────────────────────────────────────
_PRICE = re.compile(r"(?:₹|rs\.?|inr|\$|usd|€)\s?([\d,]+(?:\.\d+)?)", re.I)


def _load_watchlist() -> list[dict]:
    data = _d._t._load_json("tracking.json")
    return data if isinstance(data, list) else []


def _is_public_url(url: str) -> bool:
    """Only plain http(s) pages on the public internet — never the local network."""
    parts = urllib.parse.urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False
    try:
        for info in socket.getaddrinfo(parts.hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
    except (socket.gaierror, ValueError):
        return False
    return True


def _fetch(url: str) -> str:
    if not _d._is_public_url(url):
        raise ValueError("not a public web page")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Atulya"})
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - guarded by _d._is_public_url
        return resp.read(600_000).decode("utf-8", "replace")


def extract_price(html: str) -> float | None:
    m = _PRICE.search(html or "")
    return float(m.group(1).replace(",", "")) if m else None


@_d.tool("track_add", "Start tracking something: a price on a web page, or a note like a package or flight", {
    "label": {"type": "string", "description": "What it is, e.g. 'iPhone price' or 'parcel to Delhi'"},
    "url": {"type": "string", "description": "Web page to watch (optional for plain notes)", "default": ""},
    "alert_below": {"type": "number", "description": "Alert when the price drops below this (optional)", "default": 0},
})
async def track_add(label: str, url: str = "", alert_below: float = 0) -> str:
    if url and not await asyncio.to_thread(_d._is_public_url, url):
        return "I can only watch public http(s) web pages."
    items = _load_watchlist()
    item = {"id": uuid.uuid4().hex[:6], "label": label.strip(), "url": url, "alert_below": alert_below or None,
            "last": None, "checked": None}
    items.append(item)
    _d._t._save_json("tracking.json", items)
    return f"Tracking {item['label']} (id {item['id']})."


@_d.tool("track_list", "List everything being tracked", {})
async def track_list() -> str:
    items = _load_watchlist()
    if not items:
        return "You're not tracking anything."
    return "\n".join(f"{i['id']}: {i['label']}" + (f" — last seen {i['last']:g}" if i.get("last") is not None else "")
                     for i in items)


@_d.tool("track_remove", "Stop tracking something", {
    "track_id": {"type": "string", "description": "The id from track_list"},
})
async def track_remove(track_id: str) -> str:
    items = _load_watchlist()
    kept = [i for i in items if i["id"] != track_id]
    if len(kept) == len(items):
        return f"Nothing tracked with id {track_id}."
    _d._t._save_json("tracking.json", kept)
    return "Stopped tracking it."


@_d.tool("track_check", "Check tracked web pages now and report prices or drops", {})
async def track_check() -> str:
    items = _load_watchlist()
    notes: list[str] = []
    for item in items:
        if not item.get("url"):
            continue
        try:
            price = extract_price(await asyncio.to_thread(_d._fetch, item["url"]))
        except Exception as exc:  # noqa: BLE001
            notes.append(f"{item['label']}: couldn't check ({type(exc).__name__}).")
            continue
        if price is None:
            notes.append(f"{item['label']}: no price found on the page.")
            continue
        prev, item["last"], item["checked"] = item.get("last"), price, time.time()
        line = f"{item['label']}: {price:g}"
        if prev is not None and price < prev:
            line += f" (down from {prev:g})"
        if item.get("alert_below") and price <= item["alert_below"]:
            line += " — below your target!"
        notes.append(line)
    _d._t._save_json("tracking.json", items)
    return "\n".join(notes) or "Nothing to check."


# ── briefing ────────────────────────────────────────────────────────────
@_d.tool("morning_briefing", "Give a spoken briefing: time, weather, calendar, reminders and tracked items", {
    "location": {"type": "string", "description": "City for the weather (optional)", "default": ""},
})
async def morning_briefing(location: str = "") -> str:

    parts = [await _d._t.current_time()]
    if location.strip():
        parts.append(await _d._t.get_weather(location))
    parts.append("Calendar: " + await _d._t.calendar_list(1))
    parts.append("Reminders: " + await _d._t.list_reminders(24))
    tracked = await _d.tracking.track_check() if _d.tracking._load_watchlist() else ""
    if tracked:
        parts.append("Tracking:\n" + tracked)
    return "\n".join(p for p in parts if p)


@_d.tool("what_can_you_do", "Tell the user, briefly, what Atulya can do", {})
async def what_can_you_do() -> str:

    pc = "I can open apps and type for you when PC control is switched on." if _d.enabled() else \
        "PC control is off, but you can switch it on."
    return (
        "I can tell you the time and weather, set reminders, and manage your calendar and email. "
        "I can play music, pause, skip and change the volume, and track prices for you. "
        "Ask for your morning briefing any time. I can control smart home devices, see through a camera, "
        "and remember what you tell me. " + pc + " I always ask before doing anything risky."
    )


# ── calendar_watch ────────────────────────────────────────────────────────────

LEAD_MINUTES = int(os.environ.get("ATULYA_CALENDAR_LEAD_MIN", "10"))


def _to_ts(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        text = str(value)
        if "T" not in text:
            return None  # all-day events don't get a countdown
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


async def upcoming_events(window_minutes: int) -> list[dict[str, Any]]:
    """Events (local calendar plus Google, when connected) starting within the window."""

    now = time.time()
    end = now + window_minutes * 60
    found = [{"id": e["id"], "title": e["title"], "ts": float(e["time"])}
             for e in _d.tools._CALENDAR.values() if now < float(e["time"]) <= end]
    google = _d.tools._google()
    if google is not None:
        try:
            for e in await google.list_events(1):
                ts = _to_ts(e.get("start"))
                if ts and now < ts <= end:
                    found.append({"id": e["id"], "title": e["title"], "ts": ts})
        except Exception as exc:  # noqa: BLE001 - the watcher must never die
            _d.logger.debug("calendar watch (google) failed: %s", exc)
    return found


async def watch_calendar(events: Any, interval: float = 60.0, lead_minutes: int = LEAD_MINUTES) -> None:
    """Emit ``calendar.soon`` once per event when it is ``lead_minutes`` away or less."""
    announced: set[str] = set()
    while True:
        try:
            for e in await upcoming_events(lead_minutes):
                key = f"{e['id']}@{int(e['ts'])}"
                if key in announced:
                    continue
                announced.add(key)
                minutes = max(1, round((e["ts"] - time.time()) / 60))
                await events.emit("calendar.soon", {"id": e["id"], "title": e["title"], "minutes": minutes})
            if len(announced) > 500:
                announced.clear()
        except Exception as exc:  # noqa: BLE001
            _d.logger.debug("calendar watch failed: %s", exc)
        await asyncio.sleep(interval)


# ── media ────────────────────────────────────────────────────────────
# Windows virtual-key codes for the media keys.
_VK = {"play_pause": 0xB3, "next": 0xB0, "previous": 0xB1, "stop": 0xB2,
       "volume_up": 0xAF, "volume_down": 0xAE, "mute": 0xAD}


def _press(vk: int, times: int = 1) -> None:
    import ctypes

    for _ in range(times):
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)  # type: ignore[attr-defined]
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)  # type: ignore[attr-defined]


_VIDEO_ID = re.compile(r'"videoId":"([\w-]{11})"')


def _find_youtube_video(query: str) -> str | None:
    """Id of the top YouTube result for ``query`` (None when the page can't be read)."""
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310 - fixed https host
            html = resp.read(600_000).decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001 - fall back to the search page
        return None
    match = _VIDEO_ID.search(html)
    return match.group(1) if match else None


@_d.tool("play_music", "Play a song, artist or playlist: starts the top YouTube result (or opens a Spotify search)", {
    "query": {"type": "string", "description": "Song, artist or mood, e.g. 'arijit singh' or 'lofi beats'"},
    "service": {"type": "string", "description": "'youtube' or 'spotify'", "default": "youtube"},
})
async def play_music(query: str, service: str = "youtube") -> str:
    service = service.strip().lower()
    if service not in ("youtube", "spotify"):
        service = "youtube"
    query = query.strip()
    if not query:
        return "Tell me what to play."
    if service == "youtube":
        video = await asyncio.to_thread(_d._find_youtube_video, query)
        if video:
            url = f"https://www.youtube.com/watch?v={video}&autoplay=1"
            if await asyncio.to_thread(webbrowser.open, url):
                return f"Playing {query} on YouTube."
    return await _d.open_website(service, query)


@_d.tool("media_control", "Control playback on this computer: play_pause, next, previous, stop, volume_up, volume_down, mute", {
    "action": {"type": "string", "description": "play_pause | next | previous | stop | volume_up | volume_down | mute"},
    "amount": {"type": "integer", "description": "Repeat count, for volume steps", "default": 1},
})
async def media_control(action: str, amount: int = 1) -> str:
    action = action.strip().lower().replace(" ", "_")
    if action not in _VK:
        return f"I can do: {', '.join(_VK)}."
    if platform.system() != "Windows":
        return "Media keys are only wired up on Windows so far."
    await asyncio.to_thread(_press, _VK[action], max(1, min(int(amount or 1), 20)))
    return f"Done: {action.replace('_', ' ')}."


