"""News: RSS/Atom feed lists and the watcher that announces new headlines."""
from __future__ import annotations

import asyncio
from typing import Any



from atulya import kriya as _d

# ── Watch: the news arrives instead of being fetched ────────────────────────

_NEWS_FEEDS_FILE = "news_feeds.json"
_NEWS_STATE_FILE = "news_state.json"
_NEWS_KEEP = 500   # remembered per feed, so a busy feed cannot grow the file
_NEWS_WINDOW = 30  # entries read per poll: more than any feed adds in five minutes


def _news_feeds() -> list[str]:
    data = _d._load_json(_NEWS_FEEDS_FILE)
    feeds = data.get("feeds") if isinstance(data, dict) else None
    return [str(url).strip() for url in (feeds or []) if str(url).strip()]


def _save_news_feeds(feeds: list[str]) -> None:
    _d._save_json(_NEWS_FEEDS_FILE, {"feeds": feeds})


def _news_state() -> dict:
    data = _d._load_json(_NEWS_STATE_FILE)
    return data if isinstance(data, dict) else {}


def _save_news_state(state: dict) -> None:
    _d._save_json(_NEWS_STATE_FILE, state)


def _feed_entries(feed_url: str) -> list[dict]:
    """One feed's newest entries. It goes out to the network, so it is only ever
    called through a thread -- feedparser has no async form and blocking the
    event loop here would stop chat, reminders and voice while a feed answers."""
    import feedparser

    parsed = feedparser.parse(feed_url)
    entries: list[dict] = []
    for entry in list(parsed.entries or [])[:_NEWS_WINDOW]:
        key = str(entry.get("id") or entry.get("link") or entry.get("title") or "").strip()
        if not key:
            continue
        entries.append({
            "key": key,
            "title": str(entry.get("title") or "(untitled)").strip()[:300],
            "link": str(entry.get("link") or ""),
        })
    return entries


async def _new_news(limit: int = 20) -> list[dict]:
    """Entries published since we began watching each feed.

    Subscribing must not shout a feed's back catalogue at anybody: the first
    poll records what is already there and says nothing, exactly as the inbox
    does. One feed that will not answer is skipped rather than being allowed
    to silence the rest, and entries beyond ``limit`` are deliberately left
    unremembered so the next tick takes them instead of dropping them.
    """
    feeds = _news_feeds()
    if not feeds:
        return []
    remembered = _news_state().get("feeds") or {}
    fresh: list[dict] = []
    changed: dict[str, Any] = {}
    for url in feeds:
        try:
            entries = await asyncio.to_thread(_d._feed_entries, url)
        except Exception as exc:  # noqa: BLE001 - one dead feed must not stop the others
            _d.logger.warning("news feed failed (%s): %s", url, exc)
            continue
        prior = remembered.get(url) if isinstance(remembered.get(url), dict) else {}
        seen = {str(key) for key in (prior.get("seen") or [])}
        first_poll = url not in remembered
        for entry in entries:
            if entry["key"] in seen:
                continue
            if first_poll or len(fresh) >= limit:
                if first_poll:
                    seen.add(entry["key"])  # history, not news
                continue
            fresh.append({**entry, "feed": url})
            seen.add(entry["key"])
        changed[url] = {
            "seen": sorted(seen)[-_NEWS_KEEP:],
            "latest": [{"title": e["title"], "link": e["link"]} for e in entries[:10]],
        }
    if changed:
        _save_news_state({**_news_state(), "feeds": {**remembered, **changed}})
    return fresh


async def watch_news(events: Any, interval: float = 300.0, limit: int = 20) -> None:
    """Emit ``news.new`` once per entry that appeared after we started watching.

    ``news_latest`` only answers when somebody asks, and a headline that waits
    to be asked about is a bookmark rather than news. With no feeds subscribed
    the loop costs one list read per five minutes and reaches for nothing.
    """
    failed: str | None = None
    while True:
        try:
            for entry in await _d._new_news(limit):
                await events.emit("news.new", {
                    "title": entry["title"],
                    "feed": entry["feed"],
                    "link": entry["link"],
                })
            failed = None
        except Exception as exc:  # noqa: BLE001 - the watcher must never die
            text = f"{type(exc).__name__}: {exc}"
            if text == failed:  # the same fault, all day, is noise
                _d.logger.debug("news watch failed: %s", text)
            else:
                _d.logger.warning("news watch failed: %s", text)
                failed = text
        await asyncio.sleep(interval)


@_d.tool("news_add_feed", "Subscribe to an RSS or Atom news feed", {
    "url": {"type": "string", "description": "Feed address, e.g. https://feeds.bbci.co.uk/news/rss.xml"},
})
async def news_add_feed(url: str) -> str:
    url = str(url).strip()
    if not url.startswith(("http://", "https://")):
        return "A feed needs an http:// or https:// address."
    feeds = _news_feeds()
    if url in feeds:
        return f"Already watching {url}."
    state = _news_state()
    remembered = dict(state.get("feeds") or {})
    remembered.pop(url, None)  # coming back to a feed starts a fresh baseline
    _save_news_state({**state, "feeds": remembered})
    _save_news_feeds(feeds + [url])
    return f"Now watching {url} ({len(feeds) + 1} feeds in total)."


@_d.tool("news_remove_feed", "Stop watching a news feed", {
    "url": {"type": "string", "description": "Feed address to stop watching"},
})
async def news_remove_feed(url: str) -> str:
    url = str(url).strip()
    feeds = _news_feeds()
    if url not in feeds:
        return "That feed was not being watched."
    _save_news_feeds([item for item in feeds if item != url])
    state = _news_state()
    remembered = dict(state.get("feeds") or {})
    remembered.pop(url, None)
    _save_news_state({**state, "feeds": remembered})
    return f"Stopped watching {url}."


@_d.tool("news_latest", "List the subscribed news feeds and their newest headlines", {})
async def news_latest() -> str:
    feeds = _news_feeds()
    if not feeds:
        return "No news feeds yet. Use news_add_feed to subscribe to one."
    remembered = _news_state().get("feeds") or {}
    lines: list[str] = []
    for url in feeds:
        entries = (remembered.get(url) or {}).get("latest") or []
        lines.append(url)
        lines.extend(f"  - {entry.get('title')}" for entry in entries)
    return "Watching:\n" + "\n".join(lines)


