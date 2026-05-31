"""
State Cache — NP-DNA equivalent of KV cache for autoregressive generation.

Since Strands are recurrent (not attention), the cache stores:
- The hidden state s_t at the end of the prompt for each strand
- The routing decisions (which strands were active)

This avoids re-running the prompt on every generated token.

For a 10-token prompt + 100 token generation:
- Without cache: 10 + 100 = 110 full forward passes (each recomputes prompt)
- With cache: 10 (prefill) + 100 (single-token) = 110 total, but each
  decode step is ~10x faster (no prompt tokens to process)

Usage:
    cache = GenerationCache()

    # Prefill (process prompt, cache states)
    logits, cache = core.prefill(prompt_ids, cache=cache)

    # Decode (one token at a time, reuse cached states)
    for _ in range(max_new_tokens):
        next_token, cache = core.decode_one(last_token, cache=cache)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import torch
from torch import Tensor


@dataclass
class StrandStateCache:
    """Cached recurrent state for one layer."""
    states: dict[int, Tensor] = field(default_factory=dict)  # strand_id → state (B, S)
    router_logits: Tensor | None = None  # cached router scores


class GenerationCache:
    """Full cache for autoregressive generation.

    Stores recurrent states per layer per strand, allowing fast
    single-token decoding after the initial prefill.
    """

    def __init__(self):
        self.layer_caches: list[StrandStateCache] = []
        self.seq_len: int = 0   # how many tokens are cached
        self.is_filled: bool = False

    def store_layer_state(self, layer_idx: int, strand_id: int, state: Tensor) -> None:
        """Store a strand's recurrent state for a layer."""
        while len(self.layer_caches) <= layer_idx:
            self.layer_caches.append(StrandStateCache())
        self.layer_caches[layer_idx].states[strand_id] = state.detach()

    def get_layer_state(self, layer_idx: int, strand_id: int) -> Tensor | None:
        """Retrieve a strand's cached state. Returns None if not cached."""
        if layer_idx >= len(self.layer_caches):
            return None
        return self.layer_caches[layer_idx].states.get(strand_id)

    def store_router_logits(self, layer_idx: int, logits: Tensor) -> None:
        """Cache router logits for a layer (optional, for analysis)."""
        while len(self.layer_caches) <= layer_idx:
            self.layer_caches.append(StrandStateCache())
        self.layer_caches[layer_idx].router_logits = logits.detach()

    def clear(self) -> None:
        """Clear all cached states."""
        self.layer_caches.clear()
        self.seq_len = 0
        self.is_filled = False

    def copy(self) -> GenerationCache:
        """Create a deep copy of this cache."""
        new_cache = GenerationCache()
        new_cache.seq_len = self.seq_len
        new_cache.is_filled = self.is_filled
        for layer_cache in self.layer_caches:
            new_layer = StrandStateCache(
                states={sid: s.clone() for sid, s in layer_cache.states.items()},
                router_logits=layer_cache.router_logits.clone() if layer_cache.router_logits is not None else None,
            )
            new_cache.layer_caches.append(new_layer)
        return new_cache

    @property
    def num_layers(self) -> int:
        return len(self.layer_caches)

    @property
    def memory_bytes(self) -> int:
        """Estimate memory usage in bytes."""
        total = 0
        for layer_cache in self.layer_caches:
            for state in layer_cache.states.values():
                total += state.nelement() * state.element_size()
            if layer_cache.router_logits is not None:
                total += layer_cache.router_logits.nelement() * layer_cache.router_logits.element_size()
        return total
