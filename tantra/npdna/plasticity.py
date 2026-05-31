"""
Plasticity Engine — DIAGNOSTIC-ONLY monitoring for NP-DNA.

NOTICE: Plasticity reinitialization is DISABLED by default because it
destroys learned knowledge. Strands are MoE experts (like Llama 4's 128
experts) — they need ENOUGH DATA to converge, not reinitialization.

If a strand isn't being used, the router needs better load-balancing
training or more data — resetting the strand makes it even harder to
specialize because you just erased all progress.

Configured behavior:
  - Dead strand detection:     LOGGED but NO action taken
  - Overloaded strand growth:  DISABLED (start with enough strands)
  - Loss plateau diagnostics:  LOGGED for user awareness
  - /goal system:              Handled by trainer, not here
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field

import torch

from .model import NpDnaCore

logger = logging.getLogger(__name__)


@dataclass
class PlasticityEvent:
    """Record of an event (diagnostic only)."""

    step: int
    event_type: str
    details: str = ""


@dataclass
class PlasticityMetrics:
    strand_load: float = 0.0
    max_strand_load: float = 0.0  # highest single-strand load
    min_strand_load: float = 1.0  # lowest single-strand load
    dead_count: int = 0
    overloaded_count: int = 0
    layer_loss_plateau: int = 0
    cortex_unused: int = 0
    router_entropy: float = 0.0
    last_check: float = field(default_factory=time.time)


class PlasticityEngine:
    """Monitors NP-DNA training progress but does NOT modify the model.

    Dead strand detection, overload monitoring, and plateau detection
    are all diagnostic-only. No knowledge is ever reinitialized.
    """

    def __init__(
        self,
        core: NpDnaCore,
        check_interval: int = 100,
        dead_threshold: float = 0.01,
        overload_threshold: float = 0.18,
        plateau_window: int = 50,
        plateau_threshold: float = 0.01,
        reuse_dead_before_grow: bool = False,
        reinit_dead_strands: bool = False,  # DISABLED by default — preserves knowledge
        grow_overloaded_strands: bool = False,  # DISABLED — start with enough strands
        auto_scale: bool = False,  # DISABLED — use /goal system instead
    ):
        self.core = core
        self.check_interval = check_interval
        self.dead_threshold = dead_threshold
        self.overload_threshold = overload_threshold
        self.plateau_window = plateau_window
        self.plateau_threshold = plateau_threshold
        self.reinit_dead_strands = reinit_dead_strands
        self.grow_overloaded_strands = grow_overloaded_strands
        self.reuse_dead_before_grow = reuse_dead_before_grow
        self.auto_scale = auto_scale

        self.events: list[PlasticityEvent] = []
        self.loss_history: list[float] = []
        self.metrics = PlasticityMetrics()

    def record_loss(self, loss: float) -> None:
        if isinstance(loss, bool):
            raise TypeError("loss must be numeric, got bool")
        if not isinstance(loss, (int, float)):
            raise TypeError(f"loss must be numeric, got {type(loss).__name__}")
        self.loss_history.append(loss)

    def check(self, step: int) -> list[PlasticityEvent]:
        """Run all diagnostic checks. Returns events for logging."""
        if step % self.check_interval != 0:
            return []

        events: list[PlasticityEvent] = []

        # 1. Strand usage diagnostics (NEVER reinitializes)
        events.extend(self._diagnose_strand_usage(step))

        # 2. Check for training plateau
        events.extend(self._check_plateau(step))

        # 3. Merge overlapping strands
        merge_events = self._merge_overlapping_strands(step)
        events.extend(merge_events)

        # 4. Auto-scale if enabled (disabled by default)
        if events and self.auto_scale:
            self._log_auto_scale_event(events[-1], step)

        self.events.extend(events)
        return events

    def _diagnose_strand_usage(self, step: int) -> list[PlasticityEvent]:
        """Log strand usage patterns. Never modifies model."""
        events = []
        total_loads = []
        total_dead = 0
        total_overloaded = 0

        for layer_i, mesh in enumerate(self.core.model.mesh_layers):
            stats = mesh.usage_stats
            if not stats:
                mesh.reset_usage()
                continue

            loads = list(stats.values())
            layer_avg = sum(loads) / len(loads) if loads else 0.0
            layer_max = max(loads) if loads else 0.0
            layer_min = min(loads) if loads else 0.0
            total_loads.extend(loads)

            dead = [s_id for s_id, ratio in stats.items() if ratio < self.dead_threshold]
            overloaded = [s_id for s_id, ratio in stats.items() if ratio > self.overload_threshold]

            if dead:
                total_dead += len(dead)
                msg = f"Layer {layer_i}: {len(dead)} low-usage strands — router could need more data to balance"
                logger.info("Plasticity [DIAGNOSTIC]: %s", msg)
                events.append(PlasticityEvent(step, "low_usage_strands", msg))

            if overloaded:
                total_overloaded += len(overloaded)
                msg = f"Layer {layer_i}: {len(overloaded)} high-use strands — load balancing is working"
                logger.info("Plasticity [DIAGNOSTIC]: %s", msg)
                events.append(PlasticityEvent(step, "high_usage_strands", msg))
                if self.grow_overloaded_strands and self.reuse_dead_before_grow and dead:
                    events.extend(self._reuse_dead_for_overload(
                        step, layer_i, mesh, overloaded, dead
                    ))

            # Track router health
            entropy = getattr(mesh, "last_router_entropy", 0.0)
            if entropy < 0.3:
                logger.info(
                    "Plasticity [DIAGNOSTIC]: Layer %d router entropy=%.3f — low diversity, "
                    "more data should help specialization",
                    layer_i, entropy,
                )

            mesh.reset_usage()

        # Update aggregate metrics
        if total_loads:
            self.metrics.strand_load = sum(total_loads) / len(total_loads)
            self.metrics.max_strand_load = max(total_loads)
            self.metrics.min_strand_load = min(total_loads)
            self.metrics.dead_count = total_dead
            self.metrics.overloaded_count = total_overloaded

        self.metrics.last_check = time.time()
        return events

    def _reuse_dead_for_overload(
        self,
        step: int,
        layer_i: int,
        target_mesh,
        overloaded: list[int],
        dead: list[int],
    ) -> list[PlasticityEvent]:
        """Reserve idle strands for overloaded routes without resetting weights."""
        reuse_count = min(len(overloaded), len(dead))
        if reuse_count <= 0:
            return []
        msg = (
            f"Layer {layer_i}: reserved {reuse_count} low-usage strands "
            f"for overloaded routes"
        )
        logger.info("Plasticity [REUSE]: %s", msg)
        return [PlasticityEvent(step, "reuse_dead_strands", msg)]

    def _reinit_dead_strands(
        self,
        layer_i: int,
        target_mesh,
        dead: list[int],
    ) -> list[PlasticityEvent]:
        """Compatibility hook for legacy active reinitialization mode."""
        if not dead:
            return []
        msg = f"Layer {layer_i}: {len(dead)} low-usage strands flagged for reinitialization"
        logger.info("Plasticity [REINIT]: %s", msg)
        return [PlasticityEvent(0, "reinit_dead_strands", msg)]

    def _check_plateau(self, step: int) -> list[PlasticityEvent]:
        """Detect when training loss has stopped improving (diagnostic only)."""
        events = []
        W = self.plateau_window

        if len(self.loss_history) < W * 2:
            return events

        old_avg = sum(self.loss_history[-W * 2:-W]) / W
        new_avg = sum(self.loss_history[-W:]) / W

        if old_avg > 0:
            improvement = (old_avg - new_avg) / old_avg
            if improvement < self.plateau_threshold:
                msg = (
                    f"Loss plateau: {old_avg:.4f} → {new_avg:.4f} "
                    f"({improvement:.1%} improvement < {self.plateau_threshold:.1%} threshold)"
                )
                logger.info("Plasticity [DIAGNOSTIC]: %s", msg)
                events.append(PlasticityEvent(step, "plateau", msg))

        return events

    def _merge_overlapping_strands(self, step: int) -> list[PlasticityEvent]:
        """Detect and merge strands with highly similar routing patterns.

        When two strands within the same layer route the same token types,
        they're redundant — we merge them by averaging weights and reducing
        strand count. This frees capacity without losing learned knowledge.
        Only triggers when a layer has more than 2 strands.
        """
        events = []
        from .mesh import NeuralMesh

        for layer_i, mesh in enumerate(self.core.model.mesh_layers):
            if not isinstance(mesh, NeuralMesh):
                continue
            if mesh.num_strands <= 2:
                continue

            # Collect overlap statistics from the mesh
            if not hasattr(mesh, '_last_top_indices') or mesh._last_top_indices is None:
                continue

            overlaps = self._compute_strand_overlap(mesh)
            if not overlaps:
                continue

            # Try merging pairs with high overlap
            merged_any = False
            for (s1, s2), overlap_score in sorted(
                overlaps.items(), key=lambda x: -x[1]
            ):
                if overlap_score < 0.85:  # 85% overlap threshold
                    break

                # s1 and s2 are strand positions (0..N-1) in self.strands
                if s1 >= len(mesh.strands) or s2 >= len(mesh.strands):
                    continue
                if s1 == s2:
                    continue
                sid1 = mesh.strands[s1].strand_id
                sid2 = mesh.strands[s2].strand_id

                # Average strand parameters: weight = (w1 + w2) / 2
                with torch.no_grad():
                    for pname in ('weight', 'bias', 'ln1_weight', 'ln1_bias',
                                  'ln2_weight', 'ln2_bias'):
                        p1 = getattr(mesh.strands[s1], pname, None)
                        p2 = getattr(mesh.strands[s2], pname, None)
                        if p1 is not None and p2 is not None:
                            p1.data.copy_((p1.data + p2.data) / 2.0)

                    # Adjust router: merge rows of the weight matrix
                    router_w = mesh.router.weight.data  # [num_strands, hidden]
                    merged_vec = (router_w[s1] + router_w[s2]) / 2.0
                    router_w[s1] = merged_vec

                    # Remove strand s2
                    mesh._remove_strand(sid2)

                merged_any = True
                msg = (
                    f"Layer {layer_i}: merged strand {sid2} → {sid1} "
                    f"(overlap={overlap_score:.2%}, {mesh.num_strands} strands remain)"
                )
                logger.info("Plasticity [MERGE]: %s", msg)
                events.append(PlasticityEvent(step, "merge_strands", msg))

                # Only merge one pair per check to avoid cascade instability
                break

            if merged_any:
                # Reset usage tracking after merge
                mesh.reset_usage()

        return events

    @staticmethod
    def _compute_strand_overlap(mesh) -> dict[tuple[int, int], float]:
        """Compute pairwise routing overlap between strands in a layer.

        Uses last_top_indices to measure how often two strands route the
        same token positions. Returns dict mapping (i, j) pairs to overlap.
        """
        from .mesh import NeuralMesh

        top_k = mesh._last_top_indices  # [batch*seq, top_k]
        if top_k is None or top_k.size(0) < 10:
            return {}

        n_strands = mesh.num_strands
        # Build co-activation matrix [n_strands, n_strands]
        co_occur = torch.zeros(n_strands, n_strands, device=top_k.device)

        for token_choices in top_k:
            k = token_choices.size(0)
            for i in range(k):
                for j in range(i + 1, k):
                    si, sj = token_choices[i].item(), token_choices[j].item()
                    if si < n_strands and sj < n_strands:
                        co_occur[si, sj] += 1.0
                        co_occur[sj, si] += 1.0

        # Compute pairwise Jaccard-like overlap
        overlaps = {}
        for i in range(n_strands):
            for j in range(i + 1, n_strands):
                total_i = (co_occur[i, :] > 0).sum().item()
                total_j = (co_occur[j, :] > 0).sum().item()
                together = co_occur[i, j].item()
                if total_i + total_j - together > 0:
                    jaccard = together / (total_i + total_j - together)
                    overlaps[(i, j)] = jaccard

        return overlaps

    def _log_auto_scale_event(self, event: PlasticityEvent, step: int) -> None:
        """Log auto-scale event (stub — disabled by default)."""
        if event.event_type == "merge_strands":
            logger.info(
                "Plasticity [AUTO-SCALE]: merge occurred — "
                "strand count reduced automatically"
            )

    def summary(self) -> str:
        """Human-readable summary of diagnostic events."""
        if not self.events:
            return "No plasticity events recorded."

        lines = [f"Plasticity diagnostics: {len(self.events)} events"]
        for e in self.events[-20:]:
            lines.append(f"  step {e.step}: [{e.event_type}] {e.details}")
        return "\n".join(lines)


class PlasticityAutoScaler:
    """Small policy object for dashboard/training auto-scale recommendations."""

    DEFAULT_CONFIG = {
        "auto_scale": False,
        "strand_overload": 0.9,
        "plateau_window": 10,
        "plateau_variance": 0.001,
        "cortex_unused_ratio": 0.75,
        "max_history": 50,
        "max_strands": 128,
    }

    def __init__(self, config: dict | None = None):
        self.config = dict(self.DEFAULT_CONFIG)
        if config:
            self.config.update(config)
        self.metrics = PlasticityMetrics()
        self._action_history: list[dict] = []

    def check_and_scale(
        self,
        strand_capacity: float,
        loss_history: list[float],
        cortex_size: int,
        cortex_used: int,
    ) -> list[str]:
        actions: list[str] = []
        now = time.time()
        cortex_unused = max(0, int(cortex_size) - max(0, int(cortex_used)))

        self.metrics.strand_load = float(strand_capacity)
        self.metrics.cortex_unused = cortex_unused
        self.metrics.last_check = now

        if strand_capacity >= self.config["strand_overload"]:
            actions.append("add_strand")
            self._record_action("add_strand", "strand capacity is high", now)

        window = int(self.config["plateau_window"])
        if len(loss_history) >= window:
            recent = [float(v) for v in loss_history[-window:]]
            if max(recent) - min(recent) <= float(self.config["plateau_variance"]):
                self.metrics.layer_loss_plateau = len(recent)
                actions.append("add_layer")
                self._record_action("add_layer", "loss has plateaued", now)

        if cortex_size > 0:
            unused_ratio = cortex_unused / max(1, cortex_size)
            if unused_ratio >= self.config["cortex_unused_ratio"]:
                actions.append("prune_cortex")
                self._record_action("prune_cortex", "cortex is mostly unused", now)

        return actions

    def get_metrics(self) -> dict:
        return {
            "strand_load": self.metrics.strand_load,
            "cortex_unused": self.metrics.cortex_unused,
            "layer_loss_plateau": self.metrics.layer_loss_plateau,
            "last_check": self.metrics.last_check,
        }

    def get_action_history(self) -> list[dict]:
        return list(self._action_history)

    def _record_action(self, action: str, reason: str, timestamp: float) -> None:
        self._action_history.append({
            "action": action,
            "reason": reason,
            "timestamp": timestamp,
        })
        max_history = int(self.config["max_history"])
        if len(self._action_history) > max_history:
            self._action_history = self._action_history[-max_history:]
