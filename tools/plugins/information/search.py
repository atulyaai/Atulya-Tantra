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


async def read_page(url: str) -> str:
    """Fetch and extract text from a web page."""
    client = _client()
    try:
        resp = await client.get(url, follow_redirects=True)
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
