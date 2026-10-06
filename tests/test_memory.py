"""Tests for atulya/memory.py."""
from __future__ import annotations

import math
import tempfile
from pathlib import Path

import pytest

from atulya.memory import (
    MemoryEntry,
    MemoryManager,
    VectorMemoryProvider,
    _cosine_similarity,
    _hash_embed,
    build_memory_graph,
)


# ── test_memory_graph ────────────────────────────────────────────────────────────
def test_graph_has_a_branch_per_kind_and_a_leaf_per_source():
    view = {"user": "aj", "facts": [
        {"id": "1", "kind": "person", "key": "wife", "value": "Priya", "text": "Your wife is Priya"},
        {"id": "2", "kind": "place", "key": "home", "value": "Delhi", "text": "You live in Delhi"},
        {"id": "3", "kind": "preference", "key": "likes", "value": "cricket", "text": "You like cricket"}],
        "habits": [{"signature": "s", "label": "play lofi", "when": "around 9 pm"}]}
    g = build_memory_graph(
        view, episodes=[{"text": "what is my day", "created_at": "t"}], skills=[("play_music", "Play a song")],
        mood={"mood": "calm"}, brains=[{"name": "Groq", "seconds": 0.8}], vectors=7)
    ids = {n["id"] for n in g["nodes"]}
    assert {"root", "branch:personal", "branch:concepts", "branch:preference", "branch:episodic",
            "branch:skills", "branch:self", "branch:arch"} <= ids
    assert "branch:world" in ids                          # nothing there, but the branch is still drawn (as empty)
    assert next(n for n in g["nodes"] if n["id"] == "branch:world")["count"] == 0
    assert g["relations"] == [{"a": "aj", "rel": "wife", "b": "Priya"}]
    assert g["callouts"]["preferences"] == ["likes: cricket"] and g["callouts"]["vectors"] == 7
    assert all(e["from"] in ids and e["to"] in ids for e in g["edges"])
    # only branches with something in them can be opened by voice; the empty ones are drawn but have no list
    assert {s["id"] for s in g["sections"]} == {n["group"] for n in g["nodes"] if n["kind"] == "branch" and n["count"]}


def test_bare_profile_still_shows_the_architecture_branch():
    g = build_memory_graph({"user": "aj", "facts": [], "habits": []})
    branches = {n["group"]: n["count"] for n in g["nodes"] if n["kind"] == "branch"}
    assert branches["arch"] > 0 and branches["personal"] == 0        # the architecture always has modules; nothing is known yet
    leaves = [n for n in g["nodes"] if n["kind"] == "leaf"]
    assert g["relations"] == [] and g["total"] == len(leaves) and sum(branches.values()) == len(leaves)


def test_route_requires_login():
    from fastapi.testclient import TestClient

    from atulya.server import app

    assert TestClient(app).get("/api/memory/graph").status_code in (401, 403)


def test_mood_route_requires_login_and_reports_values(monkeypatch):
    from fastapi.testclient import TestClient

    from atulya.server import app

    client = TestClient(app)
    assert client.get("/api/mood").status_code in (401, 403)
    from atulya.api import ADMIN_TOKEN as token
    body = client.get("/api/mood", headers={"X-Atulya-Token": token}).json()
    assert set(body) == {"label", "valence", "energy"} and -1 <= body["valence"] <= 1


# ── test_memory_manager_integration ────────────────────────────────────────────────────────────
class TestMemoryManagerIntegration:
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
    async def test_semantic_search_can_be_limited_to_one_user_scope(self, tmp_dir):
        mgr = MemoryManager(data_dir=tmp_dir)
        await mgr.initialize()
        await mgr.store_session("I prefer short answers", metadata={"scope": "alice"})
        await mgr.store_session("I prefer detailed answers", metadata={"scope": "bob"})

        alice = await mgr.semantic_search("prefer answers", limit=10, scope="alice")
        bob = await mgr.semantic_search("prefer answers", limit=10, scope="bob")
        assert [entry.content for entry in alice] == ["I prefer short answers"]
        assert [entry.content for entry in bob] == ["I prefer detailed answers"]
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


# ── test_vector_store ────────────────────────────────────────────────────────────
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
    async def test_corrupt_store_is_preserved_before_fresh_start(self, provider, tmp_dir, caplog):
        corrupt = b'{"entries": [broken'
        provider._store_path.write_bytes(corrupt)

        with caplog.at_level("ERROR", logger="atulya.memory"):
            await provider.initialize()

        backups = list(tmp_dir.glob("vector_test.json.corrupt-*"))
        assert len(backups) == 1
        assert backups[0].read_bytes() == corrupt
        assert provider._store_path.read_bytes() == corrupt
        assert provider._entries == [] and provider._embeddings == []
        assert "Vector memory is corrupt" in caplog.text

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

