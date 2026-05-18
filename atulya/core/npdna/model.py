"""NP-DNA Model — full NeuroPlastic DNA Network.

Combines Genome + Mesh + Cortex into a complete language model:
  Embedding → [Mesh Layer 1] → [Mesh Layer 2] → ... → LM Head

Auto-scales: vocab grows, strands grow, layers grow — all automatic.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import torch
from torch import Tensor, nn

from .config import CONFIGS, NpDnaConfig
from .cortex import MemoryCortex
from .genome import Genome
from .mesh import NeuralMesh
from .tokenizer import AtulyaTokenizer

logger = logging.getLogger(__name__)


class NpDnaModel(nn.Module):
    """Full NP-DNA language model.

    Architecture:
        Token IDs → Embedding → [Mesh₁ → Mesh₂ → ... → Meshₙ] → Norm → LM Head

    Each Mesh layer contains multiple Strands with DNA-generated weights.
    The Cortex optionally augments hidden states with external knowledge.
    """

    def __init__(self, config: NpDnaConfig):
        super().__init__()
        self.config = config
        H = config.hidden_size

        # Token embedding
        self.embedding = nn.Embedding(config.initial_vocab, H)

        # Shared Genome (DNA weight generator for ALL Strands across ALL layers)
        self.genome = Genome(config.genome, config.mesh.strand)

        # Mesh layers (each has its own set of Strands)
        self.mesh_layers = nn.ModuleList()
        for layer_i in range(config.num_layers):
            offset = layer_i * config.mesh.num_strands
            mesh = NeuralMesh(self.genome, config.mesh, layer_offset=offset)
            self.mesh_layers.append(mesh)

        # Layer norms (one per mesh layer + final)
        self.layer_norms = nn.ModuleList([
            nn.LayerNorm(H) for _ in range(config.num_layers)
        ])
        self.final_norm = nn.LayerNorm(H)

        # LM head (output projection to vocab)
        self.lm_head = nn.Linear(H, config.initial_vocab, bias=False)

        # Tie embeddings
        if config.tie_embeddings:
            self.lm_head.weight = self.embedding.weight

    @property
    def vocab_size(self) -> int:
        return self.embedding.num_embeddings

    def parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def active_parameter_count(self) -> int:
        """Params active per token (sparse — only top_k strands)."""
        total = self.embedding.weight.numel()
        total += self.final_norm.weight.numel() * 2
        # Only top_k strands active per layer
        per_strand = (
            self.config.hidden_size * self.config.state_size * 3
            + self.config.state_size * self.config.hidden_size
        )
        total += per_strand * self.config.mesh.top_k * self.config.num_layers
        # Genome is always fully active
        total += self.genome.config.param_estimate
        return total

    def resize_embeddings(self, new_vocab: int) -> None:
        """Grow embedding + LM head to fit larger vocabulary."""
        if new_vocab <= self.vocab_size:
            return
        old_emb = self.embedding
        old_head = self.lm_head
        H = self.config.hidden_size
        old_n = old_emb.num_embeddings

        self.embedding = nn.Embedding(new_vocab, H)
        self.lm_head = nn.Linear(H, new_vocab, bias=False)

        with torch.no_grad():
            self.embedding.weight[:old_n].copy_(old_emb.weight)
            if not self.config.tie_embeddings:
                self.lm_head.weight[:old_n].copy_(old_head.weight)

        if self.config.tie_embeddings:
            self.lm_head.weight = self.embedding.weight

        logger.info("Embeddings resized: %d → %d", old_n, new_vocab)

    def forward(self, input_ids: Tensor) -> tuple[Tensor, Tensor]:
        """Forward pass.

        Args:
            input_ids: Token IDs (batch, seq_len).

        Returns:
            (logits, balance_loss) — logits for next-token prediction,
            and aggregate load-balancing loss from all Mesh layers.
        """
        x = self.embedding(input_ids)  # (B, T, H)

        total_balance_loss = torch.tensor(0.0, device=x.device)

        for i, (mesh, norm) in enumerate(zip(self.mesh_layers, self.layer_norms)):
            residual = x
            mesh_out, balance_loss = mesh(x)
            x = norm(residual + mesh_out)
            total_balance_loss = total_balance_loss + balance_loss

        x = self.final_norm(x)
        logits = self.lm_head(x)  # (B, T, vocab)

        return logits, total_balance_loss


# ---------------------------------------------------------------------------
# NpDnaCore — wraps Model + Tokenizer + Cortex
# ---------------------------------------------------------------------------

class NpDnaCore:
    """High-level wrapper: model + tokenizer + cortex + auto-scaling.

    This is the main interface for training and inference.

    Usage:
        core = NpDnaCore.from_config("nano")
        ids = core.encode("Hello world")
        logits, loss = core.model(torch.tensor([ids]))
        text = core.decode(ids)
    """

    def __init__(
        self,
        model: NpDnaModel,
        tokenizer: AtulyaTokenizer,
        cortex: MemoryCortex | None = None,
        config: NpDnaConfig | None = None,
    ):
        self.model = model
        self.tokenizer = tokenizer
        self.cortex = cortex or MemoryCortex(config.cortex if config else CONFIGS["seed"].cortex)
        self.config = config or CONFIGS["seed"]

    @classmethod
    def from_config(cls, name: str = "seed") -> "NpDnaCore":
        """Create a fresh NpDnaCore from a named config."""
        config = CONFIGS[name]
        tokenizer = AtulyaTokenizer(
            initial_capacity=config.initial_vocab,
            max_capacity=config.max_vocab,
        )
        model = NpDnaModel(config)
        cortex = MemoryCortex(config.cortex)
        logger.info(
            "NpDnaCore created [%s]: %s params (total), %s active, vocab=%d, "
            "%d layers × %d strands (top-%d)",
            name,
            f"{model.parameter_count():,}",
            f"{model.active_parameter_count():,}",
            tokenizer.vocab_size,
            config.num_layers,
            config.mesh.num_strands,
            config.mesh.top_k,
        )
        return cls(model=model, tokenizer=tokenizer, cortex=cortex, config=config)

    # ------------------------------------------------------------------
    # Encode / Decode
    # ------------------------------------------------------------------

    def encode(self, text: str, allow_growth: bool = True) -> list[int]:
        old_cap = self.tokenizer.capacity
        ids = self.tokenizer.encode(text, allow_growth=allow_growth)
        # Auto-resize model embeddings if tokenizer grew
        if self.tokenizer.capacity != old_cap:
            self.model.resize_embeddings(self.tokenizer.capacity)
        return ids

    def decode(self, ids: list[int] | Tensor) -> str:
        if isinstance(ids, Tensor):
            ids = ids.tolist()
        return self.tokenizer.decode(ids)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        max_tokens: int = 50,
        temperature: float = 0.8,
        top_k: int = 40,
    ) -> str:
        """Generate text from a prompt."""
        ids = self.encode(prompt, allow_growth=False)
        if not ids:
            ids = [self.tokenizer.token_to_id.get("<bos>", 2)]

        self.model.eval()
        eos_id = self.tokenizer.token_to_id.get("<eos>", 3)

        with torch.no_grad():
            for _ in range(max_tokens):
                input_ids = torch.tensor([ids[-512:]], dtype=torch.long)
                logits, _ = self.model(input_ids)
                next_logits = logits[0, -1]  # (vocab,)

                # Temperature
                if temperature > 0:
                    next_logits = next_logits / temperature

                # Top-k filtering
                if top_k > 0:
                    topk_vals, topk_idx = torch.topk(next_logits, min(top_k, next_logits.size(0)))
                    mask = torch.full_like(next_logits, float("-inf"))
                    mask.scatter_(0, topk_idx, topk_vals)
                    next_logits = mask

                probs = torch.softmax(next_logits, dim=-1)
                next_id = torch.multinomial(probs, 1).item()
                ids.append(next_id)

                if next_id == eos_id:
                    break

        return self.decode(ids[len(self.encode(prompt, allow_growth=False)):])

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def save(self, path: str | Path, losses: list[float] | None = None) -> None:
        """Save model, tokenizer, cortex, and metadata."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Model weights
        torch.save(self.model.state_dict(), path / "model.pt")

        # Tokenizer
        self.tokenizer.save(path / "tokenizer.json")

        # Cortex
        self.cortex.save(path / "cortex")

        # Metadata
        meta = {
            "config_name": next(
                (n for n, c in CONFIGS.items() if c is self.config), "custom"
            ),
            "hidden_size": self.config.hidden_size,
            "state_size": self.config.state_size,
            "num_layers": self.config.num_layers,
            "num_strands": self.config.mesh.num_strands,
            "top_k": self.config.mesh.top_k,
            "vocab_capacity": self.tokenizer.capacity,
            "vocab_size": self.tokenizer.size,
            "parameter_count": self.model.parameter_count(),
            "active_parameter_count": self.model.active_parameter_count(),
            "cortex_entries": self.cortex.size,
            "losses": (losses or [])[-500:],
            "saved_at": time.time(),
        }
        (path / "metadata.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )
        logger.info("NpDnaCore saved to %s (%s params)", path, f"{self.model.parameter_count():,}")

    @classmethod
    def load(cls, path: str | Path) -> "NpDnaCore":
        """Load a saved NpDnaCore."""
        path = Path(path)
        meta = json.loads((path / "metadata.json").read_text(encoding="utf-8"))

        # Reconstruct config
        from .config import CortexConfig, GenomeConfig, MeshConfig, StrandConfig

        strand_cfg = StrandConfig(
            hidden_size=meta["hidden_size"],
            state_size=meta["state_size"],
        )
        mesh_cfg = MeshConfig(
            num_strands=meta["num_strands"],
            top_k=meta["top_k"],
            strand=strand_cfg,
        )
        config = NpDnaConfig(
            initial_vocab=meta["vocab_capacity"],
            hidden_size=meta["hidden_size"],
            state_size=meta["state_size"],
            num_layers=meta["num_layers"],
            mesh=mesh_cfg,
        )

        # Tokenizer
        tokenizer = AtulyaTokenizer.load(path / "tokenizer.json")

        # Model
        model = NpDnaModel(config)
        state = torch.load(path / "model.pt", map_location="cpu", weights_only=True)
        model.load_state_dict(state)

        # Cortex
        cortex_path = path / "cortex"
        if cortex_path.exists():
            cortex = MemoryCortex.load(cortex_path, config.cortex)
        else:
            cortex = MemoryCortex(config.cortex)

        logger.info(
            "NpDnaCore loaded from %s (%s params, %d cortex entries)",
            path, f"{model.parameter_count():,}", cortex.size,
        )
        return cls(model=model, tokenizer=tokenizer, cortex=cortex, config=config)
