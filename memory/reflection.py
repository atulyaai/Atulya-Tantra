"""Reflection provider for self-improvement."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .orchestrator import MemoryProvider, MemoryEntry


class ReflectionProvider(MemoryProvider):
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir) / "reflections"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._reflections: list[dict[str, Any]] = []

    async def initialize(self):
        for f in self.data_dir.glob("*.json"):
            self._reflections.append(json.loads(f.read_text()))

    async def store(self, entry: MemoryEntry) -> str:
        filepath = self.data_dir / f"{entry.id}.json"
        data = {
            "id": entry.id, "content": entry.content,
            "metadata": entry.metadata, "tags": entry.tags, "created_at": entry.created_at,
        }
        filepath.write_text(json.dumps(data))
        self._reflections.append(data)
        return entry.id

    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        results = []
        for r in self._reflections:
            if query.lower() in r.get("content", "").lower():
                results.append(MemoryEntry(
                    id=r["id"], provider="reflection", content=r["content"],
                    metadata=r.get("metadata", {}), tags=r.get("tags", []),
                    created_at=r.get("created_at", 0),
                ))
                if len(results) >= limit:
                    break
        return results

    async def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        sorted_reflections = sorted(self._reflections, key=lambda x: x.get("created_at", 0), reverse=True)
        return [
            MemoryEntry(id=r["id"], provider="reflection", content=r["content"],
                       metadata=r.get("metadata", {}), tags=r.get("tags", []),
                       created_at=r.get("created_at", 0))
            for r in sorted_reflections[:limit]
        ]

    async def add_reflection(self, content: str, category: str = "general"):
        entry = MemoryEntry(
            id=f"ref_{int(time.time())}", provider="reflection", content=content,
            metadata={"category": category},
        )
        await self.store(entry)
        return entry.id

    async def get_insights(self) -> list[dict[str, Any]]:
        insights = []
        for r in self._reflections:
            if r.get("metadata", {}).get("category") == "insight":
                insights.append(r)
        return insights

