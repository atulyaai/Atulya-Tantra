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
            from atulya.settings import PROJECT_ROOT, Settings
            from atulya.secrets_store import load_protected
            load_dotenv(PROJECT_ROOT / ".env", override=False)
            load_protected(Settings.from_environment().data_dir)
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
        "scripted feeds: " + ", ".join(sources) if sources else "no news source saved", "jarvis"))
    routines = []
    try:
        routines = json.loads((data / "routines.json").read_text(encoding="utf-8")).get("items") or []
    except (OSError, ValueError):
        routines = []
    enabled = [item.get("name") for item in routines if item.get("enabled")]
    checks.append(_check("routines", bool(enabled), (", ".join(enabled) or "none enabled") + " — scripted schedules, not a decision", "jarvis"))
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
    if online:
        online_detail = ", ".join(online)
    elif devices:
        ages = []
        for name, seen in devices:
            if not seen:
                ages.append(f"{name} has never polled")
            else:
                ages.append(f"{name} last polled {int((time.time() - float(seen)) // 60)} min ago")
        online_detail = "; ".join(ages) + ". Open the phone app and leave it connected."
    else:
        online_detail = "paired devices are not polling"
    checks.append(_check(
        "device_paired", bool(devices),
        ", ".join(name for name, _seen in devices) or "none paired", "jarvis"))
    checks.append(_check("device_online", bool(online), online_detail, "jarvis"))
    checks.append(_check(
        "telegram", bool(env.get("ATULYA_TELEGRAM_BOT_TOKEN", "").strip()),
        "token configured" if env.get("ATULYA_TELEGRAM_BOT_TOKEN") else "no bot token", "jarvis"))
    acted = []
    try:
        import sqlite3
        with sqlite3.connect(data / "agents.sqlite3") as db:
            acted = [row[0] for row in db.execute(
                "SELECT DISTINCT kind FROM jobs WHERE status=\"executed\"" )]
    except Exception:
        acted = []
    outside = {"send_sms", "place_call", "open_app", "open_url", "say", "display_message"}
    done = sorted(set(acted) & outside)
    checks.append(_check(
        "acts_outside", bool(done),
        "receipts: " + ", ".join(done) if done else
        "phone answered " + (", ".join(sorted(set(acted))) or "nothing") + "; no SMS, call, app or laptop receipt yet",
        "jarvis"))

    proposals = []
    try:
        for path in (data / "maintenance").glob("*.json"):
            proposals.append(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        proposals = []
    findings = []
    try:
        findings = json.loads((data / "maintenance-last.json").read_text(encoding="utf-8")).get("findings") or []
    except (OSError, ValueError):
        findings = []
    proposed = [item for item in proposals if item.get("state") in {"proposed", "applied"}]
    applied = [item for item in proposals if item.get("state") == "applied"]
    checks.append(_check(
        "finds_issues", bool(findings),
        f"{len(findings)} issue(s) found by the server check" if findings else "the server check has not recorded an issue",
        "agi"))
    checks.append(_check(
        "proposes_fix", bool(proposed),
        f"{len(proposed)} code proposal(s) waiting or applied" if proposed else "no code proposal has been written",
        "agi"))
    checks.append(_check(
        "applies_fix", bool(applied),
        f"{len(applied)} approved edit(s) applied" if applied else "nothing is edited until you approve a proposal",
        "agi"))

    jarvis = [item for item in checks if item["group"] == "jarvis"]
    agi = [item for item in checks if item["group"] == "agi"]
    return {
        "jarvis": f"{sum(item['ok'] for item in jarvis)}/{len(jarvis)}",
        "agi": f"{sum(item['ok'] for item in agi)}/{len(agi)}",
        "meaning": "Jarvis checks are scripted features, not a mind. AGI moves only when the server finds an issue, writes a fix, and you approve it. Model weights are not scored.",
        "checks": checks,
    }


def render(report: dict) -> str:
    lines = [f"Jarvis {report['jarvis']}. AGI {report['agi']}.", report["meaning"]]
    for item in report["checks"]:
        mark = "pass" if item["ok"] else "fail"
        lines.append(f"- {item['group']} {item['name']}: {mark}. {item['detail']}")
    return "\n".join(lines)
