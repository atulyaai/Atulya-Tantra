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


async def briefing_news(city: str, topics: list[str] | None = None) -> list[dict]:
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
