"""Vector memory provider using embedding-based semantic search."""
from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from pathlib import Path
from typing import Any

from .orchestrator import MemoryEntry, MemoryProvider


def _hash_embed(text: str, dim: int = 128) -> list[float]:
    """Generate a deterministic pseudo-embedding from text using hash-based feature hashing.

    This is a lightweight embedding that requires no external ML libraries.
    For production use, replace with sentence-transformers or similar.
    """
    tokens = text.lower().split()
    vector = [0.0] * dim
    for token in tokens:
        h = hashlib.sha256(token.encode("utf-8")).digest()
        for i in range(dim):
            byte_val = h[i % len(h)]
            if byte_val % 2 == 0:
                vector[i] += 1.0 / (1 + i * 0.1)
            else:
                vector[i] -= 1.0 / (1 + i * 0.1)

    norm = math.sqrt(sum(x * x for x in vector))
    if norm > 0:
        vector = [x / norm for x in vector]
    return vector


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class VectorMemoryProvider(MemoryProvider):
    """Vector-based memory provider with embedding similarity search.

    Stores entries with computed embeddings and supports semantic search
    via cosine similarity. Persists to a JSON file for durability.
    """

    def __init__(self, data_dir: str | Path, collection: str = "atulya_memory", max_entries: int = 10_000):
        self.data_dir = Path(data_dir)
        self.collection = collection
        self.max_entries = max_entries
        self._store_path = self.data_dir / f"vector_{collection}.json"
        self._entries: list[dict[str, Any]] = []
        self._embeddings: list[list[float]] = []
        self._lock = threading.Lock()
        self._initialized = False

    async def initialize(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if self._store_path.exists():
            try:
                data = json.loads(self._store_path.read_text(encoding="utf-8"))
                self._entries = data.get("entries", [])
                self._embeddings = data.get("embeddings", [])
            except Exception:
                self._entries = []
                self._embeddings = []
        self._initialized = True

    def _persist(self):
        import logging
        try:
            self._store_path.write_text(
                json.dumps(
                    {"entries": self._entries, "embeddings": self._embeddings},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as e:
            logging.getLogger(__name__).error("Vector store persist failed: %s", e)

    async def store(self, entry: MemoryEntry) -> str:
        embedding = _hash_embed(entry.content)
        record = {
            "id": entry.id,
            "provider": entry.provider,
            "content": entry.content,
            "metadata": entry.metadata,
            "tags": entry.tags,
            "created_at": entry.created_at,
        }
        with self._lock:
            self._entries.append(record)
            self._embeddings.append(embedding)
            if len(self._entries) > self.max_entries:
                self._entries = self._entries[-self.max_entries:]
                self._embeddings = self._embeddings[-self.max_entries:]
        self._persist()
        return entry.id

    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        if not self._entries:
            return []

        query_embedding = _hash_embed(query)
        scored = []
        for i, emb in enumerate(self._embeddings):
            sim = _cosine_similarity(query_embedding, emb)
            scored.append((sim, i))
        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for sim, idx in scored[:limit]:
            rec = self._entries[idx]
            results.append(
                MemoryEntry(
                    id=rec["id"],
                    provider=rec["provider"],
                    content=rec["content"],
                    metadata={**rec.get("metadata", {}), "_similarity": round(sim, 4)},
                    tags=rec.get("tags", []),
                    created_at=rec.get("created_at", 0),
                )
            )
        return results

    async def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        recent = self._entries[-limit:]
        return [
            MemoryEntry(
                id=rec["id"],
                provider=rec["provider"],
                content=rec["content"],
                metadata=rec.get("metadata", {}),
                tags=rec.get("tags", []),
                created_at=rec.get("created_at", 0),
            )
            for rec in reversed(recent)
        ]

    async def close(self):
        self._persist()

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_entries": len(self._entries),
            "collection": self.collection,
            "embedding_dim": 128,
        }
