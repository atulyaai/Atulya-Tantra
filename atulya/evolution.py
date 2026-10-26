"""Standing rules learned from the owner, plus a repair pass over recent tool failures.

This does not retrain a model and it does not edit its own code. A learned rule is read on the
next reply. Repeated failures become a rule to tell the truth and the next step.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

_MAX = 40
_TEXT = 280


class Lessons:
    def __init__(self, data_dir: Path) -> None:
        self.path = Path(data_dir) / "lessons.json"

    def _load(self) -> list[dict]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        items = data.get("items") if isinstance(data, dict) else None
        return [item for item in items or [] if isinstance(item, dict) and item.get("text")]

    def _save(self, items: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"items": items[-_MAX:]}), encoding="utf-8")

    def active(self, user_id: str) -> list[dict]:
        return [item for item in self._load() if item.get("user_id") == user_id][-12:]

    def add(self, user_id: str, text: str, source: str = "user") -> dict:
        cleaned = " ".join(str(text).split())[:_TEXT]
        if len(cleaned) < 8:
            raise ValueError("Say the rule in at least a short sentence.")
        items = self._load()
        for item in items:
            if item.get("user_id") == user_id and item.get("text", "").lower() == cleaned.lower():
                return item
        item = {"id": datetime.now().strftime("%H%M%S%f")[:10], "user_id": user_id,
                "text": cleaned, "source": source if source in {"user", "repair"} else "user",
                "at": datetime.now().astimezone().isoformat(timespec="seconds")}
        items.append(item)
        own = [row for row in items if row.get("user_id") == user_id]
        if len(own) > _MAX:
            drop = {row["id"] for row in own[:-_MAX]}
            items = [row for row in items if row.get("id") not in drop or row.get("user_id") != user_id]
        self._save(items)
        return item

    def forget(self, user_id: str, query: str) -> int:
        needle = query.strip().lower()
        items = self._load()
        kept = []
        removed = 0
        for item in items:
            if item.get("user_id") != user_id:
                kept.append(item)
                continue
            if item.get("id") == query.strip() or needle and needle in item.get("text", "").lower():
                removed += 1
                continue
            kept.append(item)
        if removed:
            self._save(kept)
        return removed


def capture_order(data_dir, user_id: str, text: str) -> str:
    """Save a standing 'don't' from the user. A bare 'stop the music' is a command, not a rule."""
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) < 12 or len(cleaned) > _TEXT or cleaned.endswith("?"):
        return ""
    if not re.search(r"\b(don'?t|do not|never|stop doing|not again|from now on)\b", cleaned, re.I):
        return ""
    return Lessons(Path(data_dir)).add(user_id, cleaned, "user")["text"]


def lessons_for_prompt(data_dir, user_id: str) -> str:
    items = Lessons(data_dir).active(user_id) if data_dir else []
    if not items:
        return ""
    lines = ["Rules learned from this user. Follow them on this reply. They override an old refusal:"]
    lines.extend(f"- ({item['id']}) {item['text']}" for item in items)
    return "\n".join(lines)


def learn_from_failures(data_dir) -> list[str]:
    """Turn a tool that failed three times recently into one standing rule. No code is changed."""
    path = Path(data_dir) / "audit.jsonl"
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-400:]
    except OSError:
        return []
    counts: dict[tuple[str, str, str], int] = {}
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        outcome = str(row.get("outcome") or "")
        if outcome in {"ok", "awaiting approval"} or outcome.startswith("ok"):
            continue
        key = (str(row.get("user_id") or "admin"), str(row.get("tool") or ""), outcome[:80])
        if key[1]:
            counts[key] = counts.get(key, 0) + 1
    store = Lessons(data_dir)
    learned = []
    for (user_id, tool, outcome), count in counts.items():
        if count < 3 or not re.fullmatch(r"[A-Za-z0-9_:-]{1,80}", tool):
            continue
        text = (f"Tool {tool} has failed ({outcome}). Say the failure and the real next step. "
                "Do not claim it succeeded.")
        if any(tool in item.get("text", "") for item in store.active(user_id)):
            continue
        store.add(user_id, text, "repair")
        learned.append(text)
    return learned[:3]


def self_report(data_dir) -> str:
    lessons = Lessons(data_dir)._load()
    failures = learn_from_failures(data_dir)
    lines = [f"Learned rules on disk: {len(lessons)}.",
             "These rules are added to the next reply. The model is not retrained.",
             "Code is not edited from here. A file change still needs a maintenance proposal and approval."]
    if failures:
        lines.append("New rules from repeated failures: " + " | ".join(failures))
    else:
        lines.append("No new failure rule this pass.")
    try:
        from atulya.maintenance import Maintenance
        from atulya.settings import PROJECT_ROOT, Settings
        settings = Settings.from_environment()
        report = Maintenance(PROJECT_ROOT, Path(data_dir), settings.models_dir).check()
        findings = report.get("findings") if isinstance(report, dict) else None
        lines.append(f"Maintenance check findings: {len(findings or [])}. Nothing was auto-applied.")
    except Exception as exc:
        lines.append(f"Maintenance check skipped ({type(exc).__name__}).")
    return "\n".join(lines)
