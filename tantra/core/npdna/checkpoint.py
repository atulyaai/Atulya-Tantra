"""Checkpoint mixin for NpDnaCore.

Extracted from model.py to keep that file focused on architecture.
Handles: save, load, metadata construction.
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

import torch

logger = logging.getLogger(__name__)


class CheckpointMixin:
    """
    Provides save / load on any class that has:
      - self.model        (NpDnaModel)
      - self.tokenizer    (AtulyaTokenizer)
      - self.cortex       (MemoryCortex)
      - self.config       (NpDnaConfig)
      - self.active_path  (Path | None)
    """

    def save(
        self,
        path: str | Path,
        losses: list[float] | None = None,
        metadata_extra: dict | None = None,
    ) -> None:
        from .config import CONFIGS

        path = Path(path)
        self.active_path = path
        path.mkdir(parents=True, exist_ok=True)

        torch.save(self.model.state_dict(), path / "model.pt")
        self.tokenizer.save(path / "tokenizer.json")
        self.cortex.save(path / "cortex")

        meta: dict = {
            "config_name": self._match_config_name(),
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
            "cortex_dim": self.config.cortex.dim,
            "cortex_max_entries": self.config.cortex.max_entries,
            "cortex_top_k": self.config.cortex.top_k,
            "genome_latent_dim": self.config.genome.latent_dim,
            "genome_rank": self.config.genome.rank,
            "genome_encoder_hidden": self.config.genome.encoder_hidden,
            "genome_max_strands": self.config.genome.max_strands,
            "losses": (losses or [])[-500:],
            "saved_at": time.time(),
        }
        if losses:
            meta["best_loss"] = min(losses)
            meta["final_loss"] = losses[-1]
            meta["loss_count"] = len(losses)
        if metadata_extra:
            meta.update(metadata_extra)

        (path / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        logger.info("NpDnaCore saved → %s (%s params)", path, f"{self.model.parameter_count():,}")

    @classmethod
    def load(cls, path: str | Path) -> "CheckpointMixin":
        from .config import CONFIGS, CortexConfig, GenomeConfig, MeshConfig, NpDnaConfig, StrandConfig
        from .cortex import MemoryCortex
        from .tokenizer import AtulyaTokenizer

        path = Path(path)
        meta = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
        state = torch.load(path / "model.pt", map_location="cpu", weights_only=True)

        # Infer actual strand count from weights (beats stale metadata)
        inferred_strands = max(
            (int(re.match(r"mesh_layers\.\d+\.strands\.(\d+)\.", k).group(1)) + 1
             for k in state if re.match(r"mesh_layers\.\d+\.strands\.(\d+)\.", k)),
            default=meta.get("num_strands", 4),
        )

        strand_cfg = StrandConfig(
            hidden_size=meta["hidden_size"],
            state_size=meta["state_size"],
        )
        mesh_cfg = MeshConfig(
            num_strands=inferred_strands,
            top_k=meta["top_k"],
            strand=strand_cfg,
        )
        genome_cfg = GenomeConfig(
            latent_dim=meta.get("genome_latent_dim", 256),
            rank=meta.get("genome_rank", 32),
            encoder_hidden=meta.get("genome_encoder_hidden", 512),
            max_strands=meta.get("genome_max_strands", inferred_strands * meta["num_layers"]),
        )
        cortex_cfg = CortexConfig(
            dim=meta.get("cortex_dim", meta["hidden_size"]),
            max_entries=meta.get("cortex_max_entries", 100_000),
            top_k=meta.get("cortex_top_k", 8),
        )
        config = NpDnaConfig(
            initial_vocab=meta["vocab_capacity"],
            hidden_size=meta["hidden_size"],
            state_size=meta["state_size"],
            num_layers=meta["num_layers"],
            mesh=mesh_cfg,
            genome=genome_cfg,
            cortex=cortex_cfg,
        )
        config.genome.max_strands = meta.get("genome_max_strands", inferred_strands * meta["num_layers"])

        # Avoid circular import — import NpDnaModel here
        from .model import NpDnaModel
        model = NpDnaModel(config)

        # Restore strand IDs
        strand_ids = meta.get("strand_ids")
        if strand_ids:
            model.restore_strand_id_map(strand_ids)
        else:
            base_cfg = CONFIGS.get(str(meta.get("train_config_name") or meta.get("config_name")))
            base_n = base_cfg.mesh.num_strands if base_cfg else meta["num_strands"]
            if meta["num_strands"] > base_n:
                growth = meta["num_strands"] - base_n
                inferred = [
                    list(range(li * base_n, li * base_n + base_n))
                    + [base_n * meta["num_layers"] + g * meta["num_layers"] + li for g in range(growth)]
                    for li in range(meta["num_layers"])
                ]
                model.restore_strand_id_map(inferred)

        try:
            model.load_state_dict(state, strict=False)
        except RuntimeError as exc:
            msg = str(exc)
            if any(kw in msg for kw in ("size mismatch", "Missing key", "Unexpected key")):
                raise RuntimeError(
                    f"Checkpoint at {path} has mismatched architecture dimensions between metadata.json and model.pt. "
                    f"Metadata: hidden={config.hidden_size}, layers={config.num_layers}, "
                    f"strands={inferred_strands}. Original: {msg}"
                ) from exc
            raise

        tokenizer = AtulyaTokenizer.load(path / "tokenizer.json")
        cortex_path = path / "cortex"
        cortex = MemoryCortex.load(cortex_path, config.cortex) if cortex_path.exists() else MemoryCortex(config.cortex)

        logger.info(
            "NpDnaCore loaded ← %s (%s params, %d cortex entries)",
            path, f"{model.parameter_count():,}", cortex.size,
        )
        core = cls(model=model, tokenizer=tokenizer, cortex=cortex, config=config)
        core.active_path = path
        return core

    def _match_config_name(self) -> str:
        from .config import CONFIGS
        for name, c in CONFIGS.items():
            if (
                c.hidden_size == self.config.hidden_size
                and c.num_layers == self.config.num_layers
                and c.mesh.num_strands == self.config.mesh.num_strands
                and c.mesh.top_k == self.config.mesh.top_k
                and c.initial_vocab == self.config.initial_vocab
            ):
                return name
        return "custom"
