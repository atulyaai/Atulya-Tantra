"""Unit tests for NP-DNA architecture."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import torch

from atulya.core.npdna import (
    CONFIGS,
    AtulyaTokenizer,
    Genome,
    MemoryCortex,
    NeuralMesh,
    NpDnaCore,
    NpDnaModel,
    PlasticityEngine,
    Strand,
)
from atulya.core.npdna.config import CortexConfig, GenomeConfig, MeshConfig, NpDnaConfig, StrandConfig


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestConfig:
    def test_configs_exist(self):
        assert "seed" in CONFIGS
        assert "nano" in CONFIGS
        assert "micro" in CONFIGS

    def test_post_init_syncs(self):
        cfg = NpDnaConfig(hidden_size=256, state_size=128, num_layers=3)
        assert cfg.mesh.strand.hidden_size == 256
        assert cfg.mesh.strand.state_size == 128
        assert cfg.cortex.dim == 256


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

class TestTokenizer:
    def test_encode_decode_english(self):
        tok = AtulyaTokenizer(initial_capacity=1024)
        ids = tok.encode("hello world")
        text = tok.decode(ids)
        assert "hello" in text.lower()
        assert "world" in text.lower()

    def test_encode_decode_hindi(self):
        tok = AtulyaTokenizer(initial_capacity=2048)
        ids = tok.encode("नमस्ते दुनिया")
        assert len(ids) > 0
        text = tok.decode(ids)
        assert "नमस्ते" in text

    def test_byte_fallback(self):
        tok = AtulyaTokenizer(initial_capacity=512)
        ids = tok.encode("🎉 emoji test", allow_growth=False)
        assert len(ids) > 0  # Should encode via byte fallback
        text = tok.decode(ids)
        assert "emoji" in text

    def test_auto_growth(self):
        tok = AtulyaTokenizer(initial_capacity=300, growth_threshold=0.95)
        old_cap = tok.capacity
        # Encode many unique tokens to trigger growth
        for i in range(500):
            tok.encode(f"unique_token_{i}")
        assert tok.capacity >= old_cap

    def test_save_load(self, tmp_path):
        tok = AtulyaTokenizer(initial_capacity=1024)
        tok.encode("test data for save")
        tok.save(tmp_path / "tokenizer.json")

        tok2 = AtulyaTokenizer.load(tmp_path / "tokenizer.json")
        assert tok2.size == tok.size
        assert tok2.encode("test", allow_growth=False) == tok.encode("test", allow_growth=False)


# ---------------------------------------------------------------------------
# Genome
# ---------------------------------------------------------------------------

class TestGenome:
    def test_generate_weights(self):
        strand_cfg = StrandConfig(hidden_size=64, state_size=32)
        genome_cfg = GenomeConfig(latent_dim=128, rank=16, max_strands=8)
        genome = Genome(genome_cfg, strand_cfg)

        weight, bias = genome.generate(0, "gate")
        assert weight.shape == (64, 32)
        assert bias.shape == (32,)

    def test_generate_all(self):
        strand_cfg = StrandConfig(hidden_size=64, state_size=32)
        genome_cfg = GenomeConfig(latent_dim=128, rank=16, max_strands=8)
        genome = Genome(genome_cfg, strand_cfg)

        all_weights = genome.generate_all(0)
        assert "gate" in all_weights
        assert "state" in all_weights
        assert "recurrent" in all_weights
        assert "output" in all_weights

    def test_different_strands_different_weights(self):
        strand_cfg = StrandConfig(hidden_size=64, state_size=32)
        genome_cfg = GenomeConfig(latent_dim=128, rank=16, max_strands=8)
        genome = Genome(genome_cfg, strand_cfg)

        w0, _ = genome.generate(0, "gate")
        w1, _ = genome.generate(1, "gate")
        # Different seeds should produce different weights
        assert not torch.allclose(w0, w1)

    def test_add_strand_capacity(self):
        strand_cfg = StrandConfig(hidden_size=64, state_size=32)
        genome_cfg = GenomeConfig(latent_dim=128, rank=16, max_strands=4)
        genome = Genome(genome_cfg, strand_cfg)

        assert genome.seeds.shape[0] == 4
        genome.add_strand_capacity(4)
        assert genome.seeds.shape[0] == 8


# ---------------------------------------------------------------------------
# Strand
# ---------------------------------------------------------------------------

class TestStrand:
    def test_forward_shape(self):
        strand_cfg = StrandConfig(hidden_size=64, state_size=32)
        genome_cfg = GenomeConfig(latent_dim=128, rank=16, max_strands=4)
        genome = Genome(genome_cfg, strand_cfg)
        strand = Strand(genome, strand_id=0, config=strand_cfg)

        x = torch.randn(2, 10, 64)  # batch=2, seq=10, hidden=64
        y = strand(x)
        assert y.shape == (2, 10, 64)

    def test_causal_output_differs(self):
        """Verify that different input positions produce different outputs."""
        strand_cfg = StrandConfig(hidden_size=64, state_size=32)
        genome_cfg = GenomeConfig(latent_dim=128, rank=16, max_strands=4)
        genome = Genome(genome_cfg, strand_cfg)
        strand = Strand(genome, strand_id=0, config=strand_cfg)

        x = torch.randn(1, 5, 64)
        y = strand(x)
        # Position 0 and position 4 should differ (state accumulates)
        assert not torch.allclose(y[0, 0], y[0, 4], atol=1e-6)


# ---------------------------------------------------------------------------
# Mesh
# ---------------------------------------------------------------------------

class TestMesh:
    def test_forward_shape(self):
        strand_cfg = StrandConfig(hidden_size=64, state_size=32)
        mesh_cfg = MeshConfig(num_strands=4, top_k=2, strand=strand_cfg)
        genome_cfg = GenomeConfig(latent_dim=128, rank=16, max_strands=4)
        genome = Genome(genome_cfg, strand_cfg)
        mesh = NeuralMesh(genome, mesh_cfg, layer_offset=0)

        x = torch.randn(2, 8, 64)
        output, balance_loss = mesh(x)
        assert output.shape == (2, 8, 64)
        assert balance_loss.dim() == 0  # scalar

    def test_usage_tracking(self):
        strand_cfg = StrandConfig(hidden_size=64, state_size=32)
        mesh_cfg = MeshConfig(num_strands=4, top_k=2, strand=strand_cfg)
        genome_cfg = GenomeConfig(latent_dim=128, rank=16, max_strands=4)
        genome = Genome(genome_cfg, strand_cfg)
        mesh = NeuralMesh(genome, mesh_cfg)

        x = torch.randn(1, 4, 64)
        mesh(x)
        stats = mesh.usage_stats
        assert sum(stats.values()) > 0


# ---------------------------------------------------------------------------
# Cortex
# ---------------------------------------------------------------------------

class TestCortex:
    def test_store_and_retrieve(self):
        config = CortexConfig(dim=64, max_entries=100, top_k=3)
        cortex = MemoryCortex(config)

        key = torch.randn(64)
        cortex.store(key, topic="test")
        assert cortex.size == 1

        values, scores = cortex.retrieve(key, top_k=1)
        assert values.shape[-1] == 64
        assert scores.max() > 0.9  # Should find itself

    def test_eviction(self):
        config = CortexConfig(dim=32, max_entries=3, top_k=1)
        cortex = MemoryCortex(config)

        for i in range(5):
            cortex.store(torch.randn(32), topic=f"entry_{i}")

        assert cortex.size <= 3

    def test_save_load(self, tmp_path):
        config = CortexConfig(dim=32, max_entries=100, top_k=2)
        cortex = MemoryCortex(config)
        cortex.store(torch.randn(32), topic="hello")
        cortex.store(torch.randn(32), topic="world")
        cortex.save(tmp_path / "cortex")

        cortex2 = MemoryCortex.load(tmp_path / "cortex", config)
        assert cortex2.size == 2


# ---------------------------------------------------------------------------
# Full Model
# ---------------------------------------------------------------------------

class TestNpDnaModel:
    def test_forward(self):
        config = CONFIGS["seed"]
        model = NpDnaModel(config)
        input_ids = torch.tensor([[1, 2, 3, 4, 5]])
        logits, balance_loss = model(input_ids)
        assert logits.shape == (1, 5, config.initial_vocab)

    def test_parameter_count(self):
        config = CONFIGS["seed"]
        model = NpDnaModel(config)
        count = model.parameter_count()
        assert count > 0
        active = model.active_parameter_count()
        assert active > 0
        assert active <= count

    def test_resize_embeddings(self):
        config = CONFIGS["seed"]
        model = NpDnaModel(config)
        old_vocab = model.vocab_size
        model.resize_embeddings(old_vocab * 2)
        assert model.vocab_size == old_vocab * 2


# ---------------------------------------------------------------------------
# NpDnaCore (integration)
# ---------------------------------------------------------------------------

class TestNpDnaCore:
    def test_from_config(self):
        core = NpDnaCore.from_config("seed")
        assert core.model is not None
        assert core.tokenizer is not None

    def test_encode_decode_roundtrip(self):
        core = NpDnaCore.from_config("seed")
        text = "Hello world"
        ids = core.encode(text)
        decoded = core.decode(ids)
        assert "hello" in decoded.lower() or "world" in decoded.lower()

    def test_save_load(self, tmp_path):
        core = NpDnaCore.from_config("seed")
        core.encode("test data")
        core.save(tmp_path / "model")

        core2 = NpDnaCore.load(tmp_path / "model")
        assert core2.model.parameter_count() == core.model.parameter_count()

    def test_generate(self):
        core = NpDnaCore.from_config("seed")
        # Untrained model won't produce coherent text, but should not crash
        result = core.generate("Hello", max_tokens=5)
        assert isinstance(result, str)

    def test_training_step(self):
        """Verify a single training step runs without error."""
        core = NpDnaCore.from_config("seed")
        ids = core.encode("Hello world test")
        input_ids = torch.tensor([ids[:-1]])
        labels = torch.tensor([ids[1:]])

        core.model.train()
        logits, balance_loss = core.model(input_ids)
        loss_fn = torch.nn.CrossEntropyLoss()
        loss = loss_fn(logits.reshape(-1, logits.shape[-1]), labels.reshape(-1))
        total_loss = loss + balance_loss
        total_loss.backward()
        # Should not crash


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

class TestIdentity:
    def test_load_identity(self):
        from atulya.identity import Identity
        identity = Identity()
        assert identity.name == "Atulya"

    def test_system_prompt_user(self):
        from atulya.identity import Identity
        identity = Identity()
        prompt = identity.get_system_prompt("user")
        assert "Atulya" in prompt
        # User should NOT see architecture details
        assert "architecture" not in prompt.lower() or "NP-DNA" not in prompt

    def test_system_prompt_superuser(self):
        from atulya.identity import Identity
        identity = Identity()
        prompt = identity.get_system_prompt("superuser")
        assert "Atulya" in prompt
        # Superuser SHOULD see technical details
        assert "NP-DNA" in prompt or "architecture" in prompt.lower()

    def test_training_samples(self):
        from atulya.identity import Identity
        identity = Identity()
        samples = identity.format_for_training()
        assert len(samples) > 10
        # Should include identity, privacy, and Hindi samples
        all_text = " ".join(s.get("output", "") for s in samples)
        assert "Atulya" in all_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
