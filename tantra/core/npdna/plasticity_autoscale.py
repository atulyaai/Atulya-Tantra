"""Plasticity auto-scaling — add strands, layers, prune cortex."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlasticityMetrics:
    strand_load: float = 0.0
    layer_loss_plateau: int = 0
    cortex_unused: int = 0
    last_check: float = field(default_factory=time.time)


class PlasticityAutoScaler:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._metrics = PlasticityMetrics()
        self._actions: list[dict[str, Any]] = []

    def check_and_scale(self, strand_capacity: float, loss_history: list[float], cortex_size: int, cortex_used: int) -> list[str]:
        """Auto-scale based on current metrics."""
        actions = []
        self._metrics.strand_load = strand_capacity
        self._metrics.cortex_unused = cortex_size - cortex_used

        # Auto-add strands when all are loaded
        if strand_capacity > 0.9:
            actions.append("add_strand")
            self._actions.append({"action": "add_strand", "timestamp": time.time(), "reason": f"strand_load={strand_capacity}"})

        # Auto-add layers when loss plateaus
        if len(loss_history) >= 10:
            recent = loss_history[-10:]
            if max(recent) - min(recent) < 0.001:
                actions.append("add_layer")
                self._metrics.layer_loss_plateau += 1
                self._actions.append({"action": "add_layer", "timestamp": time.time(), "reason": "loss_plateau"})

        # Auto-prune unused cortex entries
        if cortex_size > 0 and (cortex_size - cortex_used) / cortex_size > 0.5:
            actions.append("prune_cortex")
            self._actions.append({"action": "prune_cortex", "timestamp": time.time(), "reason": f"unused={cortex_size - cortex_used}"})

        self._metrics.last_check = time.time()
        return actions

    def get_metrics(self) -> dict[str, Any]:
        return vars(self._metrics)

    def get_action_history(self) -> list[dict[str, Any]]:
        return self._actions[-50:]
