"""Web search with sources using DuckDuckGo's free API."""
from __future__ import annotations

import logging

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


async def search_web(query: str, limit: int = 5) -> list[dict]:
    """Search the web using DuckDuckGo's instant answer API."""
    client = _client()
    try:
        resp = await client.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
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


async def public_address(url: str) -> str | None:
    """Why a URL must not be fetched, or None when it points only at the public internet.

    Blocks this server, its private network and the cloud metadata service (169.254.169.254), so a page,
    email or prompt can never make Atulya read internal addresses.
    """
    import asyncio
    import ipaddress
    import socket
    from urllib.parse import urlsplit

    try:
        parts = urlsplit(url)
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        return "invalid address"
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        return "only plain http(s) web addresses can be read"
    try:
        found = await asyncio.get_running_loop().getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM)
    except OSError:
        return "that address does not resolve"
    for *_rest, sockaddr in found:
        address = ipaddress.ip_address(sockaddr[0].split("%")[0])
        if getattr(address, "ipv4_mapped", None):
            address = address.ipv4_mapped
        if not address.is_global or address.is_multicast:
            return "internal and private addresses are never read"
    return None


async def read_page(url: str) -> str:
    """Fetch and extract text from a public web page (redirects are checked hop by hop)."""
    client = _client()
    try:
        for _hop in range(5):
            refused = await public_address(url)
            if refused:
                return f"I won't read that address: {refused}."
            resp = await client.get(url, follow_redirects=False)
            if resp.is_redirect and resp.headers.get("location"):
                url = str(resp.next_request.url) if resp.next_request else str(httpx.URL(url).join(resp.headers["location"]))
                continue
            break
        else:
            return "That page redirects too many times."
        resp.raise_for_status()
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
