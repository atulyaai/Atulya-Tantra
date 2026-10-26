"""Recent tool actions from every channel, so the next reply knows what already happened."""
from __future__ import annotations

import json
from pathlib import Path


def recent_actions(data_dir, limit: int = 6) -> str:
    path = Path(data_dir) / "audit.jsonl"
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
    except OSError:
        return ""
    rows = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        tool = str(row.get("tool") or "")
        if tool:
            rows.append(row)
    if not rows:
        return ""
    shown = []
    for row in rows[-limit:]:
        shown.append(
            f"- {row.get('at', '')} {row.get('channel', '')} {row.get('tool')}: {str(row.get('outcome') or '')[:80]}"
        )
    return "Actions already taken on the web, Telegram, and routines. Do not deny these:\n" + "\n".join(shown)
