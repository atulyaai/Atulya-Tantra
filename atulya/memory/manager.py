"""Unified memory manager combining orchestration and session search."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .orchestrator import MemoryEntry, MemoryOrchestrator, MemoryProvider
from .session_search import SessionSearchProvider


class MemoryManager(MemoryOrchestrator):
    def __init__(self, data_dir: str | Path = "assets/memory"):
        super().__init__(data_dir)
        self.session_search = SessionSearchProvider(data_dir)

    async def initialize(self):
        await self.session_search.initialize()
        self.register_provider(self.session_search)

    async def close(self):
        if self.session_search:
            await self.session_search.close()
        await self.close_all()

    async def store_session(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        stats = await self.session_search.stats()
        entry = MemoryEntry(
            id=f"session_{stats['total_sessions'] + 1}",
            provider="session_search",
            content=content,
            metadata=metadata or {},
        )
        return await self.session_search.store(entry)


__all__ = ["MemoryManager", "MemoryEntry", "MemoryOrchestrator", "MemoryProvider", "SessionSearchProvider"]
