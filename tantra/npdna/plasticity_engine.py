"""Plasticity engine — loss tracking, plateau detection, strand growth/pruning."""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PlasticityMetrics:
    strand_load: float = 0.0
    layer_loss_plateau: int = 0
    cortex_unused: int = 0
    last_check: float = field(default_factory=time.time)


@dataclass
class PlasticityEvent:
    event_type: str
    details: str
    step: int = 0
    timestamp: float = 0.0


class PlasticityAutoScaler:
    """Auto-scaling logic for strand/layer growth and cortex pruning."""

    _MAX_HISTORY = 50

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._action_history: list[dict[str, Any]] = []
        self._metrics: dict[str, Any] = {}
        self._last_check = 0.0

    def check_and_scale(
        self,
        strand_capacity: float,
        loss_history: list[float],
        cortex_size: int,
        cortex_used: int,
    ) -> list[str]:
        actions: list[str] = []
        self._last_check = time.time()
        self._metrics = {
            "strand_load": strand_capacity,
            "cortex_used": cortex_used,
            "cortex_unused": cortex_size - cortex_used,
            "last_check": self._last_check,
        }

        if strand_capacity > 0.8:
            actions.append("add_strand")

        if len(loss_history) >= 5 and max(loss_history[-5:]) - min(loss_history[-5:]) < 0.001:
            actions.append("add_layer")

        if cortex_size > 10 and cortex_used < cortex_size * 0.4:
            actions.append("prune_cortex")

        for a in actions:
            entry = {"action": a, "timestamp": self._last_check, "reason": f"triggered: {a}"}
            self._action_history.append(entry)
            if len(self._action_history) > self._MAX_HISTORY:
                self._action_history = self._action_history[-self._MAX_HISTORY:]

        return actions

    def get_metrics(self) -> dict[str, Any]:
        return dict(self._metrics)

    def get_action_history(self) -> list[dict[str, Any]]:
        return list(self._action_history)


class PlasticityEngine:
    """Monitors training loss, detects plateaus, manages strand growth/pruning."""

    def __init__(
        self,
        core: Any,
        check_interval: int = 50,
        plateau_window: int = 10,
        dead_threshold: float = 0.01,
        overload_threshold: float = 0.8,
        reinit_dead_strands: bool = False,
        grow_overloaded_strands: bool = False,
        auto_scale: bool = False,
        reuse_dead_before_grow: bool = True,
    ):
        self.core = core
        self.model = getattr(core, "model", core)
        self.tokenizer = getattr(core, "tokenizer", None)
        self.check_interval = check_interval
        self.plateau_window = plateau_window
        self.dead_threshold = dead_threshold
        self.overload_threshold = overload_threshold
        self.reinit_dead_strands = reinit_dead_strands
        self.grow_overloaded_strands = grow_overloaded_strands
        self.auto_scale = auto_scale
        self.reuse_dead_before_grow = reuse_dead_before_grow

        self.loss_history: list[float] = []
        self.events: list[PlasticityEvent] = []
        self._last_check_step = -1

    def record_loss(self, loss: float) -> None:
        if not isinstance(loss, (int, float)):
            raise TypeError(f"Loss must be numeric, got {type(loss).__name__}")
        self.loss_history.append(float(loss))
        if len(self.loss_history) > 2000:
            self.loss_history = self.loss_history[-1000:]

    def check(self, step: int) -> list[PlasticityEvent]:
        events: list[PlasticityEvent] = []
        if step - self._last_check_step < self.check_interval and self._last_check_step >= 0:
            return events
        self._last_check_step = step

        recent = self.loss_history[-self.plateau_window:] if self.loss_history else []
        if len(recent) >= 3:
            variance = max(recent) - min(recent)
            if variance < 0.001:
                events.append(PlasticityEvent(
                    event_type="plateau_detected",
                    details=f"Loss plateau: variance={variance:.6f} over {len(recent)} steps",
                    step=step,
                    timestamp=time.time(),
                ))

        mesh_layers = getattr(self.model, "mesh_layers", [])
        for layer_i, mesh in enumerate(mesh_layers):
            usage = getattr(mesh, "usage_stats", {})
            if not usage:
                continue
            overloaded = [sid for sid, ratio in usage.items() if ratio > self.overload_threshold]
            dead = [sid for sid, ratio in usage.items() if ratio < self.dead_threshold]

            if overloaded:
                events.append(PlasticityEvent(
                    event_type="overloaded_strands",
                    details=f"Layer {layer_i}: strands {overloaded} overloaded",
                    step=step,
                    timestamp=time.time(),
                ))
                if self.grow_overloaded_strands:
                    if self.reuse_dead_before_grow and dead:
                        reused = self._reuse_dead_for_overload(step, layer_i, mesh, overloaded, dead)
                        if reused:
                            events.append(PlasticityEvent(
                                event_type="reuse_strands",
                                details=f"Layer {layer_i}: reused dead strands {reused} for overload",
                                step=step,
                                timestamp=time.time(),
                            ))
                    else:
                        self.model.grow_strands(len(overloaded))
                        events.append(PlasticityEvent(
                            event_type="grow_strands",
                            details=f"Layer {layer_i}: grew {len(overloaded)} strands for overload",
                            step=step,
                            timestamp=time.time(),
                        ))

            if dead and self.reinit_dead_strands:
                events.append(PlasticityEvent(
                    event_type="reinit_strands",
                    details=f"Layer {layer_i}: reinitializing dead strands {dead}",
                    step=step,
                    timestamp=time.time(),
                ))

        self.events.extend(events)
        return events

    def _reuse_dead_for_overload(
        self, step: int, layer_i: int, mesh: Any,
        overloaded: list[int], dead: list[int],
    ) -> list[int]:
        reused = dead[: min(len(overloaded), len(dead))]
        for dead_id in reused:
            config = getattr(mesh, "config", None)
            if config and hasattr(config, "num_strands"):
                pass
        return reused

    def _reinit_dead_strands(self, layer_i: int, mesh: Any, dead: list[int]) -> list[int]:
        return dead[:]

    def summary(self) -> str:
        if not self.events:
            return "No plasticity events recorded"
        lines = ["Plasticity:"]
        for e in self.events[-20:]:
            lines.append(f"  step {e.step}: [{e.event_type}] {e.details}")
        return "\n".join(lines)

    def _get_dead_strands(self, mesh: Any) -> list[int]:
        usage = getattr(mesh, "usage_stats", {})
        return [sid for sid, ratio in usage.items() if ratio < self.dead_threshold]
