"""DNA Genome — weight generator for the NP-DNA architecture.

The Genome is a small neural network (~2-5M params) that generates weight
matrices for Strands on demand.  Like biological DNA encoding proteins,
one Genome produces weights for all Strands in the system.

Compression is achieved through low-rank factored generation:
instead of storing a full (H_in × H_out) matrix, the Genome generates
rank-r factors U (H_in × r) and V (r × H_out), giving r × (H_in + H_out)
cost instead of H_in × H_out.
"""

from __future__ import annotations

import logging
from typing import Literal

import torch
from torch import Tensor, nn

from .config import GenomeConfig, StrandConfig

logger = logging.getLogger(__name__)

WeightRole = Literal["gate", "state", "recurrent", "output"]
_ROLES: list[WeightRole] = ["gate", "state", "recurrent", "output"]


class Genome(nn.Module):
    """DNA weight generator.  Stores one learnable seed per Strand and
    shared encoder/decoder networks that convert seeds into weight matrices.

    Args:
        config: Genome hyperparameters (latent dim, rank, max strands).
        strand_cfg: Per-strand shape info (hidden_size, state_size).
    """

    def __init__(self, config: GenomeConfig, strand_cfg: StrandConfig):
        super().__init__()
        self.config = config
        self.strand_cfg = strand_cfg

        H = strand_cfg.hidden_size
        S = strand_cfg.state_size
        L = config.latent_dim
        R = config.rank

        # One learnable seed per Strand (this is what gets trained per-topic)
        self.seeds = nn.Parameter(torch.randn(config.max_strands, L) * 0.02)

        # Shared encoder:  seed → latent
        self.encoder = nn.Sequential(
            nn.Linear(L, config.encoder_hidden),
            nn.GELU(),
            nn.Linear(config.encoder_hidden, L),
            nn.LayerNorm(L),
        )

        # Weight shape registry:  role → (rows, cols)
        self._shapes: dict[str, tuple[int, int]] = {
            "gate": (H, S),
            "state": (H, S),
            "recurrent": (S, S),
            "output": (S, H),
        }

        # Per-role decoders: latent → low-rank factors U, V
        self.decoders = nn.ModuleDict()
        for role, (rows, cols) in self._shapes.items():
            # U factor: latent → rows × rank
            # V factor: latent → rank × cols
            self.decoders[f"{role}_U"] = nn.Linear(L, rows * R)
            self.decoders[f"{role}_V"] = nn.Linear(L, R * cols)

        # Per-role bias decoders
        self.bias_decoders = nn.ModuleDict()
        for role, (_, cols) in self._shapes.items():
            self.bias_decoders[role] = nn.Linear(L, cols)

    def generate(self, strand_id: int, role: WeightRole) -> tuple[Tensor, Tensor]:
        """Generate a weight matrix and bias for a specific Strand and role.

        Returns:
            (weight, bias) where weight = U @ V  (low-rank approximation).
        """
        if strand_id < 0 or strand_id >= self.seeds.shape[0]:
            raise IndexError(
                f"Strand {strand_id} out of range (genome has {self.seeds.shape[0]} seeds). "
                f"Call add_strand_capacity() before routing to new strands."
            )
        seed = self.seeds[strand_id]
        latent = self.encoder(seed)

        rows, cols = self._shapes[role]
        R = self.config.rank

        U = self.decoders[f"{role}_U"](latent).reshape(rows, R)
        V = self.decoders[f"{role}_V"](latent).reshape(R, cols)
        weight = U @ V  # (rows, cols)

        bias = self.bias_decoders[role](latent)  # (cols,)

        return weight, bias

    def generate_all(self, strand_id: int) -> dict[str, tuple[Tensor, Tensor]]:
        """Generate all weight matrices for a Strand in one call."""
        return {role: self.generate(strand_id, role) for role in _ROLES}

    @property
    def num_active_strands(self) -> int:
        return self.config.max_strands

    def add_strand_capacity(self, count: int = 1) -> None:
        """Grow seed bank to accommodate more Strands."""
        old_max = self.config.max_strands
        new_max = old_max + count
        old_seeds = self.seeds.data
        new_seeds = torch.randn(new_max, self.config.latent_dim, device=old_seeds.device) * 0.02
        new_seeds[:old_max] = old_seeds
        self.seeds = nn.Parameter(new_seeds)
        self.config.max_strands = new_max
        logger.info("Genome: expanded seed bank %d → %d", old_max, new_max)
