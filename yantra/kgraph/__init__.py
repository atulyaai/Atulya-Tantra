"""Auto-fetch knowledge graph — periodically pulls from connected
services, extracts entities, feeds into vector store + Obsidian."""
from __future__ import annotations

from .engine import KnowledgeGraph

__all__ = ["KnowledgeGraph"]
