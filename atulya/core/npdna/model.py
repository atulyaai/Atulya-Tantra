"""NP-DNA Model — full NeuroPlastic DNA Network.

Combines Genome + Mesh + Cortex into a complete language model:
  Embedding → [Mesh Layer 1] → [Mesh Layer 2] → ... → LM Head

Auto-scales: vocab grows, strands grow, layers grow — all automatic.
"""

from __future__ import annotations

import json
import logging
import re
import time
from copy import deepcopy
from pathlib import Path

import torch
from torch import Tensor, nn

from .config import CONFIGS, NpDnaConfig
from .cortex import MemoryCortex
from .genome import Genome
from .mesh import NeuralMesh
from .tokenizer import SPECIAL_TOKENS, AtulyaTokenizer

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
            mesh = NeuralMesh(self.genome, deepcopy(config.mesh), layer_offset=offset)
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

        # External Knowledge Memory Cortex
        self.cortex = MemoryCortex(config.cortex)

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

    def grow_strands(self, count: int = 1) -> None:
        """Grow every mesh layer by ``count`` strands.

        Uniform growth keeps checkpoint metadata simple while letting the router
        spread load when any layer is overloaded.
        """
        if count <= 0:
            return
        old_n = self.mesh_layers[0].config.num_strands if self.mesh_layers else self.config.mesh.num_strands
        self.genome.add_strand_capacity(self.config.num_layers * count)
        for grow_i in range(count):
            for layer_i, mesh in enumerate(self.mesh_layers):
                strand_id = old_n * self.config.num_layers + grow_i * self.config.num_layers + layer_i
                mesh.add_strand(strand_id=strand_id)
        self.config.mesh.num_strands = old_n + count
        self.config.genome.max_strands = self.config.mesh.num_strands * self.config.num_layers
        logger.info("NpDnaModel: grew strands per layer %d -> %d", old_n, self.config.mesh.num_strands)

    def strand_id_map(self) -> list[list[int]]:
        return [[int(strand.strand_id) for strand in mesh.strands] for mesh in self.mesh_layers]

    def restore_strand_id_map(self, strand_ids: list[list[int]]) -> None:
        for mesh, ids in zip(self.mesh_layers, strand_ids):
            if len(ids) != len(mesh.strands):
                continue
            for strand, strand_id in zip(mesh.strands, ids):
                strand.strand_id = int(strand_id)

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
            if self.config.gradient_checkpointing and x.requires_grad:
                mesh_out, balance_loss = torch.utils.checkpoint.checkpoint(mesh, x, use_reentrant=False)
            else:
                mesh_out, balance_loss = mesh(x)
            x = norm(residual + mesh_out)
            total_balance_loss = total_balance_loss + balance_loss

        # Augment with Memory Cortex knowledge
        x = self.cortex.augment(x)

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
        # Ensure model holds the correct cortex instance
        if cortex is not None:
            self.model.cortex = cortex
        self.cortex = self.model.cortex
        self.config = config or CONFIGS["seed"]
        self.active_path: Path | None = None

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
        temperature: float = 0.35,
        top_k: int = 12,
        repetition_penalty: float = 1.12,
        suppress_byte_tokens: bool = True,
        suppress_rare_unicode: bool = True,
        context_window: int = 128,
    ) -> str:
        """Generate text from a prompt."""
        if "Assistant:" not in prompt and "User:" not in prompt:
            try:
                from atulya.identity import Identity

                system = Identity().get_system_prompt()
            except Exception:
                system = "You are Atulya. Be warm, thoughtful, and direct."
            prompt = f"System: {system}\nUser: {prompt.strip()}\nAssistant:"
        prompt_ids = self.encode(prompt, allow_growth=False)
        self.last_prompt_len = len(prompt_ids)
        ids = list(prompt_ids)
        if not ids:
            ids = [self.tokenizer.token_to_id.get("<bos>", 2)]

        self.model.eval()
        eos_id = self.tokenizer.token_to_id.get("<eos>", 3)
        valid_vocab = min(self.tokenizer.size, self.config.initial_vocab)
        byte_ids = set(self.tokenizer.byte_to_id.values()) if suppress_byte_tokens else set()
        special_ids = set(SPECIAL_TOKENS.values())
        rare_unicode_ids: set[int] = set()
        if suppress_rare_unicode:
            for tok_id, tok in enumerate(self.tokenizer.id_to_token[:valid_vocab]):
                if len(tok) != 1:
                    continue
                cp = ord(tok)
                if cp > 126:
                    rare_unicode_ids.add(tok_id)

        with torch.no_grad():
            for _ in range(max_tokens):
                input_ids = torch.tensor([ids[-context_window:]], dtype=torch.long)
                logits, _ = self.model(input_ids)
                next_logits = logits[0, -1]  # (vocab,)
                next_logits = next_logits.clone()

                # The embedding table is sized to capacity, while the tokenizer may
                # have used only part of it. Never sample ids the tokenizer cannot
                # decode yet; those show up as empty/gibberish output.
                if valid_vocab < next_logits.numel():
                    next_logits[valid_vocab:] = float("-inf")
                for tok_id in special_ids:
                    if tok_id != eos_id and tok_id < next_logits.numel():
                        next_logits[tok_id] = float("-inf")
                for tok_id in byte_ids:
                    if tok_id < next_logits.numel():
                        next_logits[tok_id] = float("-inf")
                for tok_id in rare_unicode_ids:
                    if tok_id < next_logits.numel():
                        next_logits[tok_id] = float("-inf")

                if repetition_penalty > 1.0:
                    for seen_id in set(ids[-128:]):
                        if 0 <= seen_id < next_logits.numel():
                            next_logits[seen_id] /= repetition_penalty

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

        generated_text = self.decode(ids[len(prompt_ids):])
        
        # 1. Parse active memory tags: <memory_start>...<memory_end>
        matches = re.findall(r'<memory_start>(.*?)<memory_end>', generated_text, re.DOTALL)
        for match in matches:
            fact = match.strip()
            if not fact:
                continue
            # 2. Encode and average embeddings to create a query-key vector
            fact_ids = self.encode(fact, allow_growth=False)
            if fact_ids:
                with torch.no_grad():
                    fact_t = torch.tensor(fact_ids, dtype=torch.long, device=self.model.embedding.weight.device)
                    embs = self.model.embedding(fact_t)  # (seq_len, dim)
                    vector = embs.mean(dim=0).cpu()      # (dim,)
                # 3. Store fact directly into Cortex
                self.cortex.store(key=vector, value=vector, topic="Active Write-Back", source=fact)
        
        # 4. Auto-save cortex if path tracking is active
        if matches and self.active_path:
            self.cortex.save(self.active_path / "cortex")
            meta_file = self.active_path / "metadata.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    meta["cortex_entries"] = self.cortex.size
                    meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
                except Exception as e:
                    logger.error("Failed to update metadata during active write-back: %s", e)
                    
        self.last_generated_ids = ids
        return generated_text

    def get_routing_telemetry(self) -> list[dict]:
        """Constructs a unified trace of routing paths and cortex hits for the last generated sequence."""
        if not hasattr(self, "last_generated_ids") or not self.last_generated_ids:
            return []

        # Run a parallel forward pass under eval and no_grad to populate buffers
        self.model.eval()
        with torch.no_grad():
            input_ids = torch.tensor([self.last_generated_ids], dtype=torch.long, device=self.model.embedding.weight.device)
            # This triggers mesh forward passes and cortex retrievals in eval mode
            self.model(input_ids)

        telemetry = []
        seq_len = len(self.last_generated_ids)
        prompt_len = getattr(self, "last_prompt_len", 0)

        # Retrieve cortex telemetry buffers
        cortex_indices = getattr(self.cortex, "_last_top_indices", None)
        cortex_scores = getattr(self.cortex, "_last_top_scores", None)

        for t in range(seq_len):
            tok_id = self.last_generated_ids[t]
            try:
                tok_raw = self.tokenizer.id_to_token[tok_id]
            except Exception:
                tok_raw = f"<unk_{tok_id}>"
            
            tok_clean = self.decode([tok_id])
            is_prompt = t < prompt_len

            # Build mesh layer routing information
            layers_info = []
            for layer_idx, mesh in enumerate(self.model.mesh_layers):
                mesh_indices = getattr(mesh, "_last_top_indices", None)
                mesh_weights = getattr(mesh, "_last_top_weights", None)
                
                layer_routing = []
                if mesh_indices is not None and mesh_weights is not None:
                    # shapes are (1, seq_len, top_k)
                    # For token index t
                    t_indices = mesh_indices[0, t] # shape (top_k,)
                    t_weights = mesh_weights[0, t] # shape (top_k,)
                    
                    for k in range(len(t_indices)):
                        local_idx = int(t_indices[k].item())
                        weight = float(t_weights[k].item())
                        try:
                            strand = mesh.strands[local_idx]
                            global_id = int(strand.strand_id)
                        except Exception:
                            global_id = -1
                        layer_routing.append({
                            "local_index": local_idx,
                            "strand_id": global_id,
                            "weight": weight
                        })
                layers_info.append(layer_routing)

            # Build cortex retrieval information for token t
            cortex_hits = []
            if cortex_indices is not None and cortex_scores is not None:
                # cortex_indices shape is (seq_len, k)
                if t < len(cortex_indices):
                    t_cortex_indices = cortex_indices[t] # (k,)
                    t_cortex_scores = cortex_scores[t] # (k,)
                    for k in range(len(t_cortex_indices)):
                        entry_idx = int(t_cortex_indices[k].item())
                        score = float(t_cortex_scores[k].item())
                        if 0 <= entry_idx < len(self.cortex.entries):
                            entry = self.cortex.entries[entry_idx]
                            cortex_hits.append({
                                "entry_index": entry_idx,
                                "topic": entry.topic,
                                "source": entry.source,
                                "score": score
                            })

            telemetry.append({
                "token_id": int(tok_id),
                "token_raw": tok_raw,
                "token_clean": tok_clean,
                "is_prompt": is_prompt,
                "layers": layers_info,
                "cortex": cortex_hits
            })

        return telemetry

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def save(
        self,
        path: str | Path,
        losses: list[float] | None = None,
        metadata_extra: dict[str, object] | None = None,
    ) -> None:
        """Save model, tokenizer, cortex, and metadata."""
        path = Path(path)
        self.active_path = path
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
            "strand_ids": self.model.strand_id_map(),
            "vocab_capacity": self.tokenizer.capacity,
            "vocab_size": self.tokenizer.size,
            "parameter_count": self.model.parameter_count(),
            "active_parameter_count": self.model.active_parameter_count(),
            "cortex_entries": self.cortex.size,
            "losses": (losses or [])[-500:],
            "saved_at": time.time(),
        }
        if losses:
            meta["best_loss"] = min(losses)
            meta["final_loss"] = losses[-1]
            meta["loss_count"] = len(losses)
        if metadata_extra:
            meta.update(metadata_extra)
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

        # Infer actual strand count from state_dict keys — metadata may be stale
        # after plasticity growth or config overrides.
        state = torch.load(path / "model.pt", map_location="cpu", weights_only=True)
        inferred_strands = 0
        for key in state:
            m = re.match(r"mesh_layers\.\d+\.strands\.(\d+)\.", key)
            if m:
                strand_idx = int(m.group(1)) + 1
                if strand_idx > inferred_strands:
                    inferred_strands = strand_idx
        if inferred_strands == 0:
            inferred_strands = meta.get("num_strands", 4)

        mesh_cfg = MeshConfig(
            num_strands=inferred_strands,
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
        strand_ids = meta.get("strand_ids")
        if strand_ids:
            model.restore_strand_id_map(strand_ids)
        else:
            # Backward compatibility for checkpoints made by the first
            # strand-growth implementation. Initial strands used block offsets;
            # grown strands were appended as layer-interleaved ids.
            train_config_name = meta.get("train_config_name") or meta.get("config_name")
            base_cfg = CONFIGS.get(str(train_config_name))
            base_n = base_cfg.mesh.num_strands if base_cfg else meta["num_strands"]
            if meta["num_strands"] > base_n:
                inferred = []
                growth = meta["num_strands"] - base_n
                for layer_i in range(meta["num_layers"]):
                    ids = list(range(layer_i * base_n, layer_i * base_n + base_n))
                    ids.extend(base_n * meta["num_layers"] + g * meta["num_layers"] + layer_i for g in range(growth))
                model.restore_strand_id_map(inferred)
        try:
            model.load_state_dict(state)
        except RuntimeError as e:
            err_msg = str(e)
            if "size mismatch" in err_msg or "Missing key" in err_msg or "Unexpected key" in err_msg:
                raise RuntimeError(
                    f"Model checkpoint at {path} has mismatched architecture dimensions between metadata.json and model.pt. "
                    f"Metadata specifies hidden_size={config.hidden_size}, num_layers={config.num_layers}, num_strands={mesh_cfg.num_strands}. "
                    f"Please check if metadata.json was modified/reverted or is inconsistent with the saved weights. "
                    f"Original error: {err_msg}"
                ) from e
            raise

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
        core = cls(model=model, tokenizer=tokenizer, cortex=cortex, config=config)
        core.active_path = path
        return core
