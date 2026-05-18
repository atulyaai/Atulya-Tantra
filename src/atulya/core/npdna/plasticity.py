"""Plasticity Engine — self-monitoring and auto-scaling for NP-DNA.

Monitors training metrics and adapts the architecture:
  - Grows Strands when existing ones are overloaded
  - Prunes Strands that are never used (dead)
  - Grows vocabulary when tokenizer fills up
  - Detects training plateaus and recommends scaling
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import torch

from .model import NpDnaCore

logger = logging.getLogger(__name__)


@dataclass
class PlasticityEvent:
    """Record of an adaptation event."""

    step: int
    event_type: str    # "grow_strand", "prune_strand", "grow_vocab", "plateau"
    details: str = ""


class PlasticityEngine:
    """Monitors and adapts the NP-DNA model during training.

    Call ``check()`` every N training steps to:
      1. Detect overloaded / dead Strands
      2. Grow vocabulary if tokenizer is near capacity
      3. Detect training loss plateaus
      4. Log recommendations

    Args:
        core: The NpDnaCore to monitor.
        check_interval: How often to check (in training steps).
    """

    def __init__(
        self,
        core: NpDnaCore,
        check_interval: int = 100,
        dead_threshold: float = 0.01,
        overload_threshold: float = 0.5,
        plateau_window: int = 50,
        plateau_threshold: float = 0.01,
    ):
        self.core = core
        self.check_interval = check_interval
        self.dead_threshold = dead_threshold
        self.overload_threshold = overload_threshold
        self.plateau_window = plateau_window
        self.plateau_threshold = plateau_threshold

        self.events: list[PlasticityEvent] = []
        self.loss_history: list[float] = []

    def record_loss(self, loss: float) -> None:
        """Record a training loss value."""
        self.loss_history.append(loss)

    def check(self, step: int) -> list[PlasticityEvent]:
        """Run all plasticity checks.  Returns list of events that occurred."""
        if step % self.check_interval != 0:
            return []

        events: list[PlasticityEvent] = []

        # 1. Check strand usage across all mesh layers
        events.extend(self._check_strand_usage(step))

        # 2. Check vocabulary pressure
        events.extend(self._check_vocab_pressure(step))

        # 3. Check for training plateau
        events.extend(self._check_plateau(step))

        self.events.extend(events)
        return events

    def _check_strand_usage(self, step: int) -> list[PlasticityEvent]:
        """Detect dead and overloaded Strands."""
        events = []

        for layer_i, mesh in enumerate(self.core.model.mesh_layers):
            stats = mesh.usage_stats
            N = mesh.config.num_strands

            dead = [s_id for s_id, ratio in stats.items() if ratio < self.dead_threshold]
            overloaded = [s_id for s_id, ratio in stats.items() if ratio > self.overload_threshold]

            if dead:
                msg = f"Layer {layer_i}: {len(dead)} dead strands {dead}"
                logger.warning("Plasticity: %s", msg)
                events.append(PlasticityEvent(step, "dead_strands", msg))

            if overloaded:
                msg = f"Layer {layer_i}: {len(overloaded)} overloaded strands {overloaded}"
                logger.warning("Plasticity: %s", msg)
                events.append(PlasticityEvent(step, "overloaded_strands", msg))

            # Reset counters for next check interval
            mesh.reset_usage()

        return events

    def _check_vocab_pressure(self, step: int) -> list[PlasticityEvent]:
        """Detect when tokenizer is running out of capacity."""
        events = []
        tok = self.core.tokenizer
        if tok.fill_ratio > 0.9:
            msg = f"Vocab at {tok.fill_ratio:.0%} capacity ({tok.size}/{tok.capacity})"
            logger.info("Plasticity: %s — will auto-grow on next encode", msg)
            events.append(PlasticityEvent(step, "vocab_pressure", msg))
        return events

    def _check_plateau(self, step: int) -> list[PlasticityEvent]:
        """Detect when training loss has stopped improving."""
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
                logger.warning("Plasticity: %s", msg)
                events.append(PlasticityEvent(step, "plateau", msg))

        return events

    def summary(self) -> str:
        """Human-readable summary of all plasticity events."""
        if not self.events:
            return "No plasticity events recorded."

        lines = [f"Plasticity: {len(self.events)} events"]
        for e in self.events[-20:]:  # Last 20
            lines.append(f"  step {e.step}: [{e.event_type}] {e.details}")
        return "\n".join(lines)
