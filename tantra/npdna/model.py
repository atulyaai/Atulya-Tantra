"""NP-DNA Model â€” full NeuroPlastic DNA Network.

Architecture:
    Token IDs â†’ Embedding â†’ [Meshâ‚ â†’ â€¦ â†’ Meshâ‚™] â†’ Norm â†’ LM Head

Auto-scales: vocab grows, strands grow, layers grow â€” all automatic.

Generation logic lives in generation.py (GenerationMixin).
Save/load logic lives in checkpoint.py (CheckpointMixin).
"""
from __future__ import annotations

import logging
from copy import deepcopy
from pathlib import Path

import torch
from torch import Tensor, nn

from .config import CONFIGS, LayerSpec, NpDnaConfig
from .cortex import MemoryCortex
from .genome import Genome
from .mesh import NeuralMesh
from .tokenizer import AtulyaTokenizer
from .generation import GenerationMixin
from .checkpoint import CheckpointMixin

logger = logging.getLogger(__name__)


# â”€â”€ Core architecture â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class NpDnaModel(nn.Module):
    """Full NP-DNA language model (architecture only, no inference helpers)."""

    def __init__(self, config: NpDnaConfig) -> None:
        super().__init__()
        self.config = config
        H = config.hidden_size

        self.embedding = nn.Embedding(config.initial_vocab, H)
        self.genome = Genome(config.genome, config.mesh.strand)

        self.layer_specs: list[LayerSpec] = []
        self.mesh_layers = nn.ModuleList()
        self.layer_norms = nn.ModuleList()

        if config.mesh_specs:
            self.layer_specs = config.mesh_specs
            offset = 0
            for spec in config.mesh_specs:
                mesh_cfg = spec.make_mesh_config(H, config.state_size)
                self.mesh_layers.append(NeuralMesh(self.genome, mesh_cfg, layer_offset=offset))
                self.layer_norms.append(nn.LayerNorm(H))
                offset += spec.num_strands
        else:
            self.layer_specs = [
                LayerSpec(name="layer", num_strands=config.mesh.num_strands, top_k=config.mesh.top_k)
                for _ in range(config.num_layers)
            ]
            for i in range(config.num_layers):
                self.mesh_layers.append(
                    NeuralMesh(self.genome, deepcopy(config.mesh), layer_offset=i * config.mesh.num_strands)
                )
                self.layer_norms.append(nn.LayerNorm(H))
        self.final_norm = nn.LayerNorm(H)
        self.lm_head = nn.Linear(H, config.initial_vocab, bias=False)

        if config.tie_embeddings:
            self.lm_head.weight = self.embedding.weight

        self.cortex = MemoryCortex(config.cortex)

    # â”€â”€ Properties â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @property
    def vocab_size(self) -> int:
        return self.embedding.num_embeddings

    def parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def active_parameter_count(self) -> int:
        """Params active per token (sparse â€” only top_k strands)."""
        total = self.embedding.weight.numel() + self.final_norm.weight.numel() * 2
        H = self.config.hidden_size
        S = self.config.state_size
        # Per-strand: gate (HÃ—S + S) + state (HÃ—S + S) + recurrent (SÃ—S + S) + output (SÃ—H + H)
        per_strand_weights = H * S + H * S + S * S + S * H  # = 3*H*S + S*S
        per_strand_biases = S + S + S + H  # = 3*S + H
        per_strand = per_strand_weights + per_strand_biases
        total += sum(
            per_strand * min(spec.top_k, spec.num_strands)
            for spec in self.layer_specs
        )
        total += self.genome.config.param_estimate
        return total

    # â”€â”€ Growth / reshape â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def grow_strands(self, count: int = 1) -> None:
        """Uniformly grow each mesh layer without collapsing non-uniform specs."""
        if count <= 0:
            return
        old_total = sum(spec.num_strands for spec in self.layer_specs)
        self.genome.add_strand_capacity(self.config.num_layers * count)
        for grow_i in range(count):
            for layer_i, mesh in enumerate(self.mesh_layers):
                strand_id = old_total + grow_i * self.config.num_layers + layer_i
                mesh.add_strand(strand_id=strand_id)
        for spec in self.layer_specs:
            spec.num_strands += count
        new_total = sum(spec.num_strands for spec in self.layer_specs)
        if self.layer_specs:
            self.config.mesh.num_strands = self.layer_specs[0].num_strands
        self.config.genome.max_strands = max(
            int(self.genome.seeds.shape[0]),
            new_total,
        )
        logger.info("NpDnaModel: strands/layer +%d (total %d)", count, new_total)

    def add_layer(
        self,
        name: str = "main",
        num_strands: int | None = None,
        top_k: int | None = None,
    ) -> None:
        """Append a new logical layer and allocate its strand seeds."""
        matching = [spec for spec in self.layer_specs if spec.name == name]
        if num_strands is None:
            num_strands = matching[-1].num_strands if matching else self.config.mesh.num_strands
        if top_k is None:
            top_k = matching[-1].top_k if matching else self.config.mesh.top_k

        old_total = int(self.genome.seeds.shape[0])
        self.genome.add_strand_capacity(num_strands)
        spec = LayerSpec(name=name, num_strands=num_strands, top_k=top_k)
        mesh_cfg = spec.make_mesh_config(self.config.hidden_size, self.config.state_size)
        self.mesh_layers.append(NeuralMesh(self.genome, mesh_cfg, layer_offset=old_total))
        self.layer_norms.append(nn.LayerNorm(self.config.hidden_size))
        self.layer_specs.append(spec)
        self.config.mesh_specs = self.layer_specs
        self.config.num_layers = len(self.layer_specs)
        self.config.genome.max_strands = int(self.genome.seeds.shape[0])
        logger.info("NpDnaModel: added %s layer with %d strands (top-%d)", name, num_strands, top_k)

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
        logger.info("Embeddings resized: %d â†’ %d", old_n, new_vocab)

    def strand_id_map(self) -> list[list[int]]:
        return [[int(s.strand_id) for s in mesh.strands] for mesh in self.mesh_layers]

    def restore_strand_id_map(self, strand_ids: list[list[int]]) -> None:
        for mesh, ids in zip(self.mesh_layers, strand_ids):
            if len(ids) == len(mesh.strands):
                for strand, sid in zip(mesh.strands, ids):
                    strand.strand_id = int(sid)

    # â”€â”€ Forward â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def forward(
        self,
        input_ids: Tensor,
    ) -> tuple[Tensor, Tensor]:
        x = self.embedding(input_ids)
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


# â”€â”€ High-level wrapper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class NpDnaCore(GenerationMixin, CheckpointMixin):
    """High-level wrapper: model + tokenizer + cortex + auto-scaling.

    This is the main interface for training and inference.

    Usage:
        core = NpDnaCore.from_config("atulya_small")
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
        self.config = config or CONFIGS["atulya_seed"]
        self.active_path: Path | None = None

    @classmethod
    def from_config(cls, name: str = "atulya_seed") -> "NpDnaCore":
        config = deepcopy(CONFIGS[name])
        tokenizer = AtulyaTokenizer(
            initial_capacity=config.initial_vocab,
            max_capacity=config.max_vocab,
        )
        model = NpDnaModel(config)
        cortex = MemoryCortex(config.cortex)
        logger.info(
            "NpDnaCore created [%s]: %s params total, %s active | vocab=%d | %d layers | %d strands total",
            name,
            f"{model.parameter_count():,}",
            f"{model.active_parameter_count():,}",
            tokenizer.vocab_size,
            config.num_layers,
            config.total_strands,
        )
        return cls(model=model, tokenizer=tokenizer, cortex=cortex, config=config)

    # â”€â”€ Encode / Decode â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

