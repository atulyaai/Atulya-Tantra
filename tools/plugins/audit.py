"""Audit log: every tool run recorded with user, channel, tool, args, result, time.

Secrets are never stored — arguments are scrubbed before writing.
The log is viewable via the API (GET /api/activity) and in the UI (⋮ → ACTIVITY).
"""
from __future__ import annotations

import json
import logging
import re
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Patterns that look like secrets — scrubbed before writing to the audit log.
# Order matters: Bearer tokens first (they contain spaces that \S+ would stop at).
_SECRET_PATTERNS = [
    re.compile(r"(?i)bearer\s+[a-z0-9\-._~+/]+=*"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd|auth|credential)s?\s*[=:]\s*\S+"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # emails
]

MAX_ENTRIES = 500  # in-memory ring buffer
DEFAULT_CHANNEL = "web"


@dataclass(slots=True)
class AuditEntry:
    """One tool run recorded in the audit log."""
    at: str
    user_id: str
    channel: str
    tool: str
    args_summary: str
    outcome: str
    duration_ms: int = 0


class AuditLog:
    """Thread-safe audit log with a persistent file backing.

    Writes to data/audit.jsonl (one JSON object per line) and keeps a
    ring buffer in memory for fast API reads.
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._path = data_dir / "audit.jsonl"
        self._buffer: deque[AuditEntry] = deque(maxlen=MAX_ENTRIES)
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        """Load existing entries from disk into the ring buffer."""
        if not self._path.exists():
            return
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
            for line in lines[-MAX_ENTRIES:]:
                try:
                    data = json.loads(line)
                    self._buffer.append(AuditEntry(
                        at=data["at"],
                        user_id=data["user_id"],
                        channel=data["channel"],
                        tool=data["tool"],
                        args_summary=data["args_summary"],
                        outcome=data["outcome"],
                        duration_ms=data.get("duration_ms", 0),
                    ))
                except (json.JSONDecodeError, KeyError):
                    continue
        except OSError:
            pass

    def record(
        self,
        *,
        user_id: str,
        channel: str,
        tool: str,
        args: dict,
        outcome: str,
        duration_ms: int = 0,
    ) -> AuditEntry:
        """Record a tool run. Arguments are scrubbed before storing."""
        args_summary = self._scrub_args(args)
        entry = AuditEntry(
            at=datetime.now().astimezone().isoformat(timespec="seconds"),
            user_id=user_id,
            channel=channel,
            tool=tool,
            args_summary=args_summary,
            outcome=outcome,
            duration_ms=duration_ms,
        )
        with self._lock:
            self._buffer.append(entry)
            self._append_to_file(entry)
        return entry

    def _append_to_file(self, entry: AuditEntry) -> None:
        """Append one entry to the JSONL file."""
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "at": entry.at,
                    "user_id": entry.user_id,
                    "channel": entry.channel,
                    "tool": entry.tool,
                    "args_summary": entry.args_summary,
                    "outcome": entry.outcome,
                    "duration_ms": entry.duration_ms,
                }) + "\n")
        except OSError as exc:
            logger.warning("Audit log write failed: %s", exc)

    def _scrub_args(self, args: dict) -> str:
        """Return a summary of arguments with secrets removed."""
        if not args:
            return ""
        parts = []
        for key, value in args.items():
            pair = f"{key}={str(value)[:100]}"
            for pattern in _SECRET_PATTERNS:
                pair = pattern.sub("[REDACTED]", pair)
            parts.append(pair)
        return "; ".join(parts)[:300]

    def recent(self, limit: int = 50) -> list[dict]:
        """Return the most recent entries (newest first)."""
        with self._lock:
            entries = list(self._buffer)[-limit:]
        return [
            {
                "at": e.at,
                "user_id": e.user_id,
                "channel": e.channel,
                "tool": e.tool,
                "args_summary": e.args_summary,
                "outcome": e.outcome,
                "duration_ms": e.duration_ms,
            }
            for e in reversed(entries)
        ]

    def clear(self) -> None:
        """Clear the audit log (owner only)."""
        with self._lock:
            self._buffer.clear()
            try:
                self._path.unlink(missing_ok=True)
            except OSError:
                pass


# Global instance — set by the server at startup
_AUDIT_LOG: AuditLog | None = None


def init_audit_log(data_dir: Path) -> AuditLog:
    """Initialize the global audit log. Called once at server startup."""
    global _AUDIT_LOG
    _AUDIT_LOG = AuditLog(data_dir)
    return _AUDIT_LOG


def get_audit_log() -> AuditLog | None:
    """Get the global audit log instance."""
    return _AUDIT_LOG


def record_tool_run(
    *,
    user_id: str,
    channel: str,
    tool: str,
    args: dict,
    outcome: str,
    duration_ms: int = 0,
) -> None:
    """Record a tool run in the global audit log. No-op if not initialized."""
    if _AUDIT_LOG is None:
        return
    _AUDIT_LOG.record(
        user_id=user_id,
        channel=channel,
        tool=tool,
        args=args,
        outcome=outcome,
        duration_ms=duration_ms,
    )
