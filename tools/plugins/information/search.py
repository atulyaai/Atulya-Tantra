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
            trust_env=False,
            # Pinned IP URLs may serve different TLS hostnames. Never reuse a
            # connection authenticated for one original hostname for another.
            limits=httpx.Limits(max_keepalive_connections=0),
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

    Blocks private networks and the cloud metadata service (169.254.169.254), so a page,
    email or prompt can never make Atulya read internal addresses.
    """
    _, refused = await _public_target(url)
    return refused


async def _public_target(url: str) -> tuple[str | None, str | None]:
    """Resolve and validate once; the returned address is the actual connection target."""
    import asyncio
    import ipaddress
    import socket
    from urllib.parse import urlsplit

    try:
        parts = urlsplit(url)
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        return None, "invalid address"
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        return None, "only plain http(s) web addresses can be read"
    try:
        found = await asyncio.wait_for(
            asyncio.get_running_loop().getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM), timeout=5)
    except (OSError, asyncio.TimeoutError):
        return None, "that address does not resolve"
    addresses = []
    for *_rest, sockaddr in found:
        address = ipaddress.ip_address(sockaddr[0].split("%")[0])
        if getattr(address, "ipv4_mapped", None):
            address = address.ipv4_mapped
        if not address.is_global or address.is_multicast:
            return None, "internal and private addresses are never read"
        addresses.append(address)
    if not addresses:
        return None, "that address does not resolve"
    # Prefer IPv4 on hosts without working IPv6 routing.
    address = min(addresses, key=lambda item: item.version)
    return str(address), None


async def read_page(url: str) -> str:
    """Fetch and extract text from a public web page (redirects are checked hop by hop)."""
    client = _client()
    try:
        for _hop in range(5):
            address, refused = await _public_target(url)
            if refused:
                return f"I won't read that address: {refused}."
            original = httpx.URL(url)
            # Connect to the validated numeric address; do not resolve the
            # untrusted hostname a second time. Keep Host and TLS verification.
            target = original.copy_with(host=address)
            resp = await client.get(str(target), follow_redirects=False,
                                    headers={"Host": original.netloc.decode("ascii")},
                                    extensions={"sni_hostname": original.raw_host.decode("ascii")})
            if resp.is_redirect and resp.headers.get("location"):
                url = str(original.join(resp.headers["location"]))
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
