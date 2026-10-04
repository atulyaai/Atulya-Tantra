"""Append-only audit log of everything Atulya does on your behalf."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

_SECRET_KEYS = ("password", "token", "secret", "key")


def _path() -> Path:
    base = Path(os.environ.get("ATULYA_AGENT_DATA_DIR", "kosh/agent"))
    base.mkdir(parents=True, exist_ok=True)
    return base / "audit.jsonl"


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("***" if any(s in k.lower() for s in _SECRET_KEYS) else _clean(v)) for k, v in value.items()}
    if isinstance(value, str) and len(value) > 300:
        return value[:300] + "…"
    return value


def audit(event: str, **fields: Any) -> None:
    """Record one event; never raises."""
    try:
        line = json.dumps({"t": round(time.time(), 1), "event": event, **_clean(fields)}, ensure_ascii=False)
        with _path().open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:  # noqa: BLE001 - auditing must never break an action
        pass


def recent(limit: int = 20) -> list[dict[str, Any]]:
    try:
        lines = _path().read_text(encoding="utf-8").splitlines()[-limit:]
        return [json.loads(x) for x in lines]
    except Exception:  # noqa: BLE001
        return []
