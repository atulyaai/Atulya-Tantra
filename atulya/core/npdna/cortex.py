"""Memory Cortex — external knowledge store for NP-DNA.

Stores knowledge as vectors.  The model queries the Cortex during inference
to retrieve relevant facts.  Adding knowledge = adding vectors (zero training).

This is how a 50M param model accesses unlimited knowledge:
  1M Cortex entries ≈ 100B params of stored factual knowledge.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import torch
from torch import Tensor

from .config import CortexConfig

logger = logging.getLogger(__name__)


@dataclass
class CortexEntry:
    """A single knowledge entry in the Cortex."""

    key: Tensor            # Query/key vector (dim,)
    value: Tensor          # Value vector (dim,)
    topic: str = ""
    source: str = ""
    created_at: float = field(default_factory=time.time)
    access_count: int = 0


class MemoryCortex:
    """External vector memory.  Store and retrieve knowledge without retraining.

    Args:
        config: Cortex configuration (dim, max entries, top_k).
    """

    def __init__(self, config: CortexConfig):
        self.config = config
        self.entries: list[CortexEntry] = []

        # Projection layer: hidden_state → query vector
        self.query_proj = torch.nn.Linear(config.dim, config.dim, bias=False)
        self.value_proj = torch.nn.Linear(config.dim, config.dim, bias=False)

    @property
    def size(self) -> int:
        return len(self.entries)

    def store(
        self,
        key: Tensor,
        value: Tensor | None = None,
        topic: str = "",
        source: str = "",
    ) -> int:
        """Store a knowledge entry.  Returns entry index."""
        if value is None:
            value = key.clone()

        key = key.detach().float()
        value = value.detach().float()

        # Enforce max capacity — evict least-accessed entry
        if self.size >= self.config.max_entries:
            self._evict_least_used()

        entry = CortexEntry(key=key, value=value, topic=topic, source=source)
        self.entries.append(entry)
        return self.size - 1

    def retrieve(self, query: Tensor, top_k: int | None = None) -> tuple[Tensor, Tensor]:
        """Find most relevant knowledge for a query.

        Args:
            query: Query vector (dim,) or (batch, dim).
            top_k: Number of entries to retrieve.

        Returns:
            (values, scores) — retrieved value vectors and similarity scores.
        """
        if self.size == 0:
            dim = self.config.dim
            k = top_k or self.config.top_k
            if query.dim() == 1:
                return torch.zeros(k, dim), torch.zeros(k)
            return torch.zeros(query.size(0), k, dim), torch.zeros(query.size(0), k)

        top_k = min(top_k or self.config.top_k, self.size)

        # Stack all keys into a matrix
        keys = torch.stack([e.key for e in self.entries])  # (N, dim)

        # Cosine similarity
        if query.dim() == 1:
            query = query.unsqueeze(0)

        query_norm = torch.nn.functional.normalize(query, dim=-1)   # (B, dim)
        keys_norm = torch.nn.functional.normalize(keys, dim=-1)     # (N, dim)
        scores = query_norm @ keys_norm.T  # (B, N)

        top_scores, top_indices = torch.topk(scores, top_k, dim=-1)  # (B, k)

        # Gather values
        values = torch.stack([e.value for e in self.entries])  # (N, dim)
        # Expand indices for gather
        expanded = top_indices.unsqueeze(-1).expand(-1, -1, values.size(-1))
        top_values = torch.gather(
            values.unsqueeze(0).expand(query.size(0), -1, -1),
            dim=1,
            index=expanded,
        )  # (B, k, dim)

        # Update access counts
        for idx_row in top_indices:
            for idx in idx_row:
                self.entries[idx.item()].access_count += 1

        return top_values.squeeze(0), top_scores.squeeze(0)

    def augment(self, hidden: Tensor) -> Tensor:
        """Augment a hidden state with retrieved Cortex knowledge.

        Args:
            hidden: Hidden state (batch, seq_len, dim) or (batch, dim).

        Returns:
            Augmented hidden state, same shape as input.
        """
        if self.size == 0:
            return hidden

        squeeze_seq = False
        if hidden.dim() == 2:
            hidden = hidden.unsqueeze(1)
            squeeze_seq = True

        B, T, D = hidden.shape
        query = self.query_proj(hidden.reshape(-1, D))  # (B*T, D)
        values, scores = self.retrieve(query)           # (B*T, k, D), (B*T, k)

        # Soft attention over retrieved values
        attn = torch.softmax(scores, dim=-1).unsqueeze(-1)  # (B*T, k, 1)
        context = (values * attn).sum(dim=1)                 # (B*T, D)
        context = self.value_proj(context)

        augmented = hidden + context.reshape(B, T, D)

        if squeeze_seq:
            augmented = augmented.squeeze(1)

        return augmented

    def _evict_least_used(self) -> None:
        """Remove the least-accessed entry."""
        if not self.entries:
            return
        min_idx = min(range(len(self.entries)), key=lambda i: self.entries[i].access_count)
        removed = self.entries.pop(min_idx)
        logger.debug("Cortex evicted entry (topic=%s, accesses=%d)", removed.topic, removed.access_count)

    def store_from_text(self, text: str, encoder_fn: Any, topic: str = "") -> int:
        """Convenience: encode text and store it.

        Args:
            text: Raw text to store.
            encoder_fn: Callable that converts text → tensor (dim,).
            topic: Topic label.

        Returns:
            Entry index.
        """
        with torch.no_grad():
            vec = encoder_fn(text)
        return self.store(vec, topic=topic, source=text[:200])

    def save(self, path: str | Path) -> None:
        """Save Cortex to disk."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save entries as tensor + metadata
        if self.entries:
            keys = torch.stack([e.key for e in self.entries])
            values = torch.stack([e.value for e in self.entries])
            torch.save({"keys": keys, "values": values}, path / "cortex_vectors.pt")

            meta = [
                {
                    "topic": e.topic,
                    "source": e.source,
                    "created_at": e.created_at,
                    "access_count": e.access_count,
                }
                for e in self.entries
            ]
            (path / "cortex_meta.json").write_text(
                json.dumps(meta, indent=2), encoding="utf-8"
            )

        # Save projection weights
        torch.save(
            {
                "query_proj": self.query_proj.state_dict(),
                "value_proj": self.value_proj.state_dict(),
            },
            path / "cortex_projections.pt",
        )
        logger.info("Cortex saved: %d entries to %s", self.size, path)

    @classmethod
    def load(cls, path: str | Path, config: CortexConfig) -> "MemoryCortex":
        """Load Cortex from disk."""
        path = Path(path)
        cortex = cls(config)

        proj_path = path / "cortex_projections.pt"
        if proj_path.exists():
            state = torch.load(proj_path, map_location="cpu", weights_only=True)
            cortex.query_proj.load_state_dict(state["query_proj"])
            cortex.value_proj.load_state_dict(state["value_proj"])

        vec_path = path / "cortex_vectors.pt"
        meta_path = path / "cortex_meta.json"
        if vec_path.exists() and meta_path.exists():
            vecs = torch.load(vec_path, map_location="cpu", weights_only=True)
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            keys = vecs["keys"]
            values = vecs["values"]
            for i, m in enumerate(meta):
                entry = CortexEntry(
                    key=keys[i],
                    value=values[i],
                    topic=m.get("topic", ""),
                    source=m.get("source", ""),
                    created_at=m.get("created_at", 0.0),
                    access_count=m.get("access_count", 0),
                )
                cortex.entries.append(entry)

        logger.info("Cortex loaded: %d entries from %s", cortex.size, path)
        return cortex
