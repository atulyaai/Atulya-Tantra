"""Strand â€” causal gated state-space processing unit.

Each Strand is a lightweight recurrent processor whose weights are generated
by the Genome (DNA).  It processes sequences causally (left-to-right) using
gated state recurrence â€” O(T) linear time, no attention matrices, CPU-fast.

The state update at each position t:
    gate_t = Ïƒ(x_t @ W_gate + s_{t-1} @ W_recurrent + b_gate + b_rec)
    s_t    = gate_t * s_{t-1} + (1 - gate_t) * tanh(x_t @ W_state + b_state)
    y_t    = s_t @ W_output + b_output

This is causal by construction: each step only uses s_{t-1} (the past).
"""

from __future__ import annotations

import torch
from torch import Tensor, nn

from .config import StrandConfig
from .genome import Genome


class Strand(nn.Module):
    """Causal gated state-space processing unit with DNA-generated weights.

    Does NOT store its own weights — they come from the Genome.  This means
    adding a new Strand costs only 256 params (one new seed in the Genome),
    not a full set of weight matrices.

    Each Strand has an optional category tag — when set, it only trains on
    data matching that category.

    Args:
        genome: Shared DNA weight generator.
        strand_id: This Strand's index in the Genome seed bank.
        config: Hidden/state size configuration.
        category: Optional category name (e.g., "math", "code", "conversation").
    """

    def __init__(self, genome: Genome, strand_id: int, config: StrandConfig,
                 category: str | None = None, device: torch.device | None = None):
        super().__init__()
        self.genome = genome
        self.strand_id = strand_id
        self.config = config
        self.category: str | None = category  # "math", "code", "conversation", etc.
        self.norm = nn.LayerNorm(config.hidden_size, device=device)

        # Usage tracking for Plasticity Engine
        self.usage_count: int = 0

    def reset_usage(self):
        self.usage_count = 0

    def forward(
        self,
        x: Tensor,
        weights: dict[str, tuple[Tensor, Tensor]] | None = None,
        init_state: Tensor | None = None,
        return_final_state: bool = False,
    ) -> Tensor | tuple[Tensor, Tensor]:
        """Process sequence causally with vectorized input projections.

        Optimized: pre-computes all input projections at once, then only
        loops for the sequential state update. Reduces matmuls from 3T to 3.

        Args:
            x: Input tensor (batch, seq_len, hidden_size).
            weights: Pre-generated weights (from Genome cache).
            init_state: Initial recurrent state (B, S) for state caching.
            return_final_state: If True, also return final state for caching.

        Returns:
            output: (batch, seq_len, hidden_size)
            final_state: (batch, state_size) — only if return_final_state=True
        """
        B, T, H = x.shape
        S = self.config.state_size
        device = x.device

        x = self.norm(x)

        # Generate weights from DNA once per mesh forward when caller provides a cache.
        if weights is None:
            weights = self.genome.generate_all(self.strand_id)
        W_gate, b_gate = weights["gate"]          # (H, S), (S,)
        W_state, b_state = weights["state"]       # (H, S), (S,)
        W_rec, b_rec = weights["recurrent"]       # (S, S), (S,)
        W_out, b_out = weights["output"]           # (S, H), (H,)

        # ── VECTORIZED: pre-compute all input projections at once ──
        # Instead of T separate matmuls, do 2 big ones:
        gate_input = x @ W_gate + b_gate    # (B, T, S) — all timesteps at once
        state_input = x @ W_state + b_state  # (B, T, S)

        # ── SEQUENTIAL: state update (unavoidable — uses previous state) ──
        state = init_state if init_state is not None else torch.zeros(B, S, device=device, dtype=x.dtype)
        outputs = []

        for t in range(T):
            # Now each loop iteration is 3 cheap ops instead of 3 matmuls:
            rec = state @ W_rec + b_rec          # (B, S)
            gate = torch.sigmoid(gate_input[:, t] + rec)  # (B, S)
            candidate = torch.tanh(state_input[:, t])      # (B, S) — no matmul!
            state = gate * state + (1.0 - gate) * candidate
            outputs.append(state)

        # Stack states, then single big output projection:
        all_states = torch.stack(outputs, dim=1)  # (B, T, S)
        out = all_states @ W_out + b_out           # (B, T, H) — ONE matmul for all T

        self.usage_count += B * T

        if return_final_state:
            return out, state
        return out

