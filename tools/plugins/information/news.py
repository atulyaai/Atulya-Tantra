"""BBC News RSS headline retrieval."""
import time
import xml.etree.ElementTree as ET

import httpx


_cache: tuple[float, bytes] | None = None
CACHE_SECONDS = 300


async def headlines(limit: int = 5) -> str:
    global _cache
    if _cache and time.monotonic() - _cache[0] < CACHE_SECONDS:
        content = _cache[1]
    else:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False, headers={"User-Agent": "Atulya/1.0"}) as client:
            response = await client.get("https://feeds.bbci.co.uk/news/rss.xml")
            response.raise_for_status()
        content = response.content
        _cache = (time.monotonic(), content)
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise RuntimeError("The news feed returned invalid RSS") from exc
    rows = []
    for item in root.findall("./channel/item")[:max(1, min(limit, 10))]:
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        if title:
            rows.append(f"• {title}" + (f" — {link}" if link else ""))
    if not rows:
        return "BBC News returned no headlines just now."
    return "Latest BBC News headlines:\n" + "\n".join(rows)
