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

    @property
    def strand_ids(self) -> list[int]:
        return [s.strand_id for s in self.strands]

    @property
    def num_strands(self) -> int:
        return len(self.strands)

    def add_strand(self, strand_id: int) -> None:
        """Add one routed Strand and expand router/usage state in place."""
        H = self.config.strand.hidden_size
        old_router = self.router
        old_n = len(self.strands)
        new_n = old_n + 1

        new_router = nn.Linear(
            H,
            new_n,
            bias=old_router.bias is not None,
            device=old_router.weight.device,
            dtype=old_router.weight.dtype,
        )
        with torch.no_grad():
            new_router.weight[:old_n].copy_(old_router.weight)
            scale = old_router.weight.detach().std().clamp_min(1e-5)
            new_router.weight[old_n].normal_(mean=0.0, std=float(scale))
            if old_router.bias is not None and new_router.bias is not None:
                new_router.bias[:old_n].copy_(old_router.bias)
                new_router.bias[old_n].zero_()

        ref_device = self.strands[0].norm.weight.device if self.strands else old_router.weight.device
        self.router = new_router
        self.strands.append(Strand(
            self.strands[0].genome,
            strand_id=strand_id,
            config=self.config.strand,
            device=ref_device,
        ))

        old_counts = self._usage_counts
        new_counts = torch.zeros(new_n, device=old_counts.device, dtype=old_counts.dtype)
        new_counts[:old_n].copy_(old_counts)
        self.register_buffer("_usage_counts", new_counts, persistent=False)
        self.config.num_strands = new_n
        logger.info("NeuralMesh: added strand %d (%d -> %d)", strand_id, old_n, new_n)

    def _remove_strand(self, strand_id: int) -> None:
        """Remove a strand by its ID and shrink the router."""
        idx = None
        for i, s in enumerate(self.strands):
            if s.strand_id == strand_id:
                idx = i
                break
        if idx is None:
            raise ValueError(f"Strand {strand_id} not found")
        if len(self.strands) <= 1:
            raise ValueError("Cannot remove last strand")

        with torch.no_grad():
            old_w = self.router.weight.data
            new_w = torch.cat([old_w[:idx], old_w[idx + 1:]], dim=0)
            old_b = self.router.bias.data if self.router.bias is not None else None
            new_n = len(self.strands) - 1
            self.router = nn.Linear(
                self.router.in_features, new_n, bias=old_b is not None,
                device=old_w.device,
            )
            self.router.weight.data[:] = new_w
            if old_b is not None:
                self.router.bias.data[:] = torch.cat([old_b[:idx], old_b[idx + 1:]])
            del self.strands[idx]
            self._usage_counts = torch.cat(
                [self._usage_counts[:idx], self._usage_counts[idx + 1:]]
            )

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

        # Store for Plasticity merge detection
        self._last_top_indices = top_indices.detach()
        self._last_top_weights = top_weights.detach()

        # Softmax over top-k weights only
        top_weights = top_weights.softmax(dim=-1)  # (B, T, K)

        # All strands process input (dense), then mask
        stacked = torch.stack([s(x) for s in self.strands], dim=-2)  # (B, T, N, H)

        # Build one-hot mask from top_indices
        mask = torch.zeros(B, T, N, 1, device=x.device, dtype=stacked.dtype)
        mask.scatter_(-2, top_indices.unsqueeze(-1).expand(-1, -1, -1, 1), 1.0)
        # Weight by router probabilities
        weights_full = torch.zeros(B, T, N, 1, device=x.device, dtype=stacked.dtype)
        weights_full.scatter_(-2, top_indices.unsqueeze(-1).expand(-1, -1, -1, 1),
                              top_weights.unsqueeze(-1))
        masked = stacked * mask * weights_full  # (B, T, N, H)
        output = masked.sum(dim=-2)  # (B, T, H)

        # Track usage
        with torch.no_grad():
            usage = top_indices.flatten().bincount(minlength=N)
            self._usage_counts.copy_(self._usage_counts + usage.float())

        # Balance loss (auxiliary load balancing)
        f_i = top_indices.flatten().bincount(minlength=N).float() / max(1, B * T * K)
        router_probs = scores.softmax(dim=-1).mean(dim=(0, 1))  # (N,)
        balance_loss = N * (f_i * router_probs).sum()
        entropy = -(router_probs * router_probs.clamp_min(1e-9).log()).sum()
        entropy = entropy / torch.log(torch.tensor(max(1.0, float(N)), device=x.device))
        self._last_balance_loss.copy_(balance_loss.detach())
        self._last_router_entropy.copy_(entropy.detach())

        return output, balance_loss * self.config.balance_weight

    # ── Plasticity diagnostics properties ──────────────────────────────────

    @property
    def usage_stats(self) -> dict[int, float]:
        """Return per-strand usage ratios (0..1)."""
        total = self._usage_counts.sum().item()
        if total == 0:
            return {i: 0.0 for i in range(len(self.strands))}
        return {i: float(c.item() / total) for i, c in enumerate(self._usage_counts)}

    @property
    def last_balance_loss(self) -> float:
        return float(self._last_balance_loss.item())

    @property
    def last_router_entropy(self) -> float:
        return float(self._last_router_entropy.item())

    def reset_usage(self) -> None:
        self._usage_counts.zero_()

    def specialization_report(self) -> dict[str, dict[str, float]]:
        """Unused in NeuralMesh, only meaningful for CategoryMesh."""
        return {}

# ── CategoryMesh ──────────────────────────────────────────────────────────────

class CategoryMesh(nn.Module):
    """Category-fixed expert routing.

    Router classifies each token into categories (math, code, conversation, etc.)
    instead of individual strands. Each category has dedicated strand(s) that ONLY
    train on data of that category.

    Benefits over standard NeuralMesh:
      - Guaranteed specialization: every strand trains on its category's data
      - No "dead strand" problem: each category always gets relevant data
      - Simpler router: classify 5-10 categories vs 100+ strands
      - Data categories provide curriculum control

    The category → strand mapping is fixed at init:
        category "math" → strands [0,1,2,3]
        category "code" → strands [4,5,6,7]
        ...
    """

    def __init__(
        self,
        genome: Genome,
        config: MeshConfig,
        categories: list[tuple[str, int]],  # [(name, count), ...]
        layer_offset: int = 0,
    ):
        super().__init__()
        self.config = config
        self.categories = categories  # [(name, count), ...]
        H = config.strand.hidden_size

        # Build category → strand ID mapping
        self.category_names: list[str] = [c[0] for c in categories]
        self.category_counts: list[int] = [c[1] for c in categories]
        num_categories = len(categories)
        num_strands = sum(c[1] for c in categories)

        # Router: hidden_size → num_categories (categories, not individual strands!)
        self.router = nn.Linear(H, num_categories, bias=False)

        # Create category-to-strand mapping
        self.category_to_strand_id: dict[str, list[int]] = {}
        self.strand_to_category: dict[int, str] = {}
        strand_offset = layer_offset
        for cat_name, cat_count in categories:
            strand_ids = list(range(strand_offset, strand_offset + cat_count))
            self.category_to_strand_id[cat_name] = strand_ids
            for sid in strand_ids:
                self.strand_to_category[sid] = cat_name
            strand_offset += cat_count

        # Create strands with category tags
        self.strands = nn.ModuleList()
        for cat_name, cat_count in categories:
            for i in range(cat_count):
                sid = self.category_to_strand_id[cat_name][i]
                self.strands.append(Strand(
                    genome, strand_id=sid, config=config.strand,
                    category=cat_name,
                ))

        self.num_strands = num_strands

        # Usage stats
        self.register_buffer(
            "_usage_counts",
            torch.zeros(num_strands),
            persistent=False,
        )
        self.register_buffer("_last_balance_loss", torch.tensor(0.0), persistent=False)
        self.register_buffer("_last_router_entropy", torch.tensor(0.0), persistent=False)
        self._last_top_indices = None
        self._last_top_weights = None

    @property
    def strand_ids(self) -> list[int]:
        return [s.strand_id for s in self.strands]

    @property
    def num_strands(self) -> int:
        return len(self.strands)

    def _remove_strand(self, strand_id: int) -> None:
        """Remove a strand by its ID and shrink the router."""
        idx = None
        for i, s in enumerate(self.strands):
            if s.strand_id == strand_id:
                idx = i
                break
        if idx is None:
            raise ValueError(f"Strand {strand_id} not found")
        if len(self.strands) <= 1:
            raise ValueError("Cannot remove last strand")

        with torch.no_grad():
            # Remove from router: num_strands decreases by 1
            old_w = self.router.weight.data  # [N, H]
            new_w = torch.cat([old_w[:idx], old_w[idx + 1:]], dim=0)
            old_b = self.router.bias.data if self.router.bias is not None else None
            self.router = nn.Linear(
                self.router.in_features, len(self.strands) - 1, bias=old_b is not None,
                device=old_w.device,
            )
            self.router.weight.data[:] = new_w
            if old_b is not None:
                clipped_b = torch.cat([old_b[:idx], old_b[idx + 1:]], dim=0)
                self.router.bias.data[:] = clipped_b

            # Remove from strands ModuleList
            del self.strands[idx]

            # Resize usage counts
            old_counts = self._usage_counts.data
            new_counts = torch.cat([old_counts[:idx], old_counts[idx + 1:]])
            self._usage_counts = new_counts

        # Update config num_strands
        self.config.num_strands = len(self.strands)

        logger.info(
            "NeuralMesh: removed strand %s (%d strands remain)",
            strand_id, self.num_strands,
        )

    def forward(self, x: Tensor, category_filter: str | None = None) -> tuple[Tensor, Tensor]:
        """Forward pass with category-aware routing.

        Args:
            x: Input (batch, seq_len, hidden_size).
            category_filter: When set (training with category-tagged data),
                             only route to strands of this category. The router
                             is optionally bypassed (all tokens go to the
                             matching category).

        Returns:
            (output, balance_loss)
        """
        B, T, H = x.shape
        N = self.num_strands
        num_cats = len(self.categories)
        K = min(self.config.top_k, num_cats)

        if category_filter and category_filter in self.category_to_strand_id:
            # ── Training shortcut: route ALL tokens to matching category ──
            # The router still learns but we guarantee the right category learns
            strand_ids = self.category_to_strand_id[category_filter]
            scores = self.router(x)  # (B, T, num_cats) — still compute for router grad

            # Force routing: all tokens → matching category's strands
            # We still process via strands for the weighted combination
            cat_idx = self.category_names.index(category_filter)
            cat_scores = scores[:, :, cat_idx:cat_idx+1]  # (B, T, 1)
            # Distribute tokens among the category's strands evenly
            num_cat_strands = len(strand_ids)
            strand_scores = torch.zeros(B, T, N, device=x.device)
            for i, sid in enumerate(strand_ids):
                # Each strand gets the category score / num_cat_strands
                strand_scores[:, :, sid] = cat_scores[:, :, 0] / num_cat_strands

            # Generate weights for this category's strands only
            weight_cache = {
                sid: self.strands[sid].genome.generate_all(self.strands[sid].strand_id)
                for sid in strand_ids
            }

            # Process each strand
            output = torch.zeros_like(x)
            for sid in strand_ids:
                strand_idx = self._strand_idx_by_id(sid)
                if strand_idx is None:
                    continue
                out_s = self.strands[strand_idx](x, weights=weight_cache.get(sid))
                self._usage_counts[sid] += B * T
                # Weight by the strand's router score
                weight = strand_scores[:, :, sid:sid+1]  # (B, T, 1)
                output = output + out_s * weight

            # Balance loss: encourage even distribution within the category
            f_i = torch.zeros(N, device=x.device)
            f_i[strand_ids] = 1.0 / len(strand_ids)
            probs_mean = torch.softmax(scores, dim=-1).mean(dim=(0, 1))  # (num_cats,)
            # Map category probs to strand space
            strand_probs = torch.zeros(N, device=x.device)
            for j, (cat_name, _) in enumerate(self.categories):
                for sid in self.category_to_strand_id[cat_name]:
                    strand_probs[sid] = probs_mean[j] / len(self.category_to_strand_id[cat_name])
            balance_loss = N * (f_i * strand_probs).sum()

            self._last_balance_loss.copy_(balance_loss.detach())
            return output, balance_loss * self.config.balance_weight

        else:
            # ── Normal routing: router chooses top-k categories ──
            scores = self.router(x)  # (B, T, num_cats)
            top_weights, top_indices = torch.topk(scores, K, dim=-1)  # (B, T, K)
            top_weights = torch.softmax(top_weights, dim=-1)

            # Map category indices to strand indices
            # top_indices is (B, T, K) — each entry is a category index
            # For each category, distribute weight across its strands

            flat_indices = top_indices.reshape(B * T * K)  # (B*T*K,)
            flat_weights = top_weights.reshape(B * T * K, 1)  # (B*T*K, 1)
            flat_x = x.unsqueeze(2).expand(-1, -1, K, -1).reshape(B * T * K, -1)  # (B*T*K, H)

            # Collect unique categories
            unique_cats = torch.unique(flat_indices)
            unique_cat_names = [self.category_names[int(c)] for c in unique_cats]

            # Build weight cache for all strands in selected categories
            weight_cache = {}
            for cat_name in unique_cat_names:
                for sid in self.category_to_strand_id[cat_name]:
                    strand_idx = self._strand_idx_by_id(sid)
                    if strand_idx is not None:
                        weight_cache[sid] = self.strands[strand_idx].genome.generate_all(
                            self.strands[strand_idx].strand_id
                        )

            # Process strands per category
            output = torch.zeros_like(x)
            all_flat_indices_list = []
            all_contrib = []

            for cat_idx in unique_cats:
                cat_name = self.category_names[int(cat_idx)]
                strand_ids = self.category_to_strand_id[cat_name]
                num_cat_strands = len(strand_ids)

                # Find which tokens were routed to this category
                cat_mask = flat_indices == cat_idx  # (B*T*K,) bool
                if cat_mask.sum() == 0:
                    continue

                # For each strand in this category, process a share of the weight
                for i, sid in enumerate(strand_ids):
                    strand_idx = self._strand_idx_by_id(sid)
                    if strand_idx is None:
                        continue

                    # Each strand gets category_score / num_cat_strands
                    indices_s = torch.where(cat_mask)[0]
                    w_s = flat_weights.index_select(0, indices_s) / num_cat_strands
                    x_s = flat_x.index_select(0, indices_s).unsqueeze(1)  # (M, 1, H)

                    out_s = self.strands[strand_idx](x_s, weights=weight_cache.get(sid))
                    out_s = out_s.squeeze(1)  # (M, H)

                    self._usage_counts[sid] += indices_s.shape[0]

                    # Scatter back
                    remainder = indices_s % (T * K)
                    batch_i = indices_s // (T * K)
                    time_i = remainder // K

                    output = output.index_put(
                        (batch_i, time_i), out_s * w_s, accumulate=True
                    )

            # Load-balancing loss
            routing_probs_all = torch.softmax(scores, dim=-1)
            probs_mean = routing_probs_all.mean(dim=(0, 1))  # (num_cats,)

            f_i = torch.zeros(N, device=x.device)
            # f_i per strand: for each category, distribute evenly to its strands
            for j in range(num_cats):
                cat_strand_ids = self.category_to_strand_id[self.category_names[j]]
                for sid in cat_strand_ids:
                    f_i[sid] = 1.0 / len(cat_strand_ids)

            # Actual routing frequencies per strand
            for j, cat_name in enumerate(self.categories):
                cat_strand_ids = self.category_to_strand_id[cat_name[0]]
                cat_usage = (flat_indices == j).float().sum()
                for sid in cat_strand_ids:
                    f_i[sid] *= cat_usage / (cat_usage.sum() + 1e-8)

            strand_probs = torch.zeros(N, device=x.device)
            for j, (cat_name, _) in enumerate(self.categories):
                for sid in self.category_to_strand_id[cat_name]:
                    strand_probs[sid] = probs_mean[j] / len(self.category_to_strand_id[cat_name])

            balance_loss = N * (f_i * strand_probs).sum()
            entropy = -(probs_mean * probs_mean.clamp_min(1e-9).log()).sum()
            entropy = entropy / torch.log(torch.tensor(
                max(1.0, float(num_cats)), device=x.device
            ))

            self._last_balance_loss.copy_(balance_loss.detach())
            self._last_router_entropy.copy_(entropy.detach())

            return output, balance_loss * self.config.balance_weight

    def _strand_idx_by_id(self, strand_id: int) -> int | None:
        """Find local index in self.strands for a genome strand_id."""
        for i, s in enumerate(self.strands):
            if s.strand_id == strand_id:
                return i
        return None

    @property
    def usage_stats(self) -> dict[int, float]:
        total = self._usage_counts.sum().item()
        if total == 0:
            return {i: 0.0 for i in range(self.num_strands)}
        return {
            i: self._usage_counts[i].item() / total
            for i in range(self.num_strands)
        }

    @property
    def last_balance_loss(self) -> float:
        return float(self._last_balance_loss.item())

    @property
    def last_router_entropy(self) -> float:
        return float(self._last_router_entropy.item())

    def reset_usage(self) -> None:
        self._usage_counts.zero_()

    def specialization_report(self) -> dict[str, dict[str, float]]:
        """Report what each category's strands are used for."""
        report = {}
        for cat_name, count in self.categories:
            strand_ids = self.category_to_strand_id[cat_name]
            usages = {sid: float(self._usage_counts[sid].item()) for sid in strand_ids}
            total = sum(usages.values()) or 1.0
            report[cat_name] = {
                "strand_ids": strand_ids,
                "usage_share": {sid: u/total for sid, u in usages.items()},
                "total_usage": total,
            }
        return report

    def add_strand(self, strand_id: int) -> None:
        """Add one routed Strand to this mesh and expand router/usage state."""
        H = self.config.strand.hidden_size
        old_router = self.router
        n_cats = len(self.categories)

        new_router = nn.Linear(H, n_cats, bias=False, device=old_router.weight.device)
        with torch.no_grad():
            new_router.weight.copy_(old_router.weight)
        self.router = new_router

        ref_device = self.strands[0].norm.weight.device if self.strands else None
        self.strands.append(Strand(
            self.strands[0].genome, strand_id=strand_id,
            config=self.config.strand, device=ref_device,
        ))
        old_n = self.num_strands
        self.num_strands = old_n + 1

        old_counts = self._usage_counts
        new_counts = torch.zeros(self.num_strands, device=old_counts.device)
        new_counts[:old_n].copy_(old_counts)
        self.register_buffer("_usage_counts", new_counts, persistent=False)
        logger.info("CategoryMesh: added strand %d (%d -> %d)", strand_id, old_n, self.num_strands)
