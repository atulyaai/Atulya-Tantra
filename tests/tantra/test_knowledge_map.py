"""Tests for KnowledgeMap, VectorIndex, FactCheck, LoRASimulator, TrainingTypeRegistry."""

import tempfile
import math


class TestVectorIndex:
    """Tests for VectorIndex â€” cosine similarity based ANN."""

    def test_add_and_search(self):
        from tantra.training.knowledge_map import VectorIndex
        idx = VectorIndex(dim=4)
        idx.add("a", [1.0, 0.0, 0.0, 0.0])
        idx.add("b", [0.0, 1.0, 0.0, 0.0])
        idx.add("c", [0.5, 0.5, 0.0, 0.0])
        results = idx.search([1.0, 0.0, 0.0, 0.0], top_k=2)
        assert len(results) == 2
        assert results[0][0] == "a"

    def test_search_empty(self):
        from tantra.training.knowledge_map import VectorIndex
        idx = VectorIndex(dim=4)
        assert idx.search([1.0, 0.0, 0.0, 0.0]) == []

    def test_cosine_similarity(self):
        from tantra.training.knowledge_map import VectorIndex
        sim = VectorIndex._cosine_similarity([1.0, 0.0], [0.0, 1.0])
        assert sim == 0.0

    def test_cosine_similarity_identical(self):
        from tantra.training.knowledge_map import VectorIndex
        sim = VectorIndex._cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
        assert abs(sim - 1.0) < 1e-6

    def test_cosine_similarity_empty(self):
        from tantra.training.knowledge_map import VectorIndex
        assert VectorIndex._cosine_similarity([], [1.0]) == 0.0

    def test_cosine_similarity_zero_norm(self):
        from tantra.training.knowledge_map import VectorIndex
        assert VectorIndex._cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_len(self):
        from tantra.training.knowledge_map import VectorIndex
        idx = VectorIndex(dim=4)
        assert len(idx) == 0
        idx.add("a", [1.0, 0.0, 0.0, 0.0])
        assert len(idx) == 1


class TestKnowledgeMap:
    """Tests for KnowledgeMap â€” RAG, fact checking, relations."""

    def test_add_knowledge(self):
        from tantra.training.knowledge_map import KnowledgeMap
        with tempfile.TemporaryDirectory() as tmp:
            km = KnowledgeMap(data_dir=tmp)
            nid = km.add_knowledge("AI", "Artificial Intelligence is the simulation of human intelligence")
            assert nid is not None
            assert len(nid) == 16

    def test_add_knowledge_with_tags(self):
        from tantra.training.knowledge_map import KnowledgeMap
        with tempfile.TemporaryDirectory() as tmp:
            km = KnowledgeMap(data_dir=tmp)
            nid = km.add_knowledge("Python", "Python is a programming language",
                                   sources=["docs.python.org"], tags=["programming", "language"])
            assert nid is not None

    def test_retrieve(self):
        from tantra.training.knowledge_map import KnowledgeMap
        with tempfile.TemporaryDirectory() as tmp:
            km = KnowledgeMap(data_dir=tmp)
            km.add_knowledge("Python", "Python is a high-level programming language")
            km.add_knowledge("Java", "Java is a compiled programming language")
            results = km.retrieve("programming language", top_k=2)
            assert len(results) >= 1

    def test_retrieve_empty(self):
        from tantra.training.knowledge_map import KnowledgeMap
        with tempfile.TemporaryDirectory() as tmp:
            km = KnowledgeMap(data_dir=tmp)
            results = km.retrieve("something", top_k=5)
            assert results == []

    def test_fact_check_unverified(self):
        from tantra.training.knowledge_map import KnowledgeMap
        with tempfile.TemporaryDirectory() as tmp:
            km = KnowledgeMap(data_dir=tmp)
            check = km.fact_check("Unknown claim about nothing")
            assert check.verdict == "unverified"
            assert check.confidence == 0.0

    def test_fact_check_with_knowledge(self):
        from tantra.training.knowledge_map import KnowledgeMap
        with tempfile.TemporaryDirectory() as tmp:
            km = KnowledgeMap(data_dir=tmp)
            km.add_knowledge("Python", "Python is a high-level programming language created by Guido van Rossum")
            check = km.fact_check("Python is a programming language")
            assert check.verdict in ("true", "mixed", "unverified")

    def test_add_relation(self):
        from tantra.training.knowledge_map import KnowledgeMap
        with tempfile.TemporaryDirectory() as tmp:
            km = KnowledgeMap(data_dir=tmp)
            a = km.add_knowledge("Topic A", "Content A")
            b = km.add_knowledge("Topic B", "Content B")
            km.add_relation(a, b)
            rels = km.get_relations(a)
            assert len(rels) == 1

    def test_get_relations_nonexistent(self):
        from tantra.training.knowledge_map import KnowledgeMap
        with tempfile.TemporaryDirectory() as tmp:
            km = KnowledgeMap(data_dir=tmp)
            assert km.get_relations("nonexistent") == []

    def test_add_relation_invalid(self):
        from tantra.training.knowledge_map import KnowledgeMap
        with tempfile.TemporaryDirectory() as tmp:
            km = KnowledgeMap(data_dir=tmp)
            # Should not crash
            km.add_relation("nonexistent", "also_nonexistent")

    def test_get_stats(self):
        from tantra.training.knowledge_map import KnowledgeMap
        with tempfile.TemporaryDirectory() as tmp:
            km = KnowledgeMap(data_dir=tmp)
            km.add_knowledge("A", "Content A")
            km.add_knowledge("B", "Content B")
            stats = km.get_stats()
            assert stats["total_nodes"] == 2
            assert stats["index_size"] == 2

    def test_simple_embed(self):
        from tantra.training.knowledge_map import KnowledgeMap
        emb = KnowledgeMap._simple_embed("hello world", dim=8)
        assert len(emb) == 8
        norm = math.sqrt(sum(x*x for x in emb))
        assert abs(norm - 1.0) < 1e-6

    def test_persistence(self):
        """Knowledge should survive across KnowledgeMap re-initialization."""
        from tantra.training.knowledge_map import KnowledgeMap
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            km1 = KnowledgeMap(data_dir=tmp)
            km1.add_knowledge("Persistent", "This knowledge should persist")
            km2 = KnowledgeMap(data_dir=tmp)
            stats = km2.get_stats()
            assert stats["total_nodes"] == 1


class TestLoRASimulator:
    """Tests for LoRASimulator â€” CPU-based LoRA adapter simulation."""

    def test_create_adapter(self):
        from tantra.training.knowledge_map import LoRASimulator
        sim = LoRASimulator(rank=4)
        adapter = sim.create_adapter("my_lora", "biology", [
            {"input": "what is DNA", "output": "DNA is..."},
        ])
        assert adapter["name"] == "my_lora"
        assert adapter["topic"] == "biology"

    def test_apply_adapter(self):
        from tantra.training.knowledge_map import LoRASimulator
        sim = LoRASimulator(rank=4)
        sim.create_adapter("bio_adapter", "biology", [])
        result = sim.apply_adapter("bio_adapter", "What is life?")
        assert "[biology]" in result

    def test_apply_adapter_not_found(self):
        from tantra.training.knowledge_map import LoRASimulator
        sim = LoRASimulator(rank=4)
        result = sim.apply_adapter("nonexistent", "Hello")
        assert result == "Hello"

    def test_get_adapters_empty(self):
        from tantra.training.knowledge_map import LoRASimulator
        sim = LoRASimulator(rank=4)
        assert sim.get_adapters() == []

    def test_get_adapters(self):
        from tantra.training.knowledge_map import LoRASimulator
        sim = LoRASimulator(rank=4)
        sim.create_adapter("a", "math", [])
        sim.create_adapter("b", "physics", [])
        assert len(sim.get_adapters()) == 2

    def test_init_weights(self):
        from tantra.training.knowledge_map import LoRASimulator
        weights = LoRASimulator._init_weights(4)
        assert len(weights) == 16  # rank^2


class TestTrainingTypeRegistry:
    """Tests for TrainingTypeRegistry â€” training type metadata."""

    def test_list_types(self):
        from tantra.training.knowledge_map import TrainingTypeRegistry
        reg = TrainingTypeRegistry()
        types = reg.list_types()
        assert "sft" in types
        assert "dpo" in types
        assert "lora" in types

    def test_get_config_sft(self):
        from tantra.training.knowledge_map import TrainingTypeRegistry
        reg = TrainingTypeRegistry()
        config = reg.get_config("sft")
        assert config["lr"] == 2e-5
        assert config["epochs"] == 3

    def test_get_config_dpo(self):
        from tantra.training.knowledge_map import TrainingTypeRegistry
        reg = TrainingTypeRegistry()
        config = reg.get_config("dpo")
        assert config["beta"] == 0.1

    def test_get_config_unknown(self):
        from tantra.training.knowledge_map import TrainingTypeRegistry
        reg = TrainingTypeRegistry()
        assert reg.get_config("unknown") == {}
