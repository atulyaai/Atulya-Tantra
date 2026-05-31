"""Tamper-evident audit logs with hash chaining."""
from __future__ import annotations

import hashlib
import json
import os
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
    def __init__(self, log_path: str | Path = "assets/audit.log"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash = "0" * 64
        self._load_last_hash()

    def _load_last_hash(self):
        if not self.log_path.exists() or self.log_path.stat().st_size == 0:
            return
        chunk_size = min(4096, self.log_path.stat().st_size)
        with open(self.log_path, "rb") as f:
            f.seek(-chunk_size, os.SEEK_END)
            if f.tell() > 0:
                f.readline()  # Skip potentially incomplete first line
            tail = f.read().decode("utf-8").strip()
        for line in reversed(tail.splitlines()):
            line = line.strip()
            if line:
                last = json.loads(line)
                self._last_hash = last.get("entry_hash", "0" * 64)
                break

    def append(self, action: str, details: dict[str, Any]) -> AuditEntry:
        entry = AuditEntry(
            id=f"audit_{int(time.time())}_{self._count_lines()}",
            action=action, details=details,
            previous_hash=self._last_hash,
        )
        entry.entry_hash = self._compute_hash(entry)

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(vars(entry), ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

        self._last_hash = entry.entry_hash
        return entry

    def _compute_hash(self, entry: AuditEntry) -> str:
        data = f"{entry.id}{entry.action}{json.dumps(entry.details)}{entry.timestamp}{entry.previous_hash}"
        return hashlib.sha256(data.encode()).hexdigest()

    def verify(self) -> bool:
        if not self.log_path.exists():
            return True
        prev_hash = "0" * 64
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                expected_hash = hashlib.sha256(
                    f"{entry['id']}{entry['action']}{json.dumps(entry['details'])}{entry['timestamp']}{prev_hash}".encode()
                ).hexdigest()
                if entry.get("entry_hash") != expected_hash:
                    return False
                prev_hash = entry["entry_hash"]
        return True

    def __len__(self) -> int:
        return self._count_lines()

    def _count_lines(self) -> int:
        if not self.log_path.exists():
            return 0
        count = 0
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
        return count
