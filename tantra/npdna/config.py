"""NP-DNA configuration dataclasses.

Every config auto-scales. Nothing is hardcoded. Start at any size,
the Plasticity Engine grows it from there.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class GenomeConfig:
    """DNA weight generator configuration."""

    latent_dim: int = 256
    rank: int = 32
    max_strands: int = 64
    encoder_hidden: int = 512

    @property
    def param_estimate(self) -> int:
        """Estimate parameter count for the Genome itself."""
        encoder = self.latent_dim * self.encoder_hidden + self.encoder_hidden * self.latent_dim
        seeds = self.max_strands * self.latent_dim
        return encoder + seeds


@dataclass
class StrandConfig:
    """Causal gated state-space processing unit configuration."""

    hidden_size: int = 128
    state_size: int = 64


@dataclass
class MeshConfig:
    """Sparse routing fabric configuration."""

    num_strands: int = 8
    top_k: int = 2
    balance_weight: float = 0.05
    strand: StrandConfig = field(default_factory=StrandConfig)


@dataclass
class CortexConfig:
    """External memory cortex configuration."""

    dim: int = 256
    max_entries: int = 100_000
    top_k: int = 8


@dataclass
class NpDnaConfig:
    """Full NP-DNA model configuration. Auto-scales from any starting point."""

    # Tokenizer
    initial_vocab: int = 4096
    max_vocab: int = 256_000

    # Model geometry
    hidden_size: int = 128
    state_size: int = 64
    num_layers: int = 2

    # Components
    genome: GenomeConfig = field(default_factory=GenomeConfig)
    mesh: MeshConfig = field(default_factory=MeshConfig)
    cortex: CortexConfig = field(default_factory=CortexConfig)

    # Embedding
    tie_embeddings: bool = True

    # Optimization
    gradient_checkpointing: bool = False

    def __post_init__(self):
        """Sync sub-configs with top-level sizes."""
        self.mesh.strand.hidden_size = self.hidden_size
        self.mesh.strand.state_size = self.state_size
        self.cortex.dim = self.hidden_size
        # Only set genome defaults if not explicitly configured
        if self.genome.latent_dim == 256:
            self.genome.latent_dim = min(512, self.hidden_size * 2)
        if self.genome.max_strands == 128:
            self.genome.max_strands = self.mesh.num_strands * self.num_layers

    @property
    def total_strands(self) -> int:
        return self.mesh.num_strands * self.num_layers


# ---------------------------------------------------------------------------
# Pre-built scaling configs — start at seed, auto-grow from there
# ---------------------------------------------------------------------------

CONFIGS: dict[str, NpDnaConfig] = {
    "seed": NpDnaConfig(
        initial_vocab=4096,
        hidden_size=64,
        state_size=32,
        num_layers=2,
        mesh=MeshConfig(num_strands=4, top_k=3),
    ),
    "nano": NpDnaConfig(
        initial_vocab=4096,
        hidden_size=128,
        state_size=64,
        num_layers=2,
        mesh=MeshConfig(num_strands=6, top_k=3),
    ),
    "micro": NpDnaConfig(
        initial_vocab=16384,
        hidden_size=256,
        state_size=128,
        num_layers=3,
        mesh=MeshConfig(num_strands=12, top_k=3),
    ),
    "small": NpDnaConfig(
        initial_vocab=32000,
        hidden_size=256,
        state_size=128,
        num_layers=4,
        mesh=MeshConfig(num_strands=8, top_k=3),
    ),
    "medium": NpDnaConfig(
        initial_vocab=50000,
        hidden_size=512,
        state_size=256,
        num_layers=6,
        mesh=MeshConfig(num_strands=12, top_k=3),
    ),
}


def auto_config(target_params: int = 500_000) -> NpDnaConfig:
    """Choose the best config for a target parameter budget."""
    if target_params < 100_000:
        return CONFIGS["seed"]

    best_name = "seed"
    for name, cfg in CONFIGS.items():
        est = _estimate_params(cfg)
        if est <= target_params:
            best_name = name

    return CONFIGS[best_name]


def _estimate_params(cfg: NpDnaConfig) -> int:
    """Rough parameter estimate for a config."""
    embedding = cfg.initial_vocab * cfg.hidden_size
    genome = cfg.genome.param_estimate
    # Strand weights per strand: gate, state, recurrent, output
    strand_weights = (
        cfg.hidden_size * cfg.state_size * 3  # gate, state, recurrent
        + cfg.state_size * cfg.hidden_size     # output
    )
    mesh_router = cfg.hidden_size * cfg.mesh.num_strands
    per_layer = mesh_router + strand_weights * cfg.mesh.num_strands
    lm_head = 0 if cfg.tie_embeddings else cfg.hidden_size * cfg.initial_vocab
    norm = cfg.hidden_size * 2 * (cfg.num_layers + 1)
    # Cortex (rough estimate): router + slot embeddings
    cortex = cfg.hidden_size * 64 + cfg.hidden_size * 128 if hasattr(cfg, 'cortex') else 0
    total = embedding + genome + per_layer * cfg.num_layers + lm_head + norm + cortex
    return total
