"""BBC News RSS headline retrieval."""
import xml.etree.ElementTree as ET

import httpx


async def headlines(limit: int = 5) -> str:
    async with httpx.AsyncClient(timeout=10, follow_redirects=False, headers={"User-Agent": "Atulya/1.0"}) as client:
        response = await client.get("https://feeds.bbci.co.uk/news/rss.xml")
        response.raise_for_status()
    try:
        root = ET.fromstring(response.content)
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
