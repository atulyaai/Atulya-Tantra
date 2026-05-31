"""Memory orchestrator with pluggable providers."""
from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class MemoryProviderType(Enum):
    SESSION_SEARCH = "session_search"
    PROMPT_CACHE = "prompt_cache"
    SUBCONSCIOUS = "subconscious"
    REFLECTION = "reflection"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


@dataclass
class MemoryEntry:
    id: str
    provider: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


@dataclass
class ContextWindow:
    entries: list[MemoryEntry] = field(default_factory=list)
    total_tokens: int = 0
    max_tokens: int = 8192

    def add(self, entry: MemoryEntry, token_count: int = 0):
        if self.total_tokens + token_count <= self.max_tokens:
            self.entries.append(entry)
            self.total_tokens += token_count
            return True
        return False


class MemoryProvider(ABC):
    @abstractmethod
    async def initialize(self): pass
    @abstractmethod
    async def store(self, entry: MemoryEntry) -> str: pass
    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]: pass
    @abstractmethod
    async def get_recent(self, limit: int = 10) -> list[MemoryEntry]: pass

    async def close(self):
        pass


class MemoryOrchestrator:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.providers: dict[str, MemoryProvider] = {}
        self._context = ContextWindow()

    @staticmethod
    def _provider_key(name: str) -> str:
        name = name.replace("Provider", "").replace("provider", "")
        name = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
        return re.sub(r"[^a-z0-9]+", "_", name).strip("_")

    def register_provider(self, provider: MemoryProvider, name: str | None = None):
        name = self._provider_key(name or provider.__class__.__name__)
        self.providers[name] = provider

    async def initialize_all(self):
        for provider in self.providers.values():
            await provider.initialize()

    async def store(self, entry: MemoryEntry) -> str:
        provider = self.providers.get(self._provider_key(entry.provider))
        if provider:
            return await provider.store(entry)
        raise ValueError(f"Unknown provider: {entry.provider}")

    async def search(self, query: str, provider: str | None = None, limit: int = 10) -> list[MemoryEntry]:
        if provider:
            p = self.providers.get(self._provider_key(provider))
            return await p.search(query, limit) if p else []
        results = []
        for p in self.providers.values():
            results.extend(await p.search(query, limit))
        return results[:limit]

    async def get_context(self) -> ContextWindow:
        self._context = ContextWindow()
        for name, p in self.providers.items():
            recent = await p.get_recent(limit=5)
            for entry in recent:
                self._context.add(entry, token_count=len(entry.content) // 4)
        return self._context

    async def compact(self):
        for p in self.providers.values():
            if hasattr(p, "compact"):
                await p.compact()

    async def close_all(self):
        for p in self.providers.values():
            await p.close()

    def get_stats(self) -> dict[str, Any]:
        return {
            "providers": list(self.providers.keys()),
            "context_tokens": self._context.total_tokens,
            "context_entries": len(self._context.entries),
        }

