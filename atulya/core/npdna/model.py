"""NP-DNA Model — full NeuroPlastic DNA Network.

Architecture:
    Token IDs → Embedding → [Mesh₁ → … → Meshₙ] → Norm → LM Head

Auto-scales: vocab grows, strands grow, layers grow — all automatic.

Generation logic lives in generation.py (GenerationMixin).
Save/load logic lives in checkpoint.py (CheckpointMixin).
"""
from __future__ import annotations

import logging
from copy import deepcopy
from pathlib import Path

import torch
from torch import Tensor, nn

from .config import CONFIGS, NpDnaConfig
from .cortex import MemoryCortex
from .genome import Genome
from .mesh import NeuralMesh
from .tokenizer import AtulyaTokenizer
from .multimodal import VoiceEncoder, VisionEncoder
from .generation import GenerationMixin
from .checkpoint import CheckpointMixin

logger = logging.getLogger(__name__)


# ── Core architecture ─────────────────────────────────────────────────────────

class NpDnaModel(nn.Module):
    """Full NP-DNA language model (architecture only, no inference helpers)."""

    def __init__(self, config: NpDnaConfig) -> None:
        super().__init__()
        self.config = config
        H = config.hidden_size

        self.embedding = nn.Embedding(config.initial_vocab, H)
        self.genome = Genome(config.genome, config.mesh.strand)

        self.mesh_layers = nn.ModuleList([
            NeuralMesh(self.genome, deepcopy(config.mesh), layer_offset=i * config.mesh.num_strands)
            for i in range(config.num_layers)
        ])
        self.layer_norms = nn.ModuleList([nn.LayerNorm(H) for _ in range(config.num_layers)])
        self.final_norm = nn.LayerNorm(H)
        self.lm_head = nn.Linear(H, config.initial_vocab, bias=False)

        if config.tie_embeddings:
            self.lm_head.weight = self.embedding.weight

        self.cortex = MemoryCortex(config.cortex)
        self.voice_encoder = VoiceEncoder(H)
        self.vision_encoder = VisionEncoder(H)

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def vocab_size(self) -> int:
        return self.embedding.num_embeddings

    def parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def active_parameter_count(self) -> int:
        """Params active per token (sparse — only top_k strands)."""
        total = self.embedding.weight.numel() + self.final_norm.weight.numel() * 2
        per_strand = (
            self.config.hidden_size * self.config.state_size * 3
            + self.config.state_size * self.config.hidden_size
        )
        total += per_strand * self.config.mesh.top_k * self.config.num_layers
        total += self.genome.config.param_estimate
        return total

    # ── Growth / reshape ──────────────────────────────────────────────────────

    def grow_strands(self, count: int = 1) -> None:
        """Uniformly grow every mesh layer by `count` new strands."""
        if count <= 0:
            return
        old_n = self.mesh_layers[0].config.num_strands if self.mesh_layers else self.config.mesh.num_strands
        self.genome.add_strand_capacity(self.config.num_layers * count)
        for grow_i in range(count):
            for layer_i, mesh in enumerate(self.mesh_layers):
                strand_id = old_n * self.config.num_layers + grow_i * self.config.num_layers + layer_i
                mesh.add_strand(strand_id=strand_id)
        new_n = old_n + count
        self.config.mesh.num_strands = new_n
        self.config.genome.max_strands = max(
            int(self.genome.seeds.shape[0]),
            new_n * self.config.num_layers,
        )
        logger.info("NpDnaModel: strands/layer %d → %d", old_n, new_n)

    def resize_embeddings(self, new_vocab: int) -> None:
        if new_vocab <= self.vocab_size:
            return
        old_n = self.vocab_size
        H = self.config.hidden_size
        new_emb = nn.Embedding(new_vocab, H)
        new_head = nn.Linear(H, new_vocab, bias=False)
        with torch.no_grad():
            new_emb.weight[:old_n].copy_(self.embedding.weight)
            if not self.config.tie_embeddings:
                new_head.weight[:old_n].copy_(self.lm_head.weight)
        self.embedding = new_emb
        self.lm_head = new_head
        if self.config.tie_embeddings:
            self.lm_head.weight = self.embedding.weight
        logger.info("Embeddings resized: %d → %d", old_n, new_vocab)

    def strand_id_map(self) -> list[list[int]]:
        return [[int(s.strand_id) for s in mesh.strands] for mesh in self.mesh_layers]

    def restore_strand_id_map(self, strand_ids: list[list[int]]) -> None:
        for mesh, ids in zip(self.mesh_layers, strand_ids):
            if len(ids) == len(mesh.strands):
                for strand, sid in zip(mesh.strands, ids):
                    strand.strand_id = int(sid)

    # ── Forward ───────────────────────────────────────────────────────────────

    def forward(
        self,
        input_ids: Tensor | None = None,
        audio_inputs: Tensor | None = None,
        image_inputs: Tensor | None = None,
    ) -> tuple[Tensor, Tensor]:
        embeddings: list[Tensor] = []
        if input_ids is not None:
            embeddings.append(self.embedding(input_ids))
        if audio_inputs is not None:
            embeddings.append(self.voice_encoder(audio_inputs))
        if image_inputs is not None:
            embeddings.append(self.vision_encoder(image_inputs))
        if not embeddings:
            raise ValueError("Provide at least one of: input_ids, audio_inputs, image_inputs.")

        x = torch.cat(embeddings, dim=1) if len(embeddings) > 1 else embeddings[0]
        total_balance_loss = torch.tensor(0.0, device=x.device)

        for mesh, norm in zip(self.mesh_layers, self.layer_norms):
            residual = x
            if self.config.gradient_checkpointing and x.requires_grad:
                mesh_out, bal = torch.utils.checkpoint.checkpoint(mesh.forward, x, use_reentrant=False)
            else:
                mesh_out, bal = mesh(x)
            x = norm(residual + mesh_out)
            total_balance_loss = total_balance_loss + bal

        x = self.cortex.augment(x)
        x = self.final_norm(x)
        return self.lm_head(x), total_balance_loss


# ── High-level wrapper ────────────────────────────────────────────────────────

class NpDnaCore(GenerationMixin, CheckpointMixin):
    """High-level wrapper: model + tokenizer + cortex + auto-scaling.

    This is the main interface for training and inference.

    Usage:
        core = NpDnaCore.from_config("nano")
        ids  = core.encode("Hello world")
        text = core.generate("Hello world")
    """

    def __init__(
        self,
        model: NpDnaModel,
        tokenizer: AtulyaTokenizer,
        cortex: MemoryCortex | None = None,
        config: NpDnaConfig | None = None,
    ) -> None:
        self.model = model
        self.tokenizer = tokenizer
        if cortex is not None:
            self.model.cortex = cortex
        self.cortex = self.model.cortex
        self.config = config or CONFIGS["seed"]
        self.active_path: Path | None = None

    @classmethod
    def from_config(cls, name: str = "seed") -> "NpDnaCore":
        config = CONFIGS[name]
        tokenizer = AtulyaTokenizer(
            initial_capacity=config.initial_vocab,
            max_capacity=config.max_vocab,
        )
        model = NpDnaModel(config)
        cortex = MemoryCortex(config.cortex)
        logger.info(
            "NpDnaCore created [%s]: %s params total, %s active | vocab=%d | %d layers × %d strands (top-%d)",
            name,
            f"{model.parameter_count():,}",
            f"{model.active_parameter_count():,}",
            tokenizer.vocab_size,
            config.num_layers,
            config.mesh.num_strands,
            config.mesh.top_k,
        )
        return cls(model=model, tokenizer=tokenizer, cortex=cortex, config=config)

    # ── Encode / Decode ───────────────────────────────────────────────────────

    def encode(self, text: str, allow_growth: bool = True) -> list[int]:
        old_cap = self.tokenizer.capacity
        ids = self.tokenizer.encode(text, allow_growth=allow_growth)
        if self.tokenizer.capacity != old_cap:
            self.model.resize_embeddings(self.tokenizer.capacity)
        return ids

    def decode(self, ids) -> str:
        if isinstance(ids, Tensor):
            ids = ids.tolist()
        return self.tokenizer.decode(ids)
