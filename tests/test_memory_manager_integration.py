"""Tests for MemoryManager integration with VectorMemoryProvider."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from atulya.memory.manager import MemoryManager
from atulya.memory.orchestrator import MemoryEntry


class TestMemoryManagerIntegration:
    @pytest.fixture
    def tmp_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    @pytest.fixture
    def tmp_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def _auto_close(self, mgr):
        import gc
        gc.collect()

    @pytest.mark.asyncio
    async def test_manager_registers_providers(self, tmp_dir):
        mgr = MemoryManager(data_dir=tmp_dir)
        await mgr.initialize()
        assert "session_search" in mgr.providers
        assert "vector_memory" in mgr.providers
        await mgr.close()

    @pytest.mark.asyncio
    async def test_store_session_stores_in_both(self, tmp_dir):
        mgr = MemoryManager(data_dir=tmp_dir)
        await mgr.initialize()
        session_id = await mgr.store_session("test session content")
        assert session_id is not None

        session_results = await mgr.session_search.search("test session")
        assert len(session_results) > 0

        vector_results = await mgr.vector_store.search("test session")
        assert len(vector_results) > 0
        await mgr.close()

    @pytest.mark.asyncio
    async def test_semantic_search(self, tmp_dir):
        mgr = MemoryManager(data_dir=tmp_dir)
        await mgr.initialize()
        await mgr.store_session("python programming tutorial")
        await mgr.store_session("cooking recipes for dinner")

        results = await mgr.semantic_search("programming", limit=2)
        assert len(results) > 0
        assert "python" in results[0].content.lower() or "programming" in results[0].content.lower()
        await mgr.close()

    @pytest.mark.asyncio
    async def test_search_across_providers(self, tmp_dir):
        mgr = MemoryManager(data_dir=tmp_dir)
        await mgr.initialize()
        await mgr.store_session("test entry one")
        results = await mgr.search("test entry")
        assert len(results) > 0
        await mgr.close()

    @pytest.mark.asyncio
    async def test_get_context(self, tmp_dir):
        mgr = MemoryManager(data_dir=tmp_dir)
        await mgr.initialize()
        await mgr.store_session("context entry")
        context = await mgr.get_context()
        assert context.total_tokens > 0
        await mgr.close()

    @pytest.mark.asyncio
    async def test_stats(self, tmp_dir):
        mgr = MemoryManager(data_dir=tmp_dir)
        await mgr.initialize()
        await mgr.store_session("stats entry")
        stats = mgr.get_stats()
        assert "providers" in stats
        assert "session_search" in stats["providers"]
        assert "vector_memory" in stats["providers"]
        await mgr.close()

    @pytest.mark.asyncio
    async def test_close_all(self, tmp_dir):
        mgr = MemoryManager(data_dir=tmp_dir)
        await mgr.initialize()
        await mgr.store_session("close test")
        await mgr.close()

        mgr2 = MemoryManager(data_dir=tmp_dir)
        await mgr2.initialize()
        results = await mgr2.vector_store.search("close test")
        assert len(results) > 0
        await mgr2.close()

    @pytest.mark.asyncio
    async def test_empty_semantic_search(self, tmp_dir):
        mgr = MemoryManager(data_dir=tmp_dir)
        await mgr.initialize()
        results = await mgr.semantic_search("anything at all")
        assert results == []
        await mgr.close()

    @pytest.mark.asyncio
    async def test_multiple_sessions(self, tmp_dir):
        mgr = MemoryManager(data_dir=tmp_dir)
        await mgr.initialize()
        for i in range(5):
            await mgr.store_session(f"session {i} content")

        results = await mgr.semantic_search("session", limit=10)
        assert len(results) == 5
        await mgr.close()

    @pytest.mark.asyncio
    async def test_metadata_preserved(self, tmp_dir):
        mgr = MemoryManager(data_dir=tmp_dir)
        await mgr.initialize()
        await mgr.store_session("metadata test", metadata={"source": "test", "importance": "high"})
        results = await mgr.vector_store.search("metadata test")
        assert len(results) > 0
        assert results[0].metadata.get("source") == "test"
        await mgr.close()
