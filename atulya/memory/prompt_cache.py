"""Prompt cache with deferred invalidation."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .orchestrator import MemoryProvider, MemoryEntry


class PromptCacheProvider(MemoryProvider):
    def __init__(self, data_dir: str | Path):
        self.cache_dir = Path(data_dir) / "prompt_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._invalidation_queue: list[dict[str, Any]] = []

    async def initialize(self):
        pass

    async def store(self, entry: MemoryEntry) -> str:
        filepath = self.cache_dir / f"{entry.id}.json"
        filepath.write_text(json.dumps({
            "id": entry.id,
            "content": entry.content,
            "metadata": entry.metadata,
            "tags": entry.tags,
            "created_at": entry.created_at,
        }))
        return entry.id

    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        results = []
        for f in self.cache_dir.glob("*.json"):
            data = json.loads(f.read_text())
            if query.lower() in data.get("content", "").lower():
                results.append(MemoryEntry(
                    id=data["id"], provider="prompt_cache",
                    content=data["content"], metadata=data.get("metadata", {}),
                    tags=data.get("tags", []), created_at=data.get("created_at", 0),
                ))
                if len(results) >= limit:
                    break
        return results

    async def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        entries = []
        for f in sorted(self.cache_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
            data = json.loads(f.read_text())
            entries.append(MemoryEntry(
                id=data["id"], provider="prompt_cache",
                content=data["content"], metadata=data.get("metadata", {}),
                tags=data.get("tags", []), created_at=data.get("created_at", 0),
            ))
        return entries

    def get(self, key: str) -> str | None:
        filepath = self.cache_dir / f"{key}.json"
        if filepath.exists():
            data = json.loads(filepath.read_text())
            expires = data.get("metadata", {}).get("expires")
            if expires is not None and time.time() > expires:
                return None
            return data.get("content")
        return None

    async def set(self, key: str, value: str, ttl: float = 3600):
        entry = MemoryEntry(id=key, provider="prompt_cache", content=value,
                           metadata={"ttl": ttl, "expires": time.time() + ttl})
        await self.store(entry)

    def invalidate(self, key: str):
        self._invalidation_queue.append({"key": key, "queued_at": time.time()})

    async def process_invalidation(self):
        for item in self._invalidation_queue:
            filepath = self.cache_dir / f"{item['key']}.json"
            if filepath.exists():
                filepath.unlink()
        self._invalidation_queue.clear()

    async def compact(self):
        pass  # File-based cache, no compaction needed

