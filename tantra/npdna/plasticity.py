"""Plasticity Engine — self-monitoring and auto-scaling for NP-DNA.

Monitors training metrics and adapts the architecture:
  - Grows Strands when existing ones are overloaded
  - Prunes Strands that are never used (dead)
  - Grows vocabulary when tokenizer fills up
  - Detects training plateaus and recommends scaling
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
    """Record of an adaptation event."""

    step: int
    event_type: str    # "grow_strand", "prune_strand", "grow_vocab", "plateau"
    details: str = ""


@dataclass
class PlasticityMetrics:
    strand_load: float = 0.0
    layer_loss_plateau: int = 0
    cortex_unused: int = 0
    last_check: float = field(default_factory=time.time)


class PlasticityAutoScaler:
    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._metrics = PlasticityMetrics()
        self._actions: list[dict] = []

    def check_and_scale(self, strand_capacity: float, loss_history: list[float], cortex_size: int, cortex_used: int) -> list[str]:
        actions = []
        self._metrics.strand_load = strand_capacity
        self._metrics.cortex_unused = cortex_size - cortex_used
        if strand_capacity > 0.9:
            actions.append("add_strand")
            self._actions.append({"action": "add_strand", "timestamp": time.time(), "reason": f"strand_load={strand_capacity}"})
        if len(loss_history) >= 10:
            recent = loss_history[-10:]
            if max(recent) - min(recent) < 0.001:
                actions.append("add_layer")
                self._metrics.layer_loss_plateau += 1
                self._actions.append({"action": "add_layer", "timestamp": time.time(), "reason": "loss_plateau"})
        if cortex_size > 0 and (cortex_size - cortex_used) / cortex_size > 0.5:
            actions.append("prune_cortex")
            self._actions.append({"action": "prune_cortex", "timestamp": time.time(), "reason": f"unused={cortex_size - cortex_used}"})
        self._metrics.last_check = time.time()
        return actions

    def get_metrics(self) -> dict:
        return vars(self._metrics)

    def get_action_history(self) -> list[dict]:
        return self._actions[-50:]


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
        overload_threshold: float = 0.18,
        plateau_window: int = 50,
        plateau_threshold: float = 0.01,
        reinit_dead_strands: bool = True,
        grow_overloaded_strands: bool = True,
        grow_cooldown_checks: int = 3,
        reuse_dead_before_grow: bool = True,
        auto_scale: bool = True,
    ):
        self.core = core
        self.check_interval = check_interval
        self.dead_threshold = dead_threshold
        self.overload_threshold = overload_threshold
        self.plateau_window = plateau_window
        self.plateau_threshold = plateau_threshold
        self.reinit_dead_strands = reinit_dead_strands
        self.grow_overloaded_strands = grow_overloaded_strands
        self.grow_cooldown_checks = grow_cooldown_checks
        self.reuse_dead_before_grow = reuse_dead_before_grow
        self.auto_scale = auto_scale
        self.autoscaler = PlasticityAutoScaler()

        self.events: list[PlasticityEvent] = []
        self.loss_history: list[float] = []
        self._last_dead_reinit: OrderedDict[tuple[int, int], None] = OrderedDict()
        self._available_dead_strands: dict[int, list[int]] = {}
        self._checks_since_growth = grow_cooldown_checks

    def record_loss(self, loss: float) -> None:
        """Record a training loss value. Rejects non-numeric and bool values."""
        if isinstance(loss, bool):
            raise TypeError("loss must be numeric, got bool")
        if not isinstance(loss, (int, float)):
            raise TypeError(f"loss must be numeric, got {type(loss).__name__}")
        self.loss_history.append(loss)

    def check(self, step: int) -> list[PlasticityEvent]:
        """Run all plasticity checks.  Returns list of events that occurred."""
        if step % self.check_interval != 0:
            return []

        events: list[PlasticityEvent] = []

        # 1. Check strand usage across all mesh layers
        events.extend(self._check_strand_usage(step))
        self._checks_since_growth += 1

        # 2. Check vocabulary pressure
        events.extend(self._check_vocab_pressure(step))

        # 3. Check for training plateau
        events.extend(self._check_plateau(step))

        self.events.extend(events)
        return events

    def _check_strand_usage(self, step: int) -> list[PlasticityEvent]:
        """Detect dead and overloaded Strands. Reuse dead strands before growing new ones."""
        events = []
        grew_this_check = False

        for layer_i, mesh in enumerate(self.core.model.mesh_layers):
            stats = mesh.usage_stats

            dead = [s_id for s_id, ratio in stats.items() if ratio < self.dead_threshold]
            overloaded = [s_id for s_id, ratio in stats.items() if ratio > self.overload_threshold]

            if dead:
                msg = f"Layer {layer_i}: {len(dead)} dead strands {dead}"
                logger.warning("Plasticity: %s", msg)
                events.append(PlasticityEvent(step, "dead_strands", msg))
                self._available_dead_strands[layer_i] = dead

            if overloaded:
                msg = f"Layer {layer_i}: {len(overloaded)} overloaded strands {overloaded}"
                logger.warning("Plasticity: %s", msg)
                events.append(PlasticityEvent(step, "overloaded_strands", msg))

            # Decide which dead strands to re-init vs reuse for overload
            if dead and self.reinit_dead_strands:
                if overloaded and self.reuse_dead_before_grow:
                    # Split dead pool: some used for overload reuse, rest get normal reinit
                    reuse_count = min(len(overloaded), len(dead))
                    dead_for_reuse = dead[:reuse_count]
                    dead_for_reinit = dead[reuse_count:]
                else:
                    dead_for_reuse = []
                    dead_for_reinit = dead

                if dead_for_reuse:
                    reused = self._reuse_dead_for_overload(step, layer_i, mesh, overloaded, dead_for_reuse)
                    if reused:
                        self._checks_since_growth = 0
                        grew_this_check = True

                if dead_for_reinit:
                    reinitialized = self._reinit_dead_strands(layer_i, mesh, dead_for_reinit)
                    if reinitialized:
                        reset_msg = f"Layer {layer_i}: reinitialized dead strands {reinitialized}"
                        logger.info("Plasticity: %s", reset_msg)
                        events.append(PlasticityEvent(step, "reinit_strands", reset_msg))

            # If overload remains after reuse, grow new strands
            if overloaded and self.grow_overloaded_strands and not grew_this_check:
                growth = self._grow_for_overload(step, msg)
                if growth:
                    events.append(growth)
                    self._checks_since_growth = 0
                    grew_this_check = True

            mesh.reset_usage()

        return events

    def _reuse_dead_for_overload(self, step: int, layer_i: int, mesh, overloaded: list[int], dead: list[int]) -> bool:
        """Reuse dead strands to handle overloaded capacity instead of growing new ones.

        Args:
            dead: Pre-filtered list of dead strand IDs to reuse for overload relief.
                  These will NOT also go through _reinit_dead_strands.

        Returns True if dead strands were successfully reused.
        """
        if not dead:
            return False
        
        reuse_count = min(len(overloaded), len(dead))
        if reuse_count == 0:
            return False
        
        genome = self.core.model.genome
        with torch.no_grad():
            for i in range(reuse_count):
                dead_id = dead[i]
                global_id = int(mesh.strands[dead_id].strand_id)
                
                if 0 <= global_id < genome.seeds.shape[0]:
                    genome.seeds[global_id].normal_(mean=0.0, std=0.02)
                if 0 <= dead_id < mesh.router.weight.shape[0]:
                    nn_init_std = 1.0 / (max(1, mesh.router.weight.shape[1]) ** 0.5)
                    mesh.router.weight[dead_id].normal_(mean=0.0, std=nn_init_std)
                
                key = (layer_i, dead_id)
                self._last_dead_reinit[key] = None
                
                msg = f"Layer {layer_i}: reused dead strand {dead_id} for overloaded capacity"
                logger.info("Plasticity: %s", msg)
                self.events.append(PlasticityEvent(step, "reuse_dead_strand", msg))
        
        self._available_dead_strands[layer_i] = dead[reuse_count:]
        return True

    def _grow_for_overload(self, step: int, reason: str) -> PlasticityEvent | None:
        model = self.core.model
        current = model.config.mesh.num_strands
        max_per_layer = 64
        if current >= max_per_layer:
            return None
        if self._checks_since_growth < self.grow_cooldown_checks:
            return None

        model.grow_strands(1)
        msg = f"grew strands per layer {current} -> {model.config.mesh.num_strands}; reason: {reason}"
        logger.info("Plasticity: %s", msg)
        return PlasticityEvent(step, "grow_strands", msg)

    def _reinit_dead_strands(self, layer_i: int, mesh, dead: list[int]) -> list[int]:
        """Reset dead strand seeds and router columns in place."""
        reinitialized: list[int] = []
        genome = self.core.model.genome
        with torch.no_grad():
            for s_id in dead:
                key = (layer_i, s_id)
                if key in self._last_dead_reinit:
                    continue
                global_id = int(mesh.strands[s_id].strand_id)
                if 0 <= global_id < genome.seeds.shape[0]:
                    genome.seeds[global_id].normal_(mean=0.0, std=0.02)
                if 0 <= s_id < mesh.router.weight.shape[0]:
                    nn_init_std = 1.0 / (max(1, mesh.router.weight.shape[1]) ** 0.5)
                    mesh.router.weight[s_id].normal_(mean=0.0, std=nn_init_std)
                reinitialized.append(s_id)
                self._last_dead_reinit[key] = None
        if len(self._last_dead_reinit) > 1000:
            to_remove = len(self._last_dead_reinit) - 1000
            for _ in range(to_remove):
                self._last_dead_reinit.popitem(last=False)
        return reinitialized

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
                if self.auto_scale:
                    action = self._handle_loss_plateau(step)
                    if action:
                        events.append(action)

        return events

    def _handle_loss_plateau(self, step: int) -> PlasticityEvent | None:
        if self._checks_since_growth < self.grow_cooldown_checks:
            return None
        current = self.core.model.config.mesh.num_strands
        self.core.model.grow_strands(2)
        self._checks_since_growth = 0
        msg = f"loss plateau triggered strand growth {current} -> {self.core.model.config.mesh.num_strands}"
        logger.info("Plasticity: %s", msg)
        return PlasticityEvent(step, "plateau_grow_strands", msg)

    def _prune_cortex(self, max_entries: int | None = None) -> int:
        cortex = getattr(self.core, "cortex", None)
        if cortex is None:
            return 0
        if hasattr(cortex, "prune_by_importance"):
            return cortex.prune_by_importance(max_entries)
        return 0

    def summary(self) -> str:
        """Human-readable summary of all plasticity events."""
        if not self.events:
            return "No plasticity events recorded."

        lines = [f"Plasticity: {len(self.events)} events"]
        for e in self.events[-20:]:  # Last 20
            lines.append(f"  step {e.step}: [{e.event_type}] {e.details}")
        return "\n".join(lines)
