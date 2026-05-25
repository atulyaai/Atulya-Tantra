"""NP-DNA configuration dataclasses.

Every config auto-scales. Nothing is hardcoded. Start at any size,
the Plasticity Engine grows it from there.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GenomeConfig:
    """DNA weight generator configuration."""

    latent_dim: int | None = None  # None = auto-computed from hidden_size
    rank: int = 32
    max_strands: int | None = None  # None = auto-computed from num_layers * mesh.num_strands
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
    int8_matmul: bool = False  # per-tensor symmetric int8 quantized matmul (memory-bandwidth opt)


@dataclass
class MeshConfig:
    """Sparse routing fabric configuration."""

    num_strands: int = 8
    top_k: int = 2
    balance_weight: float = 0.05
    strand: StrandConfig = field(default_factory=StrandConfig)


@dataclass
class LayerSpec:
    """One logical routed layer."""

    name: str = "main"
    num_strands: int = 8
    top_k: int = 2
    strand: StrandConfig = field(default_factory=StrandConfig)

    def make_mesh_config(self, hidden_size: int, state_size: int) -> MeshConfig:
        self.strand.hidden_size = hidden_size
        self.strand.state_size = state_size
        return MeshConfig(num_strands=self.num_strands, top_k=self.top_k, strand=self.strand)


@dataclass
class CortexConfig:
    """External memory cortex configuration."""

    dim: int = 256
    max_entries: int = 100_000
    top_k: int = 8


@dataclass
class CodecConfig:
    """Frozen tokenizer-like codec references for non-text modalities."""

    audio_codec: str | None = None
    image_codec: str | None = None
    video_codec: str | None = None


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
    mesh_specs: list[LayerSpec] = field(default_factory=list)
    cortex: CortexConfig = field(default_factory=CortexConfig)
    codecs: CodecConfig = field(default_factory=CodecConfig)

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
        # Only set genome defaults if not explicitly configured
        if self.genome.latent_dim is None:
            self.genome.latent_dim = min(512, self.hidden_size * 2)
        if self.genome.max_strands is None:
            self.genome.max_strands = self.total_strands

    @property
    def total_strands(self) -> int:
        if self.mesh_specs:
            return sum(spec.num_strands for spec in self.mesh_specs)
        return self.mesh.num_strands * self.num_layers


# ---------------------------------------------------------------------------
# Pre-built scaling configs â€” start at seed, auto-grow from there
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
    "atulya_v1_small": NpDnaConfig(
        initial_vocab=4096,
        hidden_size=64,
        state_size=32,
        tie_embeddings=True,
        genome=GenomeConfig(latent_dim=128, rank=16, max_strands=64, encoder_hidden=256),
        mesh_specs=[
            LayerSpec(name="main", num_strands=10, top_k=3),
            LayerSpec(name="sentiment", num_strands=4, top_k=1),
            LayerSpec(name="bias", num_strands=4, top_k=1),
            LayerSpec(name="security", num_strands=4, top_k=1),
            LayerSpec(name="cortex", num_strands=8, top_k=2),
        ],
        codecs=CodecConfig(
            audio_codec="frozen://encodec/tokenizer",
            image_codec="frozen://vqgan/tokenizer",
            video_codec="frozen://video-tokenizer",
        ),
        cortex=CortexConfig(dim=64, max_entries=100_000, top_k=8),
    ),
    "atulya": NpDnaConfig(
        initial_vocab=50000,
        hidden_size=768,
        state_size=512,
        tie_embeddings=True,
        genome=GenomeConfig(latent_dim=512, rank=64, max_strands=2048, encoder_hidden=1024),
        mesh_specs=[
            LayerSpec(name="main", num_strands=100, top_k=3),
            LayerSpec(name="sentiment", num_strands=16, top_k=1),
            LayerSpec(name="bias", num_strands=16, top_k=1),
            LayerSpec(name="security", num_strands=16, top_k=1),
            LayerSpec(name="cortex", num_strands=32, top_k=2),
        ],
        cortex=CortexConfig(dim=768, max_entries=1_000_000, top_k=16),
    ),
}

CONFIGS.update(
    {
        "atulya_seed": CONFIGS["seed"],
        "atulya_small": CONFIGS["atulya_v1_small"],
        "atulya_medium": CONFIGS["medium"],
        "atulya_large": CONFIGS["atulya"],
    }
)

PREFERRED_CONFIG_NAMES = ("atulya_seed", "atulya_small", "atulya_medium", "atulya_large")


def auto_config(target_params: int = 500_000) -> NpDnaConfig:
    """Choose the best config for a target parameter budget."""
    if target_params < 100_000:
        return CONFIGS["atulya_seed"]

    best_name = "atulya_seed"
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

