"""Tamper-evident audit logs with hash chaining."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AuditEntry:
    id: str
    action: str
    details: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    previous_hash: str = ""
    entry_hash: str = ""


class TamperEvidentLog:
    def __init__(self, log_path: str | Path = "data/audit.log"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash = "0" * 64
        self._load_last_hash()

    def _load_last_hash(self):
        if self.log_path.exists():
            lines = self.log_path.read_text().strip().split("\n")
            if lines:
                last = json.loads(lines[-1])
                self._last_hash = last.get("entry_hash", "0" * 64)

    def append(self, action: str, details: dict[str, Any]) -> AuditEntry:
        entry = AuditEntry(
            id=f"audit_{int(time.time())}_{len(self)}",
            action=action, details=details,
            previous_hash=self._last_hash,
        )
        entry.entry_hash = self._compute_hash(entry)
        self._last_hash = entry.entry_hash

        with open(self.log_path, "a") as f:
            f.write(json.dumps(vars(entry)) + "\n")

        return entry

    def _compute_hash(self, entry: AuditEntry) -> str:
        data = f"{entry.id}{entry.action}{json.dumps(entry.details)}{entry.timestamp}{entry.previous_hash}"
        return hashlib.sha256(data.encode()).hexdigest()

    def verify(self) -> bool:
        """Verify log integrity."""
        if not self.log_path.exists():
            return True
        lines = self.log_path.read_text().strip().split("\n")
        prev_hash = "0" * 64
        for line in lines:
            entry = json.loads(line)
            expected_hash = hashlib.sha256(
                f"{entry['id']}{entry['action']}{json.dumps(entry['details'])}{entry['timestamp']}{prev_hash}".encode()
            ).hexdigest()
            if entry.get("entry_hash") != expected_hash:
                return False
            prev_hash = entry["entry_hash"]
        return True

    def __len__(self) -> int:
        if not self.log_path.exists():
            return 0
        return len(self.log_path.read_text().strip().split("\n"))
