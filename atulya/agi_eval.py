"""One daily probe. A pass here does not raise the AGI score.

The probe is hand-written, so the result is stored with novel=false. The score moves only
when a task that was not written for this harness is recorded with novel=true.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

PROBE_ID = "exact-token"
PROBE_PROMPT = "Reply with exactly KAPOK-19 and no other words."
PROBE_EXPECT = "KAPOK-19"


def judge(text: str, expect: str = PROBE_EXPECT) -> bool:
    return text.strip() == expect


def _path(data_dir) -> Path:
    return Path(data_dir) / "novel_tasks.jsonl"


def already_today(data_dir) -> bool:
    today = datetime.now().astimezone().date().isoformat()
    try:
        lines = _path(data_dir).read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        return str(row.get("at", "")).startswith(today) and row.get("id") == PROBE_ID
    return False


def record(data_dir, *, passed: bool, answer: str, reason: str) -> dict:
    row = {
        "id": PROBE_ID,
        "novel": False,
        "passed": passed,
        "answer": answer[:300],
        "reason": reason[:200],
        "at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    path = _path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    return row


async def run_daily_probe(data_dir, brain) -> dict | None:
    if already_today(data_dir):
        return None
    if brain is None:
        return record(data_dir, passed=False, answer="", reason="no model configured")
    from tools.plugins.brain.types import Message
    try:
        reply = await brain.respond(
            [Message(role="user", content=PROBE_PROMPT)],
            system_instructions="Follow the user message exactly. Add nothing.",
        )
    except Exception as exc:
        return record(data_dir, passed=False, answer="", reason=type(exc).__name__)
    passed = judge(reply.text)
    return record(data_dir, passed=passed, answer=reply.text, reason="exact match" if passed else "not exact")
