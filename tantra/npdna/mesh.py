"""Neural Mesh â€” sparse routing fabric for NP-DNA.

Routes each token to the top-k most relevant Strands out of N total.
Only k Strands compute per token â€” the rest are skipped.  This gives
N/k Ã— compute savings (e.g., 8 strands, top-2 = 4Ã— savings).

Includes load-balancing loss to prevent dead Strands (where all tokens
route to the same few Strands and the rest are never used).
"""

from __future__ import annotations

import logging
from collections import Counter

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

        # Router: projects hidden state â†’ strand scores
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
        self.register_buffer("_last_balance_loss", torch.tensor(0.0), persistent=False)
        self.register_buffer("_last_router_entropy", torch.tensor(0.0), persistent=False)
        self._last_top_indices = None
        self._last_top_weights = None
        self.activation_topics: dict[int, Counter[str]] = {}

    def forward(self, x: Tensor) -> tuple[Tensor, Tensor]:
        """Route tokens to top-k Strands and combine outputs.

        Args:
            x: Input (batch, seq_len, hidden_size).

        Returns:
            (output, balance_loss) where balance_loss encourages even routing.
        """
        B, T, H = x.shape
        N = self.config.num_strands
        K = max(1, min(self.config.top_k, N))

        # Compute routing scores
        scores = self.router(x)  # (B, T, N)
        top_weights, top_indices = torch.topk(scores, K, dim=-1)  # (B, T, K)
        top_weights = torch.softmax(top_weights, dim=-1)

        if not self.training:
            self._last_top_indices = top_indices.detach().cpu()
            self._last_top_weights = top_weights.detach().cpu()
        else:
            self._last_top_indices = None
            self._last_top_weights = None

        # Compute outputs from selected Strands
        output = torch.zeros_like(x)

        # Gather all (batch, time, k_idx) triples and group by strand
        # This replaces the O(KÃ—N) nested loop with O(num_active_strands Ã— avg_tokens_per_strand)
        flat_indices = top_indices.reshape(B * T * K)  # (B*T*K,)
        flat_weights = top_weights.reshape(B * T * K, 1)  # (B*T*K, 1)
        flat_x = x.unsqueeze(2).expand(-1, -1, K, -1).reshape(B * T * K, -1)  # (B*T*K, H)

        # Find unique strand indices and their inverse mapping
        unique_strands, inverse = torch.unique(flat_indices, return_inverse=True)
        unique_strands = unique_strands.tolist()  # move to host for iteration
        weight_cache = {
            int(s_id): self.strands[int(s_id)].genome.generate_all(self.strands[int(s_id)].strand_id)
            for s_id in unique_strands
        }

        for s_id in unique_strands:
            mask = inverse == int(s_id)  # use the pre-computed inverse
            mask_flat = mask
            if not mask_flat.any():
                continue

            strand_tokens = flat_x[mask_flat].unsqueeze(1)  # (M, 1, H)
            strand_weights = flat_weights[mask_flat]  # (M, 1)

            # Process through Strand
            strand_output = self.strands[s_id](strand_tokens, weights=weight_cache[int(s_id)]).squeeze(1)  # (M, H)

            # Scatter back
            flat_indices_masked = torch.where(mask_flat)[0]
            batch_idx = flat_indices_masked // (T * K)
            remainder = flat_indices_masked % (T * K)
            time_idx = remainder // K
            output[batch_idx, time_idx] += strand_output * strand_weights

            # Track usage
            self._usage_counts[s_id] += mask_flat.sum().item()

        # Load-balancing loss: encourage even distribution across Strands
        # Based on Switch Transformer's balance loss
        routing_probs = torch.softmax(scores, dim=-1).mean(dim=(0, 1))  # (N,)
        balance_loss = N * (routing_probs * routing_probs).sum()  # Penalise concentration
        entropy = -(routing_probs * routing_probs.clamp_min(1e-9).log()).sum()
        entropy = entropy / torch.log(torch.tensor(max(1.0, float(N)), device=scores.device))
        self._last_balance_loss.copy_(balance_loss.detach())
        self._last_router_entropy.copy_(entropy.detach())

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

    @property
    def last_balance_loss(self) -> float:
        """Most recent unweighted router balance loss."""
        return float(self._last_balance_loss.item())

    @property
    def last_router_entropy(self) -> float:
        """Most recent router entropy normalized to 0..1."""
        return float(self._last_router_entropy.item())

    def reset_usage(self) -> None:
        self._usage_counts.zero_()

    def record_activation_topic(self, topic: str) -> None:
        """Record which topic/category activated recently routed strands."""
        if not topic or self._last_top_indices is None:
            return
        for local_idx in torch.unique(self._last_top_indices).tolist():
            if 0 <= int(local_idx) < len(self.strands):
                strand_id = int(self.strands[int(local_idx)].strand_id)
                self.activation_topics.setdefault(strand_id, Counter())[topic] += 1

    def specialization_stats(self) -> dict[int, dict[str, int]]:
        return {sid: dict(counter) for sid, counter in self.activation_topics.items()}

    def add_strand(self, strand_id: int) -> None:
        """Add one routed Strand to this mesh and expand router/usage state."""
        H = self.config.strand.hidden_size
        old_router = self.router
        old_n = self.config.num_strands
        new_n = old_n + 1

        new_router = nn.Linear(H, new_n, bias=False, device=old_router.weight.device)
        with torch.no_grad():
            new_router.weight[:old_n].copy_(old_router.weight)
            scale = old_router.weight.abs().mean().item()
            if scale < 1e-6:
                scale = 1.0 / max(1, H) ** 0.5
            nn.init.normal_(new_router.weight[old_n], mean=0.0, std=scale)
        self.router = new_router

        self.strands.append(Strand(self.strands[0].genome, strand_id=strand_id, config=self.config.strand))
        self.config.num_strands = new_n

        old_counts = self._usage_counts
        new_counts = torch.zeros(new_n, device=old_counts.device)
        new_counts[:old_n].copy_(old_counts)
        self.register_buffer("_usage_counts", new_counts, persistent=False)
        logger.info("NeuralMesh: added strand %d (%d -> %d)", strand_id, old_n, new_n)

