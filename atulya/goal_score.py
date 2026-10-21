"""Live Jarvis score and an honest AGI score.

Jarvis points are checks against this machine. AGI points stay at zero until a task
succeeds that was not hand-coded. A document cannot raise that score.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


def _check(name: str, ok: bool, detail: str, group: str) -> dict:
    return {"name": name, "ok": bool(ok), "detail": detail, "group": group}


def score(data_dir, env: dict | None = None) -> dict:
    data = Path(data_dir)
    env = env if env is not None else os.environ
    if env is os.environ:
        try:
            from dotenv import load_dotenv
            from atulya.settings import PROJECT_ROOT
            load_dotenv(PROJECT_ROOT / ".env", override=False)
        except Exception:
            pass
    checks = []

    def briefing():
        try:
            from atulya.profiles import ProfileStore
            return ProfileStore(data).briefing_settings("admin")
        except Exception as exc:
            return {"error": type(exc).__name__}

    settings = briefing()
    sources = settings.get("sources") or [] if isinstance(settings, dict) else []
    checks.append(_check(
        "news_source", bool(sources),
        "sources: " + ", ".join(sources) if sources else "no news source saved", "jarvis"))
    routines = []
    try:
        routines = json.loads((data / "routines.json").read_text(encoding="utf-8")).get("items") or []
    except (OSError, ValueError):
        routines = []
    enabled = [item.get("name") for item in routines if item.get("enabled")]
    checks.append(_check("routines", bool(enabled), ", ".join(enabled) or "none enabled", "jarvis"))
    lessons = []
    try:
        lessons = json.loads((data / "lessons.json").read_text(encoding="utf-8")).get("items") or []
    except (OSError, ValueError):
        lessons = []
    checks.append(_check("learns_corrections", bool(lessons), f"{len(lessons)} saved rule(s)", "jarvis"))
    devices = []
    try:
        import sqlite3
        with sqlite3.connect(data / "agents.sqlite3") as db:
            devices = db.execute(
                "SELECT name, seen FROM devices WHERE revoked=0").fetchall()
    except Exception:
        devices = []
    online = [name for name, seen in devices if seen and time.time() - float(seen) < 90]
    checks.append(_check(
        "device_paired", bool(devices),
        ", ".join(name for name, _seen in devices) or "none paired", "jarvis"))
    checks.append(_check(
        "device_online", bool(online),
        ", ".join(online) if online else "paired devices are not polling", "jarvis"))
    checks.append(_check(
        "telegram", bool(env.get("ATULYA_TELEGRAM_BOT_TOKEN", "").strip()),
        "token configured" if env.get("ATULYA_TELEGRAM_BOT_TOKEN") else "no bot token", "jarvis"))
    checks.append(_check(
        "acts_outside", False,
        "SMS, calls and the laptop still need a live approval receipt", "jarvis"))

    novel = data / "novel_tasks.jsonl"
    passed = 0
    try:
        for line in novel.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("passed") and row.get("novel") is True:
                passed += 1
    except (OSError, ValueError):
        passed = 0
    checks.append(_check("novel_tasks", passed > 0, f"{passed} unscripted task(s) passed", "agi"))
    checks.append(_check("weights_changed", False, "no fine-tune has been run", "agi"))
    checks.append(_check(
        "self_code", False, "repairs do not edit code unless you approve a proposal", "agi"))

    jarvis = [item for item in checks if item["group"] == "jarvis"]
    agi = [item for item in checks if item["group"] == "agi"]
    return {
        "jarvis": f"{sum(item['ok'] for item in jarvis)}/{len(jarvis)}",
        "agi": f"{sum(item['ok'] for item in agi)}/{len(agi)}",
        "meaning": "Jarvis is this product. AGI stays 0 until an unscripted task passes. A goal file cannot raise it.",
        "checks": checks,
    }


def render(report: dict) -> str:
    lines = [f"Jarvis {report['jarvis']}. AGI {report['agi']}.", report["meaning"]]
    for item in report["checks"]:
        mark = "pass" if item["ok"] else "fail"
        lines.append(f"- {item['group']} {item['name']}: {mark}. {item['detail']}")
    return "\n".join(lines)
