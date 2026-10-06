"""The filesystem watchdog (and the feedback log it sits next to)."""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any



from atulya import actions as _d

# ── Watch: file system changes arrive as events ────────────────────────────

_WATCHDOG_CONFIG_FILE = "watchdog_config.json"
_WATCHDOG_STATE_FILE = "watchdog_state.json"


def _watchdog_config() -> dict:
    data = _d._load_json(_WATCHDOG_CONFIG_FILE)
    return data if isinstance(data, dict) else {}


def _save_watchdog_config(cfg: dict) -> None:
    _d._save_json(_WATCHDOG_CONFIG_FILE, cfg)


def _watchdog_state() -> dict:
    data = _d._load_json(_WATCHDOG_STATE_FILE)
    return data if isinstance(data, dict) else {}


def _save_watchdog_state(state: dict) -> None:
    _d._save_json(_WATCHDOG_STATE_FILE, state)


async def watch_filesystem(events: Any, paths: list[str] | None = None,
                           recursive: bool = True, patterns: list[str] | None = None) -> None:
    """Watch directories for file changes and emit `file.changed` events.

    Configuration is read from `watchdog_config.json` (created by `watchdog_configure`)
    and can be overridden by arguments. If no paths are configured the watcher
    idles instead of failing.
    """
    cfg = _watchdog_config()
    watch_paths = paths or cfg.get("paths", [])
    if not watch_paths:
        _d.logger.debug("Watchdog: no paths configured, idling")
        while True:
            await asyncio.sleep(3600)

    recursive = recursive if paths is None else recursive
    if "recursive" in cfg and paths is None:
        recursive = bool(cfg.get("recursive", True))

    watch_patterns = patterns or cfg.get("patterns", None)

    from watchdog.observers import Observer
    from watchdog.events import PatternMatchingEventHandler

    handler = PatternMatchingEventHandler(
        patterns=watch_patterns,
        ignore_patterns=None,
        ignore_directories=False,
        case_sensitive=False,
    )

    loop = asyncio.get_event_loop()
    debounce: dict[str, float] = {}

    def on_any_event(event):
        if event.is_directory:
            return
        now = time.time()
        key = event.src_path
        if key in debounce and now - debounce[key] < 0.5:
            return
        debounce[key] = now
        asyncio.run_coroutine_threadsafe(
            events.emit("file.changed", {
                "path": event.src_path,
                "event_type": event.event_type,  # created, modified, deleted, moved
                "is_directory": event.is_directory,
            }),
            loop,
        )

    handler.on_created = on_any_event
    handler.on_modified = on_any_event
    handler.on_deleted = on_any_event
    handler.on_moved = lambda e: (on_any_event(e), on_any_event(type('obj', (), {'src_path': e.dest_path, 'is_directory': e.is_directory, 'event_type': 'created'})()))

    observer = Observer()
    for path in watch_paths:
        if os.path.exists(path):
            observer.schedule(handler, path, recursive=recursive)
        else:
            _d.logger.warning("Watchdog path does not exist: %s", path)

    observer.start()
    _d.logger.info("Watchdog watching %s (recursive=%s)", watch_paths, recursive)

    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        observer.stop()
        observer.join()
        raise
    except Exception:  # noqa: BLE001
        observer.stop()
        observer.join()
        raise


@_d.tool("watchdog_configure", "Configure filesystem watcher (watchdog)", {
    "paths": {"type": "array", "items": {"type": "string"}, "description": "Directories to watch", "default": []},
    "recursive": {"type": "boolean", "description": "Watch subdirectories recursively", "default": True},
    "patterns": {"type": "array", "items": {"type": "string"}, "description": "Glob patterns to match (optional)", "default": []},
})
async def watchdog_configure(paths: list[str] = None, recursive: bool = True, patterns: list[str] = None) -> str:
    paths = [str(p).strip() for p in (paths or []) if str(p).strip()]
    if not paths:
        return "At least one path is required."
    for p in paths:
        if not os.path.exists(p):
            return f"Path does not exist: {p}"
    _save_watchdog_config({
        "paths": paths,
        "recursive": bool(recursive),
        "patterns": [str(p).strip() for p in (patterns or []) if str(p).strip()] or None
    })
    return f"Watchdog configured: {', '.join(paths)} (recursive={recursive})"


@_d.tool("watchdog_status", "Show filesystem watcher configuration", {})
async def watchdog_status() -> str:
    cfg = _watchdog_config()
    if not cfg.get("paths"):
        return "Watchdog not configured. Use watchdog_configure to add paths."
    return (f"Paths: {', '.join(cfg.get('paths', []))}\n"
            f"Recursive: {cfg.get('recursive', True)}\n"
            f"Patterns: {cfg.get('patterns') or '(all)'}")

_FEEDBACK_FILE = "feedback.json"
_FEEDBACK_KEEP = 200  # enough to notice a pattern, small enough to quote per turn


def _feedback_entries() -> list[dict]:
    data = _d._load_json(_FEEDBACK_FILE)
    entries = data.get("entries") if isinstance(data, dict) else None
    return [dict(item) for item in (entries or []) if isinstance(item, dict)]


def record_feedback(rating: str, prompt: str = "", reply: str = "", comment: str = "") -> dict:
    """Remember how a reply landed.

    Both directions are kept, but only the complaints become instructions:
    being told an answer was good does not say what to repeat, whereas a
    complaint does. The question is stored alongside so a lesson can name
    what it was about instead of floating free of any context.
    """
    liked = str(rating or "").strip().lower() in ("up", "good", "like", "+", "1", "yes")
    entries = _feedback_entries()
    entries.append({
        "rating": "up" if liked else "down",
        "prompt": str(prompt or "")[:500],
        "reply": str(reply or "")[:500],
        "comment": str(comment or "")[:500],
        "at": time.time(),
    })
    kept = entries[-_FEEDBACK_KEEP:]
    _d._save_json(_FEEDBACK_FILE, {"entries": kept})
    tally = {"up": 0, "down": 0}
    for item in kept:
        tally[item["rating"]] = tally.get(item["rating"], 0) + 1
    return {**tally, "last": kept[-1]["rating"]}


def feedback_notes(limit: int = 3) -> str:
    """The recent thumbs-down, phrased as something to avoid. Empty if none.

    Sent with the turn rather than in the system prompt: that prompt is held
    byte-stable so llama.cpp can reuse its KV cache, and feedback arrives
    between turns, so putting it there would cost a full re-prefill every time
    somebody pressed a button.
    """
    downs = [item for item in _feedback_entries() if item.get("rating") == "down"]
    if not downs:
        return ""
    lines = ["The user has recently marked answers as wrong. Do not answer like that:"]
    for item in downs[-limit:]:
        question = str(item.get("prompt") or "").strip()
        said = str(item.get("comment") or "").strip()
        if question:
            lines.append(f'- To "{question[:120]}"')
        if said:
            lines.append(f"  they said: {said[:160]}")
        if not question and not said:
            lines.append("- They marked an earlier answer wrong without saying why")
    return "\n".join(lines)


@_d.tool("feedback_record", "Record whether an answer was helpful", {
    "rating": {"type": "string", "description": "\"up\" if they liked it, \"down\" if they did not"},
    "comment": {"type": "string", "description": "What they said about it", "default": ""},
    "prompt": {"type": "string", "description": "The question it answered", "default": ""},
    "reply": {"type": "string", "description": "The answer that was given", "default": ""},
})
async def feedback_record(rating: str, comment: str = "", prompt: str = "", reply: str = "") -> str:
    """So a complaint works by voice as well as by pressing a button."""
    tally = record_feedback(rating, prompt, reply, comment)
    return f"Noted. {tally['up']} good, {tally['down']} bad so far."



