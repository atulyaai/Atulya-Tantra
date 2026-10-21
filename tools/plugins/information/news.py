"""Attributed publisher RSS headlines; feed text is data, never instructions."""
import asyncio
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import httpx

_CACHE = {}
CACHE_SECONDS = 300
FEEDS = {
    "world": ("BBC News", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    "india": ("NDTV.com", "https://feeds.feedburner.com/ndtvnews-india-news"),
    "local": ("NDTV.com", "https://feeds.feedburner.com/ndtvnews-cities-news"),
}


def parse_items(content: bytes, source: str, city: str = "", now=None) -> list[dict]:
    root = ET.fromstring(content)
    now = now or datetime.now(timezone.utc)
    rows, seen = [], set()
    for item in root.findall("./channel/item"):
        title = " ".join(item.findtext("title", "").split())[:240]
        link = item.findtext("link", "").strip()
        parsed = urlsplit(link)
        if not title or parsed.scheme != "https" or not parsed.hostname or parsed.username or link in seen:
            continue
        stamp = item.findtext("pubDate", "").strip()
        try:
            published = parsedate_to_datetime(stamp)
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError, OverflowError):
            continue
        if published < now - timedelta(days=2) or published > now + timedelta(minutes=10):
            continue
        if city and not re.search(r"(?<!\w)" + re.escape(city.strip()) + r"(?!\w)", title, re.I):
            continue
        seen.add(link)
        rows.append({"title": title, "url": link, "source": source, "published": published.isoformat()})
    return rows


async def section(kind: str, city: str = "", limit: int = 2) -> dict:
    source, url = FEEDS[kind]
    try:
        cached = _CACHE.get(url)
        if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
            content = cached[1]
        else:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True, max_redirects=3,
                                         headers={"User-Agent": "Atulya/1.0"}) as client:
                response = await client.get(url)
                response.raise_for_status()
            content = response.content
            _CACHE[url] = (time.monotonic(), content)
        items = parse_items(content, source, city if kind == "local" else "")[:max(1, min(limit, 5))]
        return {"kind": kind, "source": source, "items": items,
                "status": "ready" if items else "no_recent_matching_headlines"}
    except (httpx.HTTPError, ET.ParseError, ValueError):
        return {"kind": kind, "source": source, "items": [], "status": "unavailable"}



SOURCES = {
    "zee_india": ("Zee News India", "https://zeenews.india.com/rss/india-national-news.xml"),
    "zee_world": ("Zee News World", "https://zeenews.india.com/rss/world-news.xml"),
    "ndtv_india": ("NDTV India", "https://feeds.feedburner.com/ndtvnews-india-news"),
    "ndtv_cities": ("NDTV Cities", "https://feeds.feedburner.com/ndtvnews-cities-news"),
    "bbc_world": ("BBC News", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    "bbc_india": ("BBC India", "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml"),
}
FEEDS.update(SOURCES)
ALIASES = {
    "zee": "zee_india", "zee news": "zee_india", "zee india": "zee_india", "zee news india": "zee_india",
    "zee world": "zee_world",
    "ndtv": "ndtv_india", "ndtv india": "ndtv_india",
    "bbc": "bbc_world", "bbc world": "bbc_world", "bbc news": "bbc_world", "bbc india": "bbc_india",
    "india": "ndtv_india", "world": "bbc_world", "local": "ndtv_cities",
}


def resolve_sources(value) -> list[str]:
    """Turn 'Zee News, BBC India' into known feed keys. Unknown names are rejected."""
    if isinstance(value, str):
        parts = [part.strip().lower() for part in value.replace(" and ", ",").split(",") if part.strip()]
    else:
        parts = [str(part).strip().lower() for part in value if str(part).strip()]
    found = []
    unknown = []
    for part in parts:
        key = part if part in SOURCES else ALIASES.get(part)
        if key is None:
            unknown.append(part)
        elif key not in found:
            found.append(key)
    if unknown or not found:
        names = ", ".join(sorted(SOURCES))
        raise ValueError(f"Unknown news source. Choose from: {names}")
    return found

async def briefing_news(city: str, topics: list[str] | None = None, sources: list[str] | None = None) -> list[dict]:
    if sources:
        wanted = [item for item in sources if item in FEEDS and item not in {"local", "india", "world"}]
        jobs = [section(key, limit=2) for key in wanted]
        return list(await asyncio.gather(*jobs)) if jobs else []
    wanted = [item for item in (topics or ["local", "india", "world"]) if item in FEEDS]
    jobs = []
    for kind in wanted:
        if kind == "local":
            jobs.append(section("local", city, 1) if city else _no_city())
        else:
            jobs.append(section(kind, limit=2))
    return list(await asyncio.gather(*jobs)) if jobs else []


async def _no_city():
    return {"kind": "local", "source": "", "items": [], "status": "city_not_set"}


async def headlines(limit: int = 5) -> str:
    data = await section("world", limit=limit)
    if not data["items"]:
        return "World headlines are unavailable right now; no current news was verified."
    return "🌍 World · BBC News\n" + "\n".join(
        f"• {item['title']} — {item['url']}" for item in data["items"])
