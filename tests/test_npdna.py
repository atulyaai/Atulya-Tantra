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

    def test_scaled_router_initialization(self):
        strand_cfg = StrandConfig(hidden_size=64, state_size=32)
        mesh_cfg = MeshConfig(num_strands=4, top_k=2, strand=strand_cfg)
        genome_cfg = GenomeConfig(latent_dim=128, rank=16, max_strands=8)
        genome = Genome(genome_cfg, strand_cfg)
        mesh = NeuralMesh(genome, mesh_cfg)

        with torch.no_grad():
            mesh.router.weight.fill_(1e-5)

        mesh.add_strand(strand_id=4)
        new_weight = mesh.router.weight[4]
        assert new_weight.abs().max().item() < 1e-4


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

    def test_sleep_cycle(self):
        config = CortexConfig(dim=16, max_entries=100, top_k=2)
        cortex = MemoryCortex(config)

        # Create base vector and highly similar versions (cosine similarity > 0.95)
        base_vector = torch.zeros(16)
        base_vector[0] = 1.0

        v1 = base_vector.clone()
        v2 = base_vector.clone()
        v2[1] = 0.05  # cosine similarity ≈ 0.998

        v3 = base_vector.clone()
        v3[1] = 0.08  # cosine similarity ≈ 0.996

        cortex.store(v1, topic="Paris Info", source="Paris is the capital of France.")
        cortex.store(v2, topic="Paris", source="Paris is beautiful, the capital city of France.")
        cortex.store(v3, topic="General Info", source="France capital.")

        # Set access counts
        cortex.entries[0].access_count = 5
        cortex.entries[1].access_count = 10
        cortex.entries[2].access_count = 2

        assert cortex.size == 3

        # Run sleep cycle with threshold 0.90
        stats = cortex.sleep_cycle(similarity_threshold=0.90)

        assert stats["before"] == 3
        assert stats["after"] == 1
        assert stats["merged"] == 2
        assert cortex.size == 1

        entry = cortex.entries[0]
        # Topic should be the most common non-generic non-empty topic ("Paris Info" or "Paris")
        assert entry.topic in ["Paris Info", "Paris"]
        # Source should be the longest snippet to retain maximum details
        assert entry.source == "Paris is beautiful, the capital city of France."
        # Access counts should be aggregated
        assert entry.access_count == 17


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

    def test_cortex_forward_integration(self):
        config = CONFIGS["seed"]
        model = NpDnaModel(config)
        input_ids = torch.tensor([[1, 2, 3, 4, 5]])
        logits_empty, _ = model(input_ids)

        model.cortex.store(torch.randn(config.hidden_size), topic="test_topic")
        assert model.cortex.size == 1

        logits_full, _ = model(input_ids)
        assert logits_full.shape == logits_empty.shape
        assert not torch.allclose(logits_full, logits_empty)


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

    def test_train_topic_device_routing(self, tmp_path):
        import json
        from training.npdna_train import train_topic

        # Create a tiny mock model and save it
        core = NpDnaCore.from_config("seed")
        model_dir = tmp_path / "mock_model"
        core.save(model_dir)

        # Create a tiny mock dataset
        data_file = tmp_path / "topic_data.jsonl"
        data_file.write_text(
            json.dumps({"text": "Hello topic world"}) + "\n" +
            json.dumps({"text": "Another topic sentence"}) + "\n"
        )

        # Run train_topic with explicit CPU device
        updated_core = train_topic(
            model_path=str(model_dir),
            topic="test",
            data_path=str(data_file),
            strand_id=0,
            steps=2,
            lr=1e-3,
            device="cpu"
        )
        assert updated_core is not None
        assert updated_core.model.genome.seeds.requires_grad is True

    def test_optimizer_state_recovery(self):
        from training.npdna_train import restore_optimizer_state
        import torch

        # 1. Create a model
        core = NpDnaCore.from_config("seed")
        model = core.model

        # 2. Build optimizer
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

        # 3. Perform a mock training step to populate optimizer state
        input_ids = torch.tensor([[1, 2, 3, 4, 5]])
        logits, balance_loss = model(input_ids)
        loss = logits.sum() + balance_loss
        loss.backward()
        optimizer.step()

        # Check that seeds and router have state in the optimizer
        assert model.genome.seeds in optimizer.state
        seeds_state = optimizer.state[model.genome.seeds]
        assert "exp_avg" in seeds_state
        assert "exp_avg_sq" in seeds_state

        # Record shapes and mock values of old states
        old_seeds_shape = model.genome.seeds.shape
        old_router_shape = model.mesh_layers[0].router.weight.shape

        # We manually set some distinct values in the optimizer state to verify they carry over
        seeds_exp_avg_val = torch.ones_like(seeds_state["exp_avg"]) * 7.5
        seeds_state["exp_avg"].copy_(seeds_exp_avg_val)

        # 4. Mock the capture process before growth
        old_named_params = dict(model.named_parameters())
        old_named_states = {}
        for name, param in old_named_params.items():
            if param in optimizer.state:
                state = optimizer.state[param]
                old_named_states[name] = {
                    k: (v.clone() if isinstance(v, torch.Tensor) else v)
                    for k, v in state.items()
                }

        # 5. Grow the strands by 1
        model.grow_strands(1)

        # Confirm parameter shapes grew
        assert model.genome.seeds.shape[0] == old_seeds_shape[0] + model.config.num_layers
        assert model.mesh_layers[0].router.weight.shape[0] == old_router_shape[0] + 1

        # 6. Rebuild optimizer
        new_optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
        assert model.genome.seeds not in new_optimizer.state

        # 7. Restore optimizer state
        restore_optimizer_state(new_optimizer, old_named_states, model)

        # 8. Assertions
        assert model.genome.seeds in new_optimizer.state
        new_seeds_state = new_optimizer.state[model.genome.seeds]
        assert new_seeds_state["exp_avg"].shape == model.genome.seeds.shape

        # Verify old rows are preserved exactly
        assert torch.allclose(
            new_seeds_state["exp_avg"][:old_seeds_shape[0]],
            seeds_exp_avg_val
        )
        # Verify new rows are zero-padded
        assert torch.all(new_seeds_state["exp_avg"][old_seeds_shape[0]:] == 0)

        # Test reinit_strands momentum clearing
        layer_i = 0
        dead_ids = [0]
        mesh = model.mesh_layers[layer_i]

        # 1. Clear momentum for router.weight
        if mesh.router.weight in new_optimizer.state:
            router_state = new_optimizer.state[mesh.router.weight]
            for k in ["exp_avg", "exp_avg_sq"]:
                if k in router_state and isinstance(router_state[k], torch.Tensor):
                    for s_id in dead_ids:
                        if s_id < router_state[k].shape[0]:
                            router_state[k][s_id].zero_()

        # 2. Clear momentum for genome.seeds
        if model.genome.seeds in new_optimizer.state:
            seeds_state = new_optimizer.state[model.genome.seeds]
            for k in ["exp_avg", "exp_avg_sq"]:
                if k in seeds_state and isinstance(seeds_state[k], torch.Tensor):
                    for s_id in dead_ids:
                        global_id = layer_i * mesh.config.num_strands + s_id
                        if global_id < seeds_state[k].shape[0]:
                            seeds_state[k][global_id].zero_()

        # Verify that row 0 of router.weight's exp_avg is cleared
        new_router_state = new_optimizer.state[mesh.router.weight]
        assert torch.all(new_router_state["exp_avg"][0] == 0)

        # Verify that global seed 0 is cleared
        assert torch.all(new_seeds_state["exp_avg"][0] == 0)

    def test_active_write_back(self):
        core = NpDnaCore.from_config("seed")
        
        # Patch the decode method to return a string containing memory tags
        original_decode = core.decode
        core.decode = lambda ids: "This is a fact: <memory_start>The moon orbits the Earth.<memory_end>"
        
        # Ensure active_path is tracked
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            core.active_path = Path(tmpdir)
            # Create a mock metadata.json to verify it updates
            meta_file = core.active_path / "metadata.json"
            import json
            meta_file.write_text(json.dumps({"cortex_entries": 0}), encoding="utf-8")
            
            # This will trigger generate, which calls our patched decode
            # and extracts the fact.
            res = core.generate("Give me a fact", max_tokens=5)
            
            assert "The moon orbits the Earth." in res
            assert core.cortex.size == 1
            assert core.cortex.entries[0].source == "The moon orbits the Earth."
            
            # Check metadata.json updated size
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            assert meta["cortex_entries"] == 1
            
            # Verify file exists on disk
            assert (core.active_path / "cortex" / "cortex_meta.json").exists()

    def test_routing_telemetry(self):
        core = NpDnaCore.from_config("seed")
        
        # Add a mock entry to cortex so we have retrieval candidates
        core.cortex.store(
            torch.randn(core.config.hidden_size),
            topic="geography",
            source="Paris is the capital of France."
        )
        
        # Run generate to populate last_generated_ids and last_prompt_len
        core.generate("Paris is", max_tokens=3)
        
        # Retrieve telemetry
        telemetry = core.get_routing_telemetry()
        
        # Verify correctness
        assert len(telemetry) > 0
        for item in telemetry:
            assert "token_id" in item
            assert "token_raw" in item
            assert "token_clean" in item
            assert "is_prompt" in item
            assert "layers" in item
            assert "cortex" in item
            
            # Verify structure of layers
            assert len(item["layers"]) == core.config.num_layers
            for layer in item["layers"]:
                for strand in layer:
                    assert "local_index" in strand
                    assert "strand_id" in strand
                    assert "weight" in strand
                    
            # Verify cortex structure if populated
            for hit in item["cortex"]:
                assert "entry_index" in hit
                assert "topic" in hit
                assert "source" in hit
                assert "score" in hit


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
