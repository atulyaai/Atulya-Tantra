"""Track things: a watchlist for prices, packages, flights or anything you want to keep an eye on."""
from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import time
import urllib.parse
import urllib.request
import uuid

from atulya.yantra import tools as _t
from atulya.yantra.tools import tool

_PRICE = re.compile(r"(?:₹|rs\.?|inr|\$|usd|€)\s?([\d,]+(?:\.\d+)?)", re.I)


def _load() -> list[dict]:
    data = _t._load_json("tracking.json")
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
    if not _is_public_url(url):
        raise ValueError("not a public web page")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Atulya"})
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - guarded by _is_public_url
        return resp.read(600_000).decode("utf-8", "replace")


def extract_price(html: str) -> float | None:
    m = _PRICE.search(html or "")
    return float(m.group(1).replace(",", "")) if m else None


@tool("track_add", "Start tracking something: a price on a web page, or a note like a package or flight", {
    "label": {"type": "string", "description": "What it is, e.g. 'iPhone price' or 'parcel to Delhi'"},
    "url": {"type": "string", "description": "Web page to watch (optional for plain notes)", "default": ""},
    "alert_below": {"type": "number", "description": "Alert when the price drops below this (optional)", "default": 0},
})
async def track_add(label: str, url: str = "", alert_below: float = 0) -> str:
    if url and not await asyncio.to_thread(_is_public_url, url):
        return "I can only watch public http(s) web pages."
    items = _load()
    item = {"id": uuid.uuid4().hex[:6], "label": label.strip(), "url": url, "alert_below": alert_below or None,
            "last": None, "checked": None}
    items.append(item)
    _t._save_json("tracking.json", items)
    return f"Tracking {item['label']} (id {item['id']})."


@tool("track_list", "List everything being tracked", {})
async def track_list() -> str:
    items = _load()
    if not items:
        return "You're not tracking anything."
    return "\n".join(f"{i['id']}: {i['label']}" + (f" — last seen {i['last']:g}" if i.get("last") is not None else "")
                     for i in items)


@tool("track_remove", "Stop tracking something", {
    "track_id": {"type": "string", "description": "The id from track_list"},
})
async def track_remove(track_id: str) -> str:
    items = _load()
    kept = [i for i in items if i["id"] != track_id]
    if len(kept) == len(items):
        return f"Nothing tracked with id {track_id}."
    _t._save_json("tracking.json", kept)
    return "Stopped tracking it."


@tool("track_check", "Check tracked web pages now and report prices or drops", {})
async def track_check() -> str:
    items = _load()
    notes: list[str] = []
    for item in items:
        if not item.get("url"):
            continue
        try:
            price = extract_price(await asyncio.to_thread(_fetch, item["url"]))
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
    _t._save_json("tracking.json", items)
    return "\n".join(notes) or "Nothing to check."
