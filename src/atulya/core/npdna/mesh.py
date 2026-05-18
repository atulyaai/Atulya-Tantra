"""Neural Mesh — sparse routing fabric for NP-DNA.

Routes each token to the top-k most relevant Strands out of N total.
Only k Strands compute per token — the rest are skipped.  This gives
N/k × compute savings (e.g., 8 strands, top-2 = 4× savings).

Includes load-balancing loss to prevent dead Strands (where all tokens
route to the same few Strands and the rest are never used).
"""

from __future__ import annotations

import logging

import torch
from torch import Tensor, nn

from .config import MeshConfig
from .genome import Genome
from .strand import Strand

logger = logging.getLogger(__name__)


class NeuralMesh(nn.Module):
    """Sparse routing mesh.  Each token is processed by only top_k Strands.

    Args:
        genome: Shared DNA weight generator for all Strands.
        config: Mesh configuration (num_strands, top_k, etc.).
        layer_offset: Offset into the Genome seed bank for this mesh layer.
    """

    def __init__(self, genome: Genome, config: MeshConfig, layer_offset: int = 0):
        super().__init__()
        self.config = config

        H = config.strand.hidden_size

        # Router: projects hidden state → strand scores
        self.router = nn.Linear(H, config.num_strands, bias=False)

        # Create Strands (each gets a unique strand_id in the Genome)
        self.strands = nn.ModuleList([
            Strand(genome, strand_id=layer_offset + i, config=config.strand)
            for i in range(config.num_strands)
        ])

        # Running usage stats for Plasticity
        self.register_buffer(
            "_usage_counts",
            torch.zeros(config.num_strands),
            persistent=False,
        )

    def forward(self, x: Tensor) -> tuple[Tensor, Tensor]:
        """Route tokens to top-k Strands and combine outputs.

        Args:
            x: Input (batch, seq_len, hidden_size).

        Returns:
            (output, balance_loss) where balance_loss encourages even routing.
        """
        B, T, H = x.shape
        N = self.config.num_strands
        K = self.config.top_k

        # Compute routing scores
        scores = self.router(x)  # (B, T, N)
        top_weights, top_indices = torch.topk(scores, K, dim=-1)  # (B, T, K)
        top_weights = torch.softmax(top_weights, dim=-1)

        # Compute outputs from selected Strands
        output = torch.zeros_like(x)

        for k_idx in range(K):
            strand_indices = top_indices[:, :, k_idx]  # (B, T)
            w = top_weights[:, :, k_idx].unsqueeze(-1)  # (B, T, 1)

            for s_id in range(N):
                mask = strand_indices == s_id  # (B, T)
                if not mask.any():
                    continue

                # Gather tokens that route to this Strand
                # Use a batched approach: find all (batch, time) positions
                batch_idx, time_idx = torch.where(mask)
                if len(batch_idx) == 0:
                    continue

                # Extract relevant tokens
                strand_input = x[batch_idx, time_idx].unsqueeze(1)  # (M, 1, H)

                # Process through Strand
                strand_output = self.strands[s_id](strand_input).squeeze(1)  # (M, H)

                # Weight and accumulate
                token_weights = w[batch_idx, time_idx]  # (M, 1)
                output[batch_idx, time_idx] += strand_output * token_weights

                # Track usage
                self._usage_counts[s_id] += len(batch_idx)

        # Load-balancing loss: encourage even distribution across Strands
        # Based on Switch Transformer's balance loss
        routing_probs = torch.softmax(scores, dim=-1).mean(dim=(0, 1))  # (N,)
        ideal = 1.0 / N
        balance_loss = N * (routing_probs * routing_probs).sum()  # Penalise concentration

        return output, balance_loss * self.config.balance_weight

    @property
    def usage_stats(self) -> dict[int, float]:
        """Usage ratio per Strand."""
        total = self._usage_counts.sum().item()
        if total == 0:
            return {i: 0.0 for i in range(self.config.num_strands)}
        return {
            i: self._usage_counts[i].item() / total
            for i in range(self.config.num_strands)
        }

    def reset_usage(self) -> None:
        self._usage_counts.zero_()
