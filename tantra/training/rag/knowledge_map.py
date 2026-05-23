"""Compact knowledge map, adapter simulation, and training type registry."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class FactCheck:
    verdict: str
    confidence: float


class KnowledgeMap:
    def __init__(self, data_dir: str | Path = "atulya/runtime/rag"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.nodes: dict[str, dict[str, str]] = {}
        self.relations: dict[str, list[str]] = {}

    def add_knowledge(self, topic: str, content: str) -> str:
        node_id = f"n{len(self.nodes) + 1}"
        self.nodes[node_id] = {"topic": topic, "content": content}
        return node_id

    def retrieve(self, query: str) -> list[dict[str, str]]:
        terms = {part.lower() for part in query.split() if part}
        results = []
        for node_id, node in self.nodes.items():
            haystack = f"{node['topic']} {node['content']}".lower()
            if any(term in haystack for term in terms):
                results.append({"id": node_id, **node})
        return results

    def fact_check(self, statement: str) -> FactCheck:
        normalized = statement.lower()
        for node in self.nodes.values():
            if normalized in node["content"].lower():
                return FactCheck("true", 0.9)
        return FactCheck("unverified", 0.0)

    def add_relation(self, source_id: str, target_id: str) -> None:
        self.relations.setdefault(source_id, []).append(target_id)

    def get_relations(self, source_id: str) -> list[str]:
        return self.relations.get(source_id, [])

    def get_stats(self) -> dict[str, int]:
        return {"total_nodes": len(self.nodes), "total_relations": sum(len(v) for v in self.relations.values())}


class LoRASimulator:
    def __init__(self):
        self.adapters: dict[str, dict] = {}

    def create_adapter(self, name: str, domain: str, examples: list[dict], rank: int = 8) -> dict:
        adapter = {"name": name, "domain": domain, "examples": examples, "rank": rank}
        self.adapters[name] = adapter
        return adapter

    def apply_adapter(self, name: str, prompt: str) -> str:
        adapter = self.adapters[name]
        return f"[{adapter['domain']}] {prompt}"


class TrainingTypeRegistry:
    def __init__(self):
        self.types = {
            "lora": {"rank": 8, "description": "Low-rank adaptation"},
            "rope": {"scale": 1.0, "description": "Rotary position extension"},
            "dpo": {"beta": 0.1, "description": "Preference optimization"},
        }

    def list_types(self) -> list[str]:
        return sorted(self.types)

    def get_config(self, name: str) -> dict:
        return dict(self.types[name])


__all__ = ["KnowledgeMap", "FactCheck", "LoRASimulator", "TrainingTypeRegistry"]
