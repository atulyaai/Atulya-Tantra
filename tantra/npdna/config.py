"""NP-DNA configuration dataclasses.

Every config auto-scales. Category → Layer → Strand architecture:
each category is one layer in the stack with N strands that auto-specialize.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GenomeConfig:
    """DNA weight generator configuration."""

    latent_dim: int | None = None  # None = auto-computed from hidden_size
    rank: int = 32
    max_strands: int | None = None  # None = auto-computed from total_strands
    encoder_hidden: int = 512

    @property
    def param_estimate(self) -> int:
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
class LayerSpec:
    """One layer = one category = N strands.

    Each layer is a NeuralMesh (or CategoryMesh when categories is set)
    with N strands. The internal router picks top-k strands per token.

    Args:
        name: Category name (e.g. "conversation", "code", "math")
        num_strands: Strands dedicated to this category/layer
        top_k: Active strands per token
        categories: When set, uses CategoryMesh (multi-category layer)
        dense: If True, standard FFN instead of strands
    """
    name: str = "main"
    num_strands: int = 8
    top_k: int = 2
    categories: list[tuple[str, int]] | None = None  # [(name, count), ...]
    dense: bool = False
    strand: StrandConfig = field(default_factory=StrandConfig)

    @property
    def total_strands(self) -> int:
        if self.categories:
            return sum(c[1] for c in self.categories)
        return self.num_strands

    def make_mesh_config(self, hidden_size: int, state_size: int) -> MeshConfig:
        self.strand.hidden_size = hidden_size
        self.strand.state_size = state_size
        return MeshConfig(num_strands=self.total_strands, top_k=self.top_k, strand=self.strand)

    def is_dense(self) -> bool:
        return self.dense

    def is_category(self) -> bool:
        return self.categories is not None


@dataclass
class CortexConfig:
    """External memory cortex configuration."""
    dim: int = 256
    max_entries: int = 100_000
    top_k: int = 8


@dataclass
class CodecConfig:
    """Frozen multimodal codec references.

    These are URIs to external tokenizer-like codecs. NP-DNA stores the
    reference, but codec weights remain outside the model.
    """
    enabled: bool = False
    audio_codec: str | None = None
    image_codec: str | None = None
    video_codec: str | None = None

@dataclass
class NpDnaConfig:
    """Full NP-DNA model configuration. Category → Layer → Strand architecture.

    Each category is one layer. Layers are stacked sequentially.
    Strands within a layer auto-specialize via routing.
    """

    # Tokenizer
    initial_vocab: int = 4096
    max_vocab: int = 256_000

    # Model geometry
    hidden_size: int = 128
    state_size: int = 64
    num_layers: int = 2  # auto-computed from mesh_specs if set

    # Default strands per category layer (used when LayerSpec.num_strands not set)
    strands_per_layer: int = 10

    # Components
    genome: GenomeConfig = field(default_factory=GenomeConfig)
    mesh: MeshConfig = field(default_factory=MeshConfig)
    mesh_specs: list[LayerSpec] = field(default_factory=list)
    cortex: CortexConfig = field(default_factory=CortexConfig)

    # Dense mode (no strands, standard FFN)
    dense_model: bool = False
    dense_ffn_mult: float = 3.5

    # Embedding
    tie_embeddings: bool = True

    # Optimization
    gradient_checkpointing: bool = False

    def __post_init__(self):
        """Sync sub-configs with top-level sizes."""
        if self.mesh_specs:
            self.num_layers = len(self.mesh_specs)
            for spec in self.mesh_specs:
                spec.strand.hidden_size = self.hidden_size
                spec.strand.state_size = self.state_size
        self.mesh.strand.hidden_size = self.hidden_size
        self.mesh.strand.state_size = self.state_size
        self.cortex.dim = self.hidden_size
        if self.genome.latent_dim is None:
            self.genome.latent_dim = min(512, self.hidden_size * 2)
        if self.genome.max_strands is None:
            self.genome.max_strands = self.total_strands

    @property
    def total_strands(self) -> int:
        if self.dense_model:
            return 0
        if self.mesh_specs:
            return sum(spec.total_strands for spec in self.mesh_specs)
        return self.mesh.num_strands * self.num_layers


# ---------------------------------------------------------------------------
# Category-based configs — each category = one layer with N strands
# Ordered by priority: conversation → code → math → science → writing
# Start with 5, expand to 10 as needed
# ---------------------------------------------------------------------------

CONFIGS: dict[str, NpDnaConfig] = {
    "seed": NpDnaConfig(
        initial_vocab=4096,
        hidden_size=64,
        state_size=32,
        strands_per_layer=8,
        mesh_specs=[
            LayerSpec(name="conversation", num_strands=8, top_k=3),
            LayerSpec(name="code", num_strands=8, top_k=3),
            LayerSpec(name="math", num_strands=8, top_k=3),
            LayerSpec(name="science", num_strands=6, top_k=2),
            LayerSpec(name="writing", num_strands=6, top_k=2),
        ],
        genome=GenomeConfig(latent_dim=128, rank=16, max_strands=64, encoder_hidden=256),
        cortex=CortexConfig(dim=64, max_entries=100_000, top_k=8),
    ),
    "nano": NpDnaConfig(
        initial_vocab=4096,
        hidden_size=128,
        state_size=64,
        strands_per_layer=10,
        mesh_specs=[
            LayerSpec(name="conversation", num_strands=10, top_k=3),
            LayerSpec(name="code", num_strands=10, top_k=3),
            LayerSpec(name="math", num_strands=10, top_k=3),
            LayerSpec(name="science", num_strands=8, top_k=2),
            LayerSpec(name="writing", num_strands=8, top_k=2),
        ],
        genome=GenomeConfig(latent_dim=256, rank=32, max_strands=128, encoder_hidden=512),
        cortex=CortexConfig(dim=128, max_entries=100_000, top_k=8),
    ),
    "micro": NpDnaConfig(
        initial_vocab=16384,
        hidden_size=256,
        state_size=128,
        strands_per_layer=12,
        mesh_specs=[
            LayerSpec(name="conversation", num_strands=12, top_k=3),
            LayerSpec(name="code", num_strands=12, top_k=3),
            LayerSpec(name="math", num_strands=12, top_k=3),
            LayerSpec(name="science", num_strands=10, top_k=2),
            LayerSpec(name="writing", num_strands=10, top_k=2),
        ],
        genome=GenomeConfig(latent_dim=512, rank=32, max_strands=256, encoder_hidden=512),
        cortex=CortexConfig(dim=256, max_entries=500_000, top_k=16),
    ),
    "small": NpDnaConfig(
        initial_vocab=32000,
        hidden_size=256,
        state_size=128,
        strands_per_layer=14,
        mesh_specs=[
            LayerSpec(name="conversation", num_strands=14, top_k=4),
            LayerSpec(name="code", num_strands=14, top_k=4),
            LayerSpec(name="math", num_strands=14, top_k=4),
            LayerSpec(name="science", num_strands=10, top_k=3),
            LayerSpec(name="writing", num_strands=10, top_k=3),
        ],
        genome=GenomeConfig(latent_dim=512, rank=64, max_strands=256, encoder_hidden=1024),
        cortex=CortexConfig(dim=256, max_entries=500_000, top_k=16),
    ),
    "medium": NpDnaConfig(
        initial_vocab=50000,
        hidden_size=512,
        state_size=256,
        strands_per_layer=20,
        mesh_specs=[
            LayerSpec(name="conversation", num_strands=20, top_k=4),
            LayerSpec(name="code", num_strands=20, top_k=4),
            LayerSpec(name="math", num_strands=20, top_k=4),
            LayerSpec(name="science", num_strands=14, top_k=3),
            LayerSpec(name="writing", num_strands=14, top_k=3),
        ],
        genome=GenomeConfig(latent_dim=512, rank=64, max_strands=512, encoder_hidden=1024),
        cortex=CortexConfig(dim=512, max_entries=1_000_000, top_k=16),
    ),
    "large": NpDnaConfig(
        initial_vocab=50000,
        hidden_size=768,
        state_size=512,
        strands_per_layer=24,
        mesh_specs=[
            LayerSpec(name="conversation", num_strands=24, top_k=4),
            LayerSpec(name="code", num_strands=24, top_k=4),
            LayerSpec(name="math", num_strands=24, top_k=4),
            LayerSpec(name="science", num_strands=16, top_k=3),
            LayerSpec(name="writing", num_strands=16, top_k=3),
        ],
        genome=GenomeConfig(latent_dim=768, rank=64, max_strands=1024, encoder_hidden=1536),
        cortex=CortexConfig(dim=768, max_entries=2_000_000, top_k=24),
    ),
}

PREFERRED_CONFIG_NAMES = (
    "seed", "nano", "micro", "small", "medium", "large",
)


def auto_config(target_params: int = 500_000) -> NpDnaConfig:
    """Choose the best config for a target parameter budget."""
    best_name = PREFERRED_CONFIG_NAMES[0]
    for name in PREFERRED_CONFIG_NAMES:
        cfg = CONFIGS[name]
        est = _estimate_params(cfg)
        if est <= target_params:
            best_name = name
    return CONFIGS[best_name]


def _estimate_params(cfg: NpDnaConfig) -> int:
    """Rough parameter estimate for a config."""
    embedding = cfg.initial_vocab * cfg.hidden_size
    genome = cfg.genome.param_estimate
    if cfg.mesh_specs:
        router = sum(cfg.hidden_size * spec.num_strands for spec in cfg.mesh_specs)
        norms = cfg.hidden_size * 2 * (len(cfg.mesh_specs) + 1)
    else:
        router = cfg.hidden_size * cfg.mesh.num_strands * cfg.num_layers
        norms = cfg.hidden_size * 2 * (cfg.num_layers + 1)
    lm_head = 0 if cfg.tie_embeddings else cfg.hidden_size * cfg.initial_vocab
    return embedding + genome + router + lm_head + norms
