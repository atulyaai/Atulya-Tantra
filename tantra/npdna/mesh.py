"""Neural Mesh — sparse routing fabric for NP-DNA.

Routes each token to the top-k most relevant Strands out of N total.
Only k Strands compute per token — the rest are skipped.  This gives
N/k × compute savings (e.g., 8 strands, top-2 = 4× savings).

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
        self.register_buffer("_last_balance_loss", torch.tensor(0.0), persistent=False)
        self.register_buffer("_last_router_entropy", torch.tensor(0.0), persistent=False)
        self._last_top_indices = None
        self._last_top_weights = None
        self.activation_topics: dict[int, Counter[str]] = {}

    def forward(self, x: Tensor) -> tuple[Tensor, Tensor]:
        """Route tokens to top-k Strands and combine outputs.

        Uses dense weighted summation (all N strands process all tokens,
        then outputs are masked via router weights) to avoid PyTorch
        autograd issues with dynamic gather/scatter of variable-size batches.

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

        # ── Sparse Strand routing ──────────────────────────────────────
        # Process each strand only for the batch of tokens routed to it.
        # We concat all selected tokens per strand (variable M), process
        # with the strand, then scatter results back to output positions.
        # This gives N/K × compute savings.
        flat_indices = top_indices.reshape(B * T * K)  # (B*T*K,)
        flat_weights = top_weights.reshape(B * T * K, 1)  # (B*T*K, 1)
        flat_x = x.unsqueeze(2).expand(-1, -1, K, -1).reshape(B * T * K, -1)  # (B*T*K, H)

        unique_strands, inverse = torch.unique(flat_indices, return_inverse=True)
        unique_strands_list = unique_strands.tolist()

        weight_cache = {
            int(s_id): self.strands[int(s_id)].genome.generate_all(
                self.strands[int(s_id)].strand_id
            )
            for s_id in unique_strands_list
        }

        # Collect contributions per strand for a single deterministic scatter.
        all_batch: list[Tensor] = []
        all_time: list[Tensor] = []
        all_contrib: list[Tensor] = []

        for s_id in unique_strands_list:
            mask = inverse == int(s_id)  # (B*T*K,) bool
            count = mask.sum()
            if count == 0:
                continue

            self._usage_counts[s_id] += count.item()

            # ── Gather: (M, 1, H) ─────────────────────────────────────
            indices_s = torch.where(mask)[0]  # (M,)  long, no grad
            x_s = flat_x.index_select(0, indices_s).unsqueeze(1)  # (M, 1, H)
            w_s = flat_weights.index_select(0, indices_s)  # (M, 1)

            # ── Process ────────────────────────────────────────────────
            out_s = self.strands[s_id](x_s, weights=weight_cache[int(s_id)])
            out_s = out_s.squeeze(1)  # (M, H)

            # ── Scatter indices ────────────────────────────────────────
            remainder = indices_s % (T * K)
            batch_i = indices_s // (T * K)
            time_i = remainder // K

            all_batch.append(batch_i)
            all_time.append(time_i)
            all_contrib.append(out_s * w_s)  # (M, H)

        if all_contrib:
            output = torch.zeros_like(x)
            flat_batch = torch.cat(all_batch)  # (total_M,)
            flat_time = torch.cat(all_time)
            flat_contrib = torch.cat(all_contrib, dim=0)  # (total_M, H)
            output = output.index_put(
                (flat_batch, flat_time), flat_contrib, accumulate=True
            )
        else:
            output = torch.zeros_like(x)

        # Load-balancing loss: encourage even distribution across Strands
        # Standard Switch Transformer formulation: N * sum(f_i * P_i)
        # where f_i = fraction of tokens routed to expert i and P_i = avg probability
        routing_probs_all = torch.softmax(scores, dim=-1)  # (B, T, N) — full probability
        probs_mean = routing_probs_all.mean(dim=(0, 1))  # (N,) — P_i

        # f_i: fraction of top-k routing decisions assigned to each expert
        f_i = torch.zeros(N, device=scores.device, dtype=scores.dtype)
        f_i.scatter_add_(0, flat_indices, torch.ones_like(flat_indices, dtype=scores.dtype))
        f_i = f_i / (B * T * K)  # normalize to fraction

        balance_loss = N * (f_i * probs_mean).sum()

        entropy = -(probs_mean * probs_mean.clamp_min(1e-9).log()).sum()
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

        ref_device = self.strands[0].norm.weight.device if self.strands else None
        self.strands.append(Strand(
            self.strands[0].genome, strand_id=strand_id,
            config=self.config.strand, device=ref_device,
        ))
        self.config.num_strands = new_n

        old_counts = self._usage_counts
        new_counts = torch.zeros(new_n, device=old_counts.device)
        new_counts[:old_n].copy_(old_counts)
        self.register_buffer("_usage_counts", new_counts, persistent=False)
        logger.info("NeuralMesh: added strand %d (%d -> %d)", strand_id, old_n, new_n)
