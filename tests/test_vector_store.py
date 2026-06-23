"""Tests for VectorMemoryProvider - hash-based embedding semantic search."""
from __future__ import annotations

import asyncio
import json
import math
import tempfile
from pathlib import Path

import pytest

from atulya.memory.vector_store import VectorMemoryProvider, _cosine_similarity, _hash_embed
from atulya.memory.orchestrator import MemoryEntry


class TestHashEmbed:
    def test_deterministic(self):
        v1 = _hash_embed("hello world")
        v2 = _hash_embed("hello world")
        assert v1 == v2

    def test_different_inputs_different_vectors(self):
        v1 = _hash_embed("hello world")
        v2 = _hash_embed("goodbye universe")
        assert v1 != v2

    def test_default_dimension(self):
        v = _hash_embed("test")
        assert len(v) == 128

    def test_custom_dimension(self):
        v = _hash_embed("test", dim=64)
        assert len(v) == 64

    def test_normalized(self):
        v = _hash_embed("test message")
        norm = math.sqrt(sum(x * x for x in v))
        assert abs(norm - 1.0) < 1e-6

    def test_empty_string(self):
        v = _hash_embed("")
        assert len(v) == 128

    def test_similar_texts_closer(self):
        v1 = _hash_embed("write a python function")
        v2 = _hash_embed("write a python script")
        v3 = _hash_embed("buy groceries at store")
        sim_related = _cosine_similarity(v1, v2)
        sim_unrelated = _cosine_similarity(v1, v3)
        assert sim_related > sim_unrelated


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 0.0, 0.0]
        assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        assert abs(_cosine_similarity(v1, v2)) < 1e-6

    def test_opposite_vectors(self):
        v1 = [1.0, 0.0]
        v2 = [-1.0, 0.0]
        assert abs(_cosine_similarity(v1, v2) - (-1.0)) < 1e-6

    def test_zero_vector(self):
        v1 = [0.0, 0.0]
        v2 = [1.0, 0.0]
        assert _cosine_similarity(v1, v2) == 0.0

    def test_symmetric(self):
        v1 = [1.0, 2.0, 3.0]
        v2 = [4.0, 5.0, 6.0]
        assert abs(_cosine_similarity(v1, v2) - _cosine_similarity(v2, v1)) < 1e-6


class TestVectorMemoryProvider:
    @pytest.fixture
    def tmp_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    @pytest.fixture
    def provider(self, tmp_dir):
        return VectorMemoryProvider(tmp_dir, collection="test")

    @pytest.mark.asyncio
    async def test_initialize_creates_data_dir(self, provider, tmp_dir):
        await provider.initialize()
        assert provider._initialized is True
        assert tmp_dir.exists()

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, provider, tmp_dir):
        await provider.initialize()
        entry = MemoryEntry(
            id="test1",
            provider="test",
            content="hello world",
            metadata={"source": "test"},
            tags=["greeting"],
        )
        result = await provider.store(entry)
        assert result == "test1"
        assert len(provider._entries) == 1
        assert provider._entries[0]["content"] == "hello world"

    @pytest.mark.asyncio
    async def test_search_returns_results(self, provider, tmp_dir):
        await provider.initialize()
        await provider.store(MemoryEntry(id="1", provider="test", content="python programming"))
        await provider.store(MemoryEntry(id="2", provider="test", content="javascript coding"))
        await provider.store(MemoryEntry(id="3", provider="test", content="cooking recipes"))

        results = await provider.search("programming", limit=2)
        assert len(results) > 0
        assert results[0].content in ["python programming", "javascript coding"]

    @pytest.mark.asyncio
    async def test_search_similarity_scores(self, provider, tmp_dir):
        await provider.initialize()
        await provider.store(MemoryEntry(id="1", provider="test", content="python programming"))
        await provider.store(MemoryEntry(id="2", provider="test", content="cooking recipes"))

        results = await provider.search("python", limit=2)
        if len(results) >= 2:
            assert results[0].metadata.get("_similarity", 0) >= results[1].metadata.get("_similarity", 0)

    @pytest.mark.asyncio
    async def test_get_recent(self, provider, tmp_dir):
        await provider.initialize()
        for i in range(5):
            await provider.store(MemoryEntry(id=f"{i}", provider="test", content=f"entry {i}"))

        recent = await provider.get_recent(limit=3)
        assert len(recent) == 3
        assert recent[0].content == "entry 4"
        assert recent[1].content == "entry 3"
        assert recent[2].content == "entry 2"

    @pytest.mark.asyncio
    async def test_persistence(self, tmp_dir):
        provider1 = VectorMemoryProvider(tmp_dir, collection="persist_test")
        await provider1.initialize()
        await provider1.store(MemoryEntry(id="1", provider="test", content="persisted entry"))
        await provider1.close()

        provider2 = VectorMemoryProvider(tmp_dir, collection="persist_test")
        await provider2.initialize()
        assert len(provider2._entries) == 1
        assert provider2._entries[0]["content"] == "persisted entry"

    @pytest.mark.asyncio
    async def test_empty_search(self, provider, tmp_dir):
        await provider.initialize()
        results = await provider.search("anything")
        assert results == []

    @pytest.mark.asyncio
    async def test_stats(self, provider, tmp_dir):
        await provider.initialize()
        await provider.store(MemoryEntry(id="1", provider="test", content="test"))
        stats = provider.get_stats()
        assert stats["total_entries"] == 1
        assert stats["collection"] == "test"
        assert stats["embedding_dim"] == 128

    @pytest.mark.asyncio
    async def test_close_persists(self, provider, tmp_dir):
        await provider.initialize()
        await provider.store(MemoryEntry(id="1", provider="test", content="data"))
        await provider.close()

        provider2 = VectorMemoryProvider(tmp_dir, collection="test")
        await provider2.initialize()
        assert len(provider2._entries) == 1

    @pytest.mark.asyncio
    async def test_corrupt_store_file_recovery(self, tmp_dir):
        store_path = tmp_dir / "vector_test.json"
        store_path.write_text("not valid json {{{", encoding="utf-8")

        provider = VectorMemoryProvider(tmp_dir, collection="test")
        await provider.initialize()
        assert provider._entries == []

    def test_get_stats_before_init(self, provider, tmp_dir):
        stats = provider.get_stats()
        assert stats["total_entries"] == 0
