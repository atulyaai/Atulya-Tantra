"""Strand — causal gated state-space processing unit.

Each Strand is a lightweight recurrent processor whose weights are generated
by the Genome (DNA).  It processes sequences causally (left-to-right) using
gated state recurrence — O(T) linear time, no attention matrices, CPU-fast.

The state update at each position t:
    gate_t = σ(x_t @ W_gate + s_{t-1} @ W_recurrent + b_gate + b_rec)
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

    Args:
        genome: Shared DNA weight generator.
        strand_id: This Strand's index in the Genome seed bank.
        config: Hidden/state size configuration.
    """

    def __init__(self, genome: Genome, strand_id: int, config: StrandConfig):
        super().__init__()
        self.genome = genome
        self.strand_id = strand_id
        self.config = config
        self.norm = nn.LayerNorm(config.hidden_size)

        # Usage tracking for Plasticity Engine
        self.usage_count: int = 0

    def forward(self, x: Tensor) -> Tensor:
        """Process sequence causally.

        Args:
            x: Input tensor (batch, seq_len, hidden_size).

        Returns:
            Output tensor (batch, seq_len, hidden_size).
        """
        B, T, H = x.shape
        S = self.config.state_size
        device = x.device

        x = self.norm(x)

        # Generate weights from DNA (shared Genome)
        weights = self.genome.generate_all(self.strand_id)
        W_gate, b_gate = weights["gate"]          # (H, S), (S,)
        W_state, b_state = weights["state"]       # (H, S), (S,)
        W_rec, b_rec = weights["recurrent"]       # (S, S), (S,)
        W_out, b_out = weights["output"]           # (S, H), (H,)

        # Causal state-space recurrence
        state = torch.zeros(B, S, device=device, dtype=x.dtype)
        outputs = []

        for t in range(T):
            x_t = x[:, t, :]  # (B, H)

            # Gate: how much to remember vs reset
            gate = torch.sigmoid(x_t @ W_gate + state @ W_rec + b_gate + b_rec)

            # State update: blend old state with new input
            candidate = torch.tanh(x_t @ W_state + b_state)
            state = gate * state + (1.0 - gate) * candidate

            # Output: project state back to hidden dim
            y_t = state @ W_out + b_out  # (B, H)
            outputs.append(y_t)

        self.usage_count += B * T
        return torch.stack(outputs, dim=1)  # (B, T, H)
