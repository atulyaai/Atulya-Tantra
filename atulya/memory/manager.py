"""Unified memory manager combining orchestration, session search, and vector memory."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .orchestrator import MemoryEntry, MemoryOrchestrator, MemoryProvider
from .session_search import SessionSearchProvider
from .vector_store import VectorMemoryProvider


class MemoryManager(MemoryOrchestrator):
    def __init__(self, data_dir: str | Path = "assets/memory"):
        super().__init__(data_dir)
        self.session_search = SessionSearchProvider(data_dir)
        self.vector_store = VectorMemoryProvider(data_dir)

    async def initialize(self):
        await self.session_search.initialize()
        await self.vector_store.initialize()
        self.register_provider(self.session_search)
        self.register_provider(self.vector_store)

    async def close(self):
        if self.session_search:
            await self.session_search.close()
        if self.vector_store:
            await self.vector_store.close()
        await self.close_all()

    async def store_session(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        stats = await self.session_search.stats()
        entry = MemoryEntry(
            id=f"session_{stats['total_sessions'] + 1}",
            provider="session_search",
            content=content,
            metadata=metadata or {},
        )
        await self.session_search.store(entry)

        vec_entry = MemoryEntry(
            id=f"vec_{stats['total_sessions'] + 1}",
            provider="vector_store",
            content=content,
            metadata=metadata or {},
        )
        return await self.vector_store.store(vec_entry)

    async def semantic_search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        return await self.vector_store.search(query, limit)


__all__ = ["MemoryManager", "MemoryEntry", "MemoryOrchestrator", "MemoryProvider", "SessionSearchProvider", "VectorMemoryProvider"]
