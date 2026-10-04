"""Memory orchestrator with pluggable providers."""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


# ── orchestrator ────────────────────────────────────────────────────────────
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


# ── session_search ────────────────────────────────────────────────────────────
class SessionSearchProvider(MemoryProvider):
    def __init__(self, data_dir: str | Path):
        self.db_path = Path(data_dir) / "session_search.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def __del__(self):
        try:
            if self._conn:
                self._conn.close()
                self._conn = None
        except Exception:
            pass

    async def initialize(self):
        def _do():
            conn = self._get_conn()
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS sessions USING fts5(
                    id, content, metadata, tags, created_at,
                    tokenize='unicode61'
                )
            """)
            conn.commit()
        await asyncio.to_thread(_do)

    async def store(self, entry: MemoryEntry) -> str:
        def _do():
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO sessions (id, content, metadata, tags, created_at) VALUES (?, ?, ?, ?, ?)",
                (entry.id, entry.content, json.dumps(entry.metadata), json.dumps(entry.tags), entry.created_at),
            )
            conn.commit()
            return entry.id
        return await asyncio.to_thread(_do)

    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        def _do():
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT id, content, metadata, tags, created_at FROM sessions WHERE sessions MATCH ? LIMIT ?",
                (query, limit),
            ).fetchall()
            return [
                MemoryEntry(
                    id=r[0], provider="session_search", content=r[1],
                    metadata=json.loads(r[2]) if r[2] else {},
                    tags=json.loads(r[3]) if r[3] else [],
                    created_at=r[4],
                )
                for r in rows
            ]
        return await asyncio.to_thread(_do)

    async def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        def _do():
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT id, content, metadata, tags, created_at FROM sessions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [
                MemoryEntry(
                    id=r[0], provider="session_search", content=r[1],
                    metadata=json.loads(r[2]) if r[2] else {},
                    tags=json.loads(r[3]) if r[3] else [],
                    created_at=r[4],
                )
                for r in rows
            ]
        return await asyncio.to_thread(_do)

    async def compact(self):
        def _do():
            conn = self._get_conn()
            conn.execute("INSERT INTO sessions(sessions) VALUES('optimize')")
            conn.commit()
        await asyncio.to_thread(_do)

    async def stats(self) -> dict[str, Any]:
        def _do():
            conn = self._get_conn()
            count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            return {"total_sessions": count}
        return await asyncio.to_thread(_do)

    async def close(self):
        if self._conn:
            def _do_close():
                try:
                    self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    self._conn.execute("PRAGMA journal_mode=DELETE")
                except Exception:
                    pass
                self._conn.close()
            await asyncio.to_thread(_do_close)
            self._conn = None


# ── vector_store ────────────────────────────────────────────────────────────
_WORD_RE = re.compile(r"[a-z0-9]+")
_CHAR_NGRAMS = (3, 4)


def _hbytes(text: str) -> bytes:
    return hashlib.sha256(text.encode("utf-8")).digest()


def _signed_probe(text: str, salt: int) -> tuple[int, float]:
    """Map a feature string to a (dimension, weight) using a salted hash."""
    digest = _hbytes(f"{salt}:{text}")
    dim = (digest[0] << 8) | digest[1]
    sign = 1.0 if (digest[2] & 1) else -1.0
    mag = 0.5 + (digest[3] / 255.0)
    return dim, sign * mag


def _hash_embed(text: str, dim: int = 128) -> list[float]:
    """Generate a deterministic dependency-free embedding from text.

    Combines word unigrams with character n-grams (3- and 4-grams) using
    salted feature hashing. Character n-grams capture morphological and
    near-duplicate overlap ("python script" vs "python function",
    "running" vs "run"), giving meaningfully better recall than naive
    per-token hashing while needing no external ML libraries.
    """
    vector = [0.0] * dim
    lower = (text or "").lower()
    words = _WORD_RE.findall(lower)

    features: set[str] = set(words)
    for gram in _CHAR_NGRAMS:
        if len(lower) >= gram:
            features.update(lower[i : i + gram] for i in range(len(lower) - gram + 1))

    # Keep sparse: probe each feature into dim via salted hash (2 probes/feature).
    for feature in features:
        for salt in (1, 2, 3):
            feature_dim, weight = _signed_probe(feature, salt)
            vector[feature_dim % dim] += weight

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


# ── manager ────────────────────────────────────────────────────────────
class MemoryManager(MemoryOrchestrator):
    def __init__(self, data_dir: str | Path = "kosh/memory"):
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


# ── graph ────────────────────────────────────────────────────────────
# id, label, words that mean this branch when spoken ("open episodic memories")
BRANCHES = [
    ("personal", "Personal history", ("personal history", "history", "personal")),
    ("concepts", "Concepts & entities", ("concepts", "entities", "people", "relations")),
    ("preference", "User preferences", ("preferences", "likes", "dislikes")),
    ("episodic", "Episodic memories", ("episodic", "episodes", "conversations", "chats")),
    ("skills", "Skills & capabilities", ("skills", "capabilities", "tools", "abilities")),
    ("self", "Self-awareness", ("self awareness", "self-awareness", "myself", "mood")),
    ("arch", "Cognitive architecture", ("architecture", "cognitive", "modules")),
    ("world", "World knowledge", ("world knowledge", "world", "knowledge", "topics")),
]
SECTIONS = [{"id": b, "label": label, "words": list(words)} for b, label, words in BRANCHES]

_PERSONAL_KINDS = {"place", "work", "date", "health", "note"}
_ENTITY_KINDS = {"person"}

MODULES = [
    ("kernel", "Cognitive kernel: routes every request"),
    ("planner", "Planner: turns a request into steps"),
    ("safety", "Safety: risky actions ask first"),
    ("triggers", "Triggers: reacts to events on its own"),
    ("memory", "Memory: profile, vectors, summaries"),
    ("senses", "Senses: camera, motion, home sensors"),
    ("router", "Brain router: fastest working brain first"),
]


def build_memory_graph(
    view: dict[str, Any],
    topics: list[dict[str, Any]] | None = None,
    *,
    episodes: list[dict[str, Any]] | None = None,
    skills: list[tuple[str, str]] | None = None,
    mood: dict[str, Any] | None = None,
    brains: list[dict[str, Any]] | None = None,
    vectors: int = 0,
) -> dict[str, Any]:
    """``view`` is ``ProfileStore.view()``; the rest are optional extra sources."""
    user = view.get("user") or "You"
    leaves: dict[str, list[dict[str, Any]]] = {b: [] for b, _, _ in BRANCHES}
    relations: list[dict[str, str]] = []
    prefs: list[str] = []

    for fact in view.get("facts") or []:
        kind, value, text = fact.get("kind"), str(fact.get("value") or ""), str(fact.get("text") or "")
        leaf = {"id": f"fact:{fact.get('id', len(relations))}", "label": value or text, "detail": text, "key": fact.get("key", "")}
        if kind in _ENTITY_KINDS:
            leaves["concepts"].append(leaf)
            relations.append({"a": user, "rel": str(fact.get("key") or "knows"), "b": value})
        elif kind == "preference":
            leaves["preference"].append(leaf)
            prefs.append(f"{fact.get('key', '')}: {value}")
        elif kind in _PERSONAL_KINDS or kind:
            leaves["personal"].append(leaf)
        else:
            leaves["personal"].append(leaf)
    for habit in view.get("habits") or []:
        leaves["personal"].append({"id": f"habit:{habit.get('signature')}", "label": str(habit.get("label") or ""),
                                   "detail": f"{habit.get('label')} {habit.get('when', '')}".strip(), "key": "habit"})
    for i, ep in enumerate(episodes or []):
        text = str(ep.get("text") or ep.get("content") or "").strip()
        if text:
            leaves["episodic"].append({"id": f"ep:{i}", "label": text[:48], "detail": text[:400], "time": ep.get("created_at", "")})
    for name, desc in skills or []:
        leaves["skills"].append({"id": f"skill:{name}", "label": name.replace("_", " "), "detail": desc})
    for k, v in (mood or {}).items():
        leaves["self"].append({"id": f"self:{k}", "label": f"{k}: {v}", "detail": f"Atulya's {k} is {v}"})
    for b in brains or []:
        leaves["self"].append({"id": f"brain:{b['name']}", "label": f"brain: {b['name']}",
                               "detail": f"{b['name']} answers in about {b['seconds']}s" if b.get("seconds") else f"{b['name']} is ready"})
    for name, desc in MODULES:
        leaves["arch"].append({"id": f"mod:{name}", "label": name, "detail": desc})
    for t in topics or []:
        leaves["world"].append({"id": f"topic:{t.get('topic')}", "label": str(t.get("topic") or ""), "detail": str(t.get("summary") or "")[:300]})

    nodes: list[dict[str, Any]] = [{"id": "root", "label": user, "group": "root", "kind": "root"}]
    edges: list[dict[str, str]] = []
    for bid, label, _ in BRANCHES:
        if not leaves[bid]:
            continue
        branch_id = f"branch:{bid}"
        nodes.append({"id": branch_id, "label": label, "group": bid, "kind": "branch", "count": len(leaves[bid])})
        edges.append({"from": "root", "to": branch_id})
        for leaf in leaves[bid]:
            nodes.append({**leaf, "group": bid, "kind": "leaf"})
            edges.append({"from": branch_id, "to": leaf["id"]})

    recent = [n for n in leaves["episodic"][:2]]
    return {
        "nodes": nodes, "edges": edges, "total": sum(len(v) for v in leaves.values()), "relations": relations,
        "sections": [s for s in SECTIONS if leaves[s["id"]]],
        "callouts": {
            "episodic": [{"label": n["label"], "time": n.get("time", "")} for n in recent],
            "relations": relations[:2],
            "preferences": prefs[:3],
            "vectors": vectors,
        },
    }


# ── smriti ────────────────────────────────────────────────────────────
__all__ = [
    "ContextWindow",
    "MemoryEntry",
    "MemoryOrchestrator",
    "MemoryProvider",
    "MemoryProviderType",
    "MemoryManager",
    "SessionSearchProvider",
    "VectorMemoryProvider",
]

