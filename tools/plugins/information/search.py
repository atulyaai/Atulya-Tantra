"""Web search with sources using DuckDuckGo's free API."""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger(__name__)

_search_client: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _search_client
    if _search_client is None or _search_client.is_closed:
        _search_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10, connect=5),
            headers={"User-Agent": "Atulya-Tantra/1.0"},
        )
    return _search_client


# DuckDuckGo's safe-search parameter: 1 strict, -1 moderate, -2 off (PLAN M12-6).
SAFESEARCH_KP = {"strict": "1", "moderate": "-1", "off": "-2"}


async def search_web(query: str, limit: int = 5, *, safesearch: str = "moderate") -> list[dict]:
    """Search the web using DuckDuckGo's instant answer API."""
    client = _client()
    try:
        resp = await client.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1,
                    "kp": SAFESEARCH_KP.get(safesearch, "1")},
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Web search failed: %s", type(exc).__name__)
        return []
    results = []
    # Related topics
    for topic in data.get("RelatedTopics", [])[:limit]:
        if isinstance(topic, dict) and "Text" in topic:
            results.append({
                "title": topic.get("Text", "")[:100],
                "url": topic.get("FirstURL", ""),
                "snippet": topic.get("Text", "")[:200],
            })
    # Abstract
    abstract = data.get("AbstractText", "")
    if abstract:
        results.insert(0, {
            "title": data.get("Heading", query),
            "url": data.get("AbstractURL", ""),
            "snippet": abstract[:300],
        })
    return results[:limit]


MAX_REDIRECTS = 3


class BlockedURL(ValueError):
    """The URL points somewhere read_url must not fetch (non-https or a non-public address)."""


async def _check_public(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise BlockedURL("only https:// pages can be read")
    host = parsed.hostname
    if not host:
        raise BlockedURL("the URL has no host")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            infos = await asyncio.get_running_loop().getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise BlockedURL(f"could not resolve {host}") from exc
        addresses = [ipaddress.ip_address(info[4][0].split("%", 1)[0]) for info in infos]
    if not addresses or any(not address.is_global for address in addresses):
        raise BlockedURL(f"{host} is not a public internet address")


async def read_page(url: str, *, client: httpx.AsyncClient | None = None) -> str:
    """Fetch and extract text from a public https web page; every redirect hop is re-checked."""
    client = client or _client()
    try:
        for _hop in range(MAX_REDIRECTS + 1):
            await _check_public(url)
            resp = await client.get(url, follow_redirects=False)
            if not resp.is_redirect:
                break
            url = str(resp.url.join(resp.headers.get("location", "")))
        else:
            return "I couldn't read that page (too many redirects)."
        resp.raise_for_status()
    except BlockedURL as exc:
        return f"I won't read that page: {exc}."
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Page fetch failed: %s", type(exc).__name__)
        return f"I couldn't read that page ({type(exc).__name__})."
    # Simple text extraction: strip HTML tags
    import re
    text = resp.text
    # Remove script/style blocks
    text = re.sub(r"<(script|style)[^>]*>[^<]*</\1>", "", text, flags=re.I | re.S)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text[:3000] if text else "The page had no readable text."
