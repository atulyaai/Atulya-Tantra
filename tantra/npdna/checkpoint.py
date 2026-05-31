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
            "layer_specs": [
                {
                    "name": spec.name,
                    "num_strands": spec.num_strands,
                    "top_k": spec.top_k,
                }
                for spec in getattr(self.model, "layer_specs", [])
            ],
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
        logger.info("NpDnaCore saved â†’ %s (%s params)", path, f"{self.model.parameter_count():,}")

    @classmethod
    def load(cls, path: str | Path) -> "CheckpointMixin":
        from .config import CONFIGS, CortexConfig, GenomeConfig, LayerSpec, MeshConfig, NpDnaConfig, StrandConfig
        from .cortex import MemoryCortex
        from .tokenizer import AtulyaTokenizer

        path = Path(path)
        meta = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
        if (path / "model.pt").exists():
            state = torch.load(path / "model.pt", map_location="cpu", weights_only=True)
        elif cls._is_component_format(path):
            state = cls._load_components(path)
        elif cls._is_sharded_format(path):
            index = json.loads((path / "model_index.json").read_text(encoding="utf-8"))
            state = cls._load_sharded(path, index)
        else:
            raise FileNotFoundError(f"Checkpoint at {path} has neither model.pt nor component model_index.json")

        # Check for mismatched architecture dimensions between metadata.json and model.pt
        if "embedding.weight" in state:
            saved_hidden_size = state["embedding.weight"].shape[1]
            meta_hidden_size = meta.get("hidden_size")
            if meta_hidden_size is not None and saved_hidden_size != meta_hidden_size:
                raise RuntimeError(
                    f"Checkpoint at {path} has mismatched architecture dimensions between metadata.json and model.pt "
                    f"(metadata hidden_size {meta_hidden_size} vs model.pt hidden_size {saved_hidden_size})"
                )

        # Infer actual strand count from weights (beats stale metadata)
        inferred_strands = max(
            (int(m.group(1)) + 1
             for k in state
             if (m := re.match(r"mesh_layers\.\d+\.strands\.(\d+)\.", k))),
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
        layer_specs = [
            LayerSpec(
                name=str(item.get("name", "main")),
                num_strands=int(item.get("num_strands", inferred_strands)),
                top_k=int(item.get("top_k", meta["top_k"])),
                strand=StrandConfig(hidden_size=meta["hidden_size"], state_size=meta["state_size"]),
            )
            for item in meta.get("layer_specs", [])
        ]
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
            mesh_specs=layer_specs,
            genome=genome_cfg,
            cortex=cortex_cfg,
        )

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
            if not layer_specs and meta["num_strands"] > base_n:
                growth = meta["num_strands"] - base_n
                inferred = [
                    list(range(li * base_n, li * base_n + base_n))
                    + [base_n * meta["num_layers"] + g * meta["num_layers"] + li for g in range(growth)]
                    for li in range(meta["num_layers"])
                ]
                model.restore_strand_id_map(inferred)

        # Gracefully handle size mismatches — don't crash, just skip mismatched weights
        # This lets users load checkpoints from different architectures (e.g. seed → nano)
        # without deleting and re-copying files. Mismatched params keep their init values.
        model_state = model.state_dict()
        for key in list(state.keys()):
            if key in model_state:
                if state[key].shape != model_state[key].shape:
                    logger.warning(
                        "Size mismatch for '%s': checkpoint %s vs model %s. "
                        "Skipping — weight will use random init instead of checkpoint.",
                        key, list(state[key].shape), list(model_state[key].shape),
                    )
                    del state[key]
            else:
                logger.debug("Key '%s' in checkpoint not found in model. Skipping.", key)
        model.load_state_dict(state, strict=False)

        tokenizer = AtulyaTokenizer.load(path / "tokenizer.json")
        cortex_path = path / "cortex"
        cortex = MemoryCortex.load(cortex_path, config.cortex) if cortex_path.exists() else MemoryCortex(config.cortex)

        logger.info(
            "NpDnaCore loaded â† %s (%s params, %d cortex entries)",
            path, f"{model.parameter_count():,}", cortex.size,
        )
        core = cls(model=model, tokenizer=tokenizer, cortex=cortex, config=config)
        core.active_path = path
        return core

    @staticmethod
    def _is_component_format(path: Path) -> bool:
        """Check if model_index.json points to component files (v3) vs shards (v2)."""
        try:
            idx = json.loads((path / "model_index.json").read_text(encoding="utf-8"))
            return "component_files" in idx
        except Exception:
            return False

    @staticmethod
    def _is_sharded_format(path: Path) -> bool:
        """Check if model_index.json points to shard files (v2) vs component files (v3)."""
        try:
            idx = json.loads((path / "model_index.json").read_text(encoding="utf-8"))
            return "weight_files" in idx
        except Exception:
            return False

    @staticmethod
    def _load_components(path: Path) -> dict[str, torch.Tensor]:
        """Load state dict from component files (genome.pt, embedding.pt, layer_*.pt, final_norm.pt)."""
        idx = json.loads((path / "model_index.json").read_text(encoding="utf-8"))
        components = idx["component_files"]
        vocabulary_file = components.get("vocabulary") or components.get("embedding")
        if not vocabulary_file:
            raise KeyError(
                f"Checkpoint at {path} is missing both 'vocabulary' and 'embedding' keys "
                "in model_index.json component_files"
            )
        required_files = [components["genome"], vocabulary_file, *components["layers"], components["final_norm"]]
        missing = [fname for fname in required_files if not (path / fname).exists()]
        if missing:
            raise FileNotFoundError(
                f"Checkpoint at {path} is component-indexed but missing weight files: {missing}"
            )
        state = {}

        # Load genome
        genome = torch.load(path / components["genome"], map_location="cpu", weights_only=True)
        state.update(genome)
        logger.debug("Loaded genome.pt (%d tensors)", len(genome))

        # Load embedding
        embedding = torch.load(path / vocabulary_file, map_location="cpu", weights_only=True)
        state.update(embedding)
        logger.debug("Loaded embedding.pt (%d tensors)", len(embedding))

        # Load per-layer files
        for fname in components["layers"]:
            layer = torch.load(path / fname, map_location="cpu", weights_only=True)
            state.update(layer)
            logger.debug("Loaded %s (%d tensors)", fname, len(layer))

        # Load final norm
        final_norm = torch.load(path / components["final_norm"], map_location="cpu", weights_only=True)
        state.update(final_norm)
        logger.debug("Loaded final_norm.pt (%d tensors)", len(final_norm))

        logger.info("Loaded state from %d component files", len(required_files))
        return state

    @staticmethod
    def _load_sharded(path: Path, index: dict) -> dict[str, torch.Tensor]:
        """Load state dict from multiple shard files listed in model_index.json (v2 format)."""
        state = {}
        for wf in index["weight_files"]:
            shard = torch.load(path / wf, map_location="cpu", weights_only=True)
            state.update(shard)
            logger.debug("Loaded shard %s (%d tensors)", wf, len(shard))
        return state

    # â”€â”€ Config matching â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

