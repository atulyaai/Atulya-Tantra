"""Knowledge Graph — auto-fetch from connected services,
entity extraction, vector store + Obsidian wiki sync."""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeNode:
    id: str
    label: str
    type: str
    content: str
    source: str
    embeddings: list[float] | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    connections: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeEdge:
    source: str
    target: str
    relation: str
    weight: float = 1.0
    created_at: float = field(default_factory=time.time)


class KnowledgeGraph:
    """Auto-fetch knowledge graph. Periodically pulls from connected
    services, extracts entities, and feeds into vector store + Obsidian."""

    def __init__(self, data_dir: str | Path, max_nodes: int = 10_000, max_edges: int = 50_000):
        self.data_dir = Path(data_dir) / "kgraph"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_nodes = max_nodes
        self.max_edges = max_edges
        self._lock = threading.Lock()
        self._nodes: dict[str, KnowledgeNode] = {}
        self._edges: list[KnowledgeEdge] = []
        self._sources: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self):
        nf = self.data_dir / "nodes.json"
        if nf.exists():
            try:
                data = json.loads(nf.read_text())
                for n, nd in data.items():
                    self._nodes[n] = KnowledgeNode(**nd)
            except Exception as e:
                logger.warning("Failed to load knowledge graph nodes: %s", e)
        ef = self.data_dir / "edges.json"
        if ef.exists():
            try:
                self._edges = [KnowledgeEdge(**e) for e in json.loads(ef.read_text())]
            except Exception as e:
                logger.warning("Failed to load knowledge graph edges: %s", e)
        sf = self.data_dir / "sources.json"
        if sf.exists():
            try:
                self._sources = json.loads(sf.read_text())
            except Exception as e:
                logger.warning("Failed to load knowledge graph sources: %s", e)

    def _save(self):
        nf = self.data_dir / "nodes.json"
        nf.write_text(json.dumps({n: vars(nd) for n, nd in self._nodes.items()}, indent=2))
        ef = self.data_dir / "edges.json"
        ef.write_text(json.dumps([vars(e) for e in self._edges], indent=2))
        sf = self.data_dir / "sources.json"
        sf.write_text(json.dumps(self._sources, indent=2))

    # ── sources ──────────────────────────────────────────────

    def register_source(self, name: str, source_type: str, config: dict[str, Any]):
        self._sources[name] = {
            "type": source_type,
            "config": config,
            "last_fetch": 0.0,
            "created_at": time.time(),
        }
        self._save()

    def remove_source(self, name: str):
        self._sources.pop(name, None)
        self._save()

    def get_sources(self) -> dict[str, dict[str, Any]]:
        return dict(self._sources)

    # ── nodes ────────────────────────────────────────────────

    def add_node(self, label: str, type: str, content: str, source: str,
                 connections: list[str] | None = None,
                 metadata: dict[str, Any] | None = None) -> KnowledgeNode:
        nid = self._make_id(label, source)
        with self._lock:
            if nid in self._nodes:
                node = self._nodes[nid]
                node.content = content
                node.updated_at = time.time()
                if connections:
                    node.connections = list(set(node.connections + connections))
                if metadata:
                    node.metadata.update(metadata)
            else:
                node = KnowledgeNode(
                    id=nid, label=label, type=type, content=content,
                    source=source, connections=connections or [],
                    metadata=metadata or {},
                )
                self._nodes[nid] = node
            if len(self._nodes) > self.max_nodes:
                oldest = sorted(self._nodes.keys(), key=lambda k: self._nodes[k].created_at)[:len(self._nodes) - self.max_nodes]
                for k in oldest:
                    del self._nodes[k]
        self._save()
        return node

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        return self._nodes.get(node_id)

    def search_nodes(self, query: str) -> list[KnowledgeNode]:
        q = query.lower()
        results = []
        for node in self._nodes.values():
            if q in node.label.lower() or q in node.content.lower():
                results.append(node)
        return results

    def search_by_type(self, type: str) -> list[KnowledgeNode]:
        return [n for n in self._nodes.values() if n.type == type]

    def search_by_source(self, source: str) -> list[KnowledgeNode]:
        return [n for n in self._nodes.values() if n.source == source]

    # ── edges / connections ──────────────────────────────────

    def add_edge(self, source: str, target: str, relation: str, weight: float = 1.0):
        with self._lock:
            self._edges.append(KnowledgeEdge(
                source=source, target=target, relation=relation, weight=weight,
            ))
            if len(self._edges) > self.max_edges:
                self._edges = self._edges[-self.max_edges:]
        self._save()

    def get_connected(self, node_id: str) -> list[tuple[KnowledgeNode, str, float]]:
        results = []
        for edge in self._edges:
            if edge.source == node_id:
                target = self._nodes.get(edge.target)
                if target:
                    results.append((target, edge.relation, edge.weight))
            elif edge.target == node_id:
                source = self._nodes.get(edge.source)
                if source:
                    results.append((source, edge.relation, edge.weight))
        return results

    # ── entity extraction ────────────────────────────────────

    def extract_entities(self, text: str, source: str) -> list[KnowledgeNode]:
        """Extract entities from text using regex patterns."""
        nodes = []
        patterns = {
            "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "url": r"https?://[^\s]+",
            "hashtag": r"#(\w+)",
            "mention": r"@(\w+)",
        }
        seen = set()
        for etype, pattern in patterns.items():
            for match in re.finditer(pattern, text):
                value = match.group(0) if etype in ("email", "url") else match.group(1)
                key = f"{etype}:{value}"
                if key not in seen:
                    seen.add(key)
                    node = self.add_node(
                        label=value, type=etype, content=value,
                        source=source,
                    )
                    nodes.append(node)
        return nodes

    def extract_topics(self, text: str, source: str) -> list[KnowledgeNode]:
        """Extract potential topic entities by noun phrase detection."""
        words = re.findall(r"[A-Z][a-z]+(?:\s[A-Z][a-z]+)*", text)
        camel = re.findall(r"[A-Z][a-z]+(?=[A-Z]|$)", text)
        freq: dict[str, int] = {}
        for w in words:
            if len(w) > 3:
                freq[w] = freq.get(w, 0) + 1
        for w in camel:
            if len(w) > 3:
                freq[w] = freq.get(w, 0) + 1
        nodes = []
        for word, count in sorted(freq.items(), key=lambda x: -x[1])[:10]:
            if count >= 2:
                node = self.add_node(
                    label=word, type="topic", content=word,
                    source=source,
                )
                nodes.append(node)
        return nodes

    # ── data ingestion ───────────────────────────────────────

    def ingest_data(self, source_name: str, data: list[dict[str, Any]]):
        """Ingest structured data from a fetched source."""
        if source_name not in self._sources:
            self.register_source(source_name, "auto", {})
        updated = 0
        for item in data:
            label = item.get("title") or item.get("name") or item.get("id", "unknown")
            content = item.get("content") or item.get("description") or json.dumps(item)
            item_type = item.get("type", "document")
            connections = item.get("connections", [])
            metadata = {k: v for k, v in item.items()
                       if k not in ("title", "name", "content", "description", "type", "connections")}
            self.add_node(label, item_type, content, source_name, connections, metadata)
            self.extract_entities(content, source_name)
            updated += 1
        self._sources[source_name]["last_fetch"] = time.time()
        self._save()
        return {"ingested": updated, "source": source_name}

    # ── export to Obsidian ───────────────────────────────────

    def export_to_obsidian(self, vault_dir: str | Path) -> dict[str, Any]:
        """Export knowledge graph to an Obsidian vault."""
        vault = Path(vault_dir)
        vault.mkdir(parents=True, exist_ok=True)
        kg_dir = vault / "knowledge-graph"
        kg_dir.mkdir(parents=True, exist_ok=True)

        # Group by type
        by_type: dict[str, list[KnowledgeNode]] = defaultdict(list)
        for node in self._nodes.values():
            by_type[node.type].append(node)

        exported = 0
        for ntype, nodes in by_type.items():
            content = [
                f"# {ntype.capitalize()} Nodes",
                f"",
                f"*Auto-synced from knowledge graph: {time.strftime('%Y-%m-%d %H:%M')}*",
                f"",
                f"---",
                f"",
            ]
            for node in nodes:
                content.extend([
                    f"## [[{self._slugify(node.label)}]]",
                    f"",
                    f"- **Source:** {node.source}",
                    f"- **Type:** {node.type}",
                    f"- **Created:** {time.strftime('%Y-%m-%d', time.localtime(node.created_at))}",
                    f"",
                    f"{node.content}",
                    f"",
                ])
                if node.connections:
                    links = " ".join(f"[[{c}]]" for c in node.connections)
                    content.append(f"**Connections:** {links}\n")
                if node.metadata:
                    for k, v in node.metadata.items():
                        content.append(f"- {k}: {v}")
                content.append("---\n")
            (kg_dir / f"{ntype}.md").write_text("\n".join(content))
            exported += len(nodes)

        # Index
        index = [
            "# Knowledge Graph Index",
            f"",
            f"*Auto-synced: {time.strftime('%Y-%m-%d %H:%M')}*",
            f"",
            f"---",
            f"",
        ]
        for ntype in sorted(by_type.keys()):
            index.append(f"- [[{ntype}]] ({len(by_type[ntype])} nodes)")
        (kg_dir / "index.md").write_text("\n".join(index))

        return {"exported": exported, "types": len(by_type)}

    # ── stats ────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        by_type: dict[str, int] = defaultdict(int)
        by_source: dict[str, int] = defaultdict(int)
        for node in self._nodes.values():
            by_type[node.type] += 1
            by_source[node.source] += 1

        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "sources": len(self._sources),
            "by_type": dict(by_type),
            "by_source": dict(by_source),
        }

    @staticmethod
    def _make_id(label: str, source: str) -> str:
        import hashlib
        raw = f"{label}:{source}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    @staticmethod
    def _slugify(text: str) -> str:
        return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
