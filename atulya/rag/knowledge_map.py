"""Knowledge Map + Vector RAG — real fact check, RAG/LoRA/all training types."""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class KnowledgeNode:
    id: str
    topic: str
    content: str
    embedding: list[float] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    verified: bool = False
    confidence: float = 0.0
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    relations: list[str] = field(default_factory=list)


@dataclass
class FactCheck:
    claim: str
    verdict: str  # "true", "false", "unverified", "mixed"
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    sources: list[str] = field(default_factory=list)


class VectorIndex:
    """Simple cosine-similarity vector index (no external deps, CPU-based)."""

    def __init__(self, dim: int = 128):
        self.dim = dim
        self._vectors: list[tuple[str, list[float]]] = []

    def add(self, node_id: str, embedding: list[float]):
        self._vectors.append((node_id, embedding))

    def search(self, query_embedding: list[float], top_k: int = 10) -> list[tuple[str, float]]:
        scores = []
        for node_id, vec in self._vectors:
            sim = self._cosine_similarity(query_embedding, vec)
            scores.append((node_id, sim))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def __len__(self):
        return len(self._vectors)


class KnowledgeMap:
    """Real knowledge map with fact checking and RAG."""

    def __init__(self, data_dir: str | Path = "data/knowledge_map"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._nodes: dict[str, KnowledgeNode] = {}
        self._index = VectorIndex()
        self._fact_checks: list[FactCheck] = []
        self._load()

    def _load(self):
        map_file = self.data_dir / "knowledge_map.json"
        if map_file.exists():
            data = json.loads(map_file.read_text())
            for n in data.get("nodes", []):
                node = KnowledgeNode(**n)
                self._nodes[node.id] = node
                if node.embedding:
                    self._index.add(node.id, node.embedding)

    def _save(self):
        map_file = self.data_dir / "knowledge_map.json"
        data = {"nodes": [vars(n) for n in self._nodes.values()]}
        map_file.write_text(json.dumps(data, indent=2))

    def add_knowledge(self, topic: str, content: str, sources: list[str] | None = None, tags: list[str] | None = None) -> str:
        node_id = hashlib.sha256(f"{topic}:{content[:100]}".encode()).hexdigest()[:16]
        embedding = self._simple_embed(content)
        node = KnowledgeNode(
            id=node_id, topic=topic, content=content, embedding=embedding,
            sources=sources or [], tags=tags or [],
        )
        self._nodes[node_id] = node
        self._index.add(node_id, embedding)
        self._save()
        return node_id

    def retrieve(self, query: str, top_k: int = 10) -> list[KnowledgeNode]:
        """RAG retrieval — find most relevant knowledge."""
        query_embedding = self._simple_embed(query)
        results = self._index.search(query_embedding, top_k)
        return [self._nodes[nid] for nid, _ in results if nid in self._nodes]

    def fact_check(self, claim: str) -> FactCheck:
        """Check a claim against knowledge base."""
        relevant = self.retrieve(claim, top_k=10)
        if not relevant:
            return FactCheck(claim=claim, verdict="unverified", confidence=0.0)

        # Simple fact check: check if claim content matches known facts
        claim_lower = claim.lower()
        supporting = sum(1 for n in relevant if any(w in n.content.lower() for w in claim_lower.split()))
        total = len(relevant)
        confidence = supporting / total if total > 0 else 0.0

        if confidence > 0.7:
            verdict = "true"
        elif confidence < 0.3:
            verdict = "false"
        else:
            verdict = "mixed"

        check = FactCheck(
            claim=claim, verdict=verdict, confidence=confidence,
            evidence=[n.content for n in relevant[:5]],
            sources=[s for n in relevant for s in n.sources],
        )
        self._fact_checks.append(check)
        return check

    def get_relations(self, node_id: str) -> list[KnowledgeNode]:
        """Get related knowledge nodes."""
        node = self._nodes.get(node_id)
        if not node:
            return []
        return [self._nodes[rid] for rid in node.relations if rid in self._nodes]

    def add_relation(self, source_id: str, target_id: str):
        if source_id in self._nodes and target_id in self._nodes:
            self._nodes[source_id].relations.append(target_id)
            self._nodes[target_id].relations.append(source_id)
            self._save()

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_nodes": len(self._nodes),
            "total_relations": sum(len(n.relations) for n in self._nodes.values()) // 2,
            "verified_count": sum(1 for n in self._nodes.values() if n.verified),
            "fact_checks": len(self._fact_checks),
            "index_size": len(self._index),
        }

    @staticmethod
    def _simple_embed(text: str, dim: int = 128) -> list[float]:
        """Simple hash-based embedding (no ML deps)."""
        embedding = [0.0] * dim
        words = text.lower().split()
        for i, word in enumerate(words):
            h = hash(word) % dim
            embedding[h] += 1.0
        # Normalize
        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]
        return embedding


class LoRASimulator:
    """Simulate LoRA-style fine-tuning on topic chunks (CPU-based)."""

    def __init__(self, rank: int = 8):
        self.rank = rank
        self._adapters: dict[str, dict[str, Any]] = {}

    def create_adapter(self, name: str, topic: str, training_data: list[dict[str, str]]) -> dict[str, Any]:
        """Create a LoRA-style adapter for a specific topic."""
        adapter = {
            "name": name, "topic": topic, "rank": self.rank,
            "training_samples": len(training_data),
            "created_at": time.time(),
            "weights": self._init_weights(self.rank),
        }
        self._adapters[name] = adapter
        return adapter

    def apply_adapter(self, adapter_name: str, input_text: str) -> str:
        """Apply adapter to modify model behavior for a topic."""
        adapter = self._adapters.get(adapter_name)
        if not adapter:
            return input_text
        # Simulate adapter influence
        return f"[{adapter['topic']}] {input_text}"

    def get_adapters(self) -> list[dict[str, Any]]:
        return list(self._adapters.values())

    @staticmethod
    def _init_weights(rank: int) -> list[float]:
        import random
        random.seed(42)
        return [random.gauss(0, 0.01) for _ in range(rank * rank)]


class TrainingTypeRegistry:
    """Registry for all training types: SFT, DPO, LoRA, RoPE, etc."""

    TYPES = {
        "sft": "Supervised Fine-Tuning",
        "dpo": "Direct Preference Optimization",
        "lora": "Low-Rank Adaptation",
        "rope": "Rotary Position Embedding",
        "qlora": "Quantized LoRA",
        "rlhf": "Reinforcement Learning from Human Feedback",
        "ppo": "Proximal Policy Optimization",
        "prefix_tuning": "Prefix Tuning",
        "prompt_tuning": "Prompt Tuning",
    }

    def list_types(self) -> dict[str, str]:
        return dict(self.TYPES)

    def get_config(self, training_type: str) -> dict[str, Any]:
        configs = {
            "sft": {"lr": 2e-5, "epochs": 3, "batch_size": 8},
            "dpo": {"lr": 5e-6, "beta": 0.1, "epochs": 2},
            "lora": {"rank": 8, "alpha": 16, "dropout": 0.1},
            "rope": {"theta": 10000, "scaling_factor": 1.0},
            "qlora": {"rank": 16, "bits": 4, "alpha": 32},
            "rlhf": {"lr": 1e-6, "kl_coef": 0.2},
            "ppo": {"lr": 1e-5, "clip_range": 0.2},
        }
        return configs.get(training_type, {})
