"""Tests for CortexAutoStore — intermediate representation storage during training."""

import os
import tempfile


class TestCortexAutoStore:
    """Tests for CortexAutoStore — auto-store and retrieve intermediate representations."""

    def test_auto_store_and_retrieve(self):
        from tantra.core.npdna.cortex_autostore import CortexAutoStore
        with tempfile.TemporaryDirectory() as tmp:
            store = CortexAutoStore(data_dir=tmp)
            store.auto_store("layer_1", {"attention": [0.1, 0.2], "output": [0.5]}, step=10)
            result = store.retrieve("layer_1", step=10)
            assert result is not None
            assert result["layer"] == "layer_1"
            assert result["step"] == 10
            assert "attention" in result["representation_keys"]

    def test_retrieve_nonexistent(self):
        from tantra.core.npdna.cortex_autostore import CortexAutoStore
        with tempfile.TemporaryDirectory() as tmp:
            store = CortexAutoStore(data_dir=tmp)
            assert store.retrieve("layer_x", 999) is None

    def test_get_stats_empty(self):
        from tantra.core.npdna.cortex_autostore import CortexAutoStore
        with tempfile.TemporaryDirectory() as tmp:
            store = CortexAutoStore(data_dir=tmp)
            stats = store.get_stats()
            assert stats["entries"] == 0
            assert stats["layers"] == []

    def test_get_stats_after_store(self):
        from tantra.core.npdna.cortex_autostore import CortexAutoStore
        with tempfile.TemporaryDirectory() as tmp:
            store = CortexAutoStore(data_dir=tmp)
            store.auto_store("layer_1", {"data": [1.0]}, step=1)
            store.auto_store("layer_2", {"data": [2.0]}, step=2)
            stats = store.get_stats()
            assert stats["entries"] == 2
            assert "layer_1" in stats["layers"]
            assert "layer_2" in stats["layers"]

    def test_max_entries_capped(self):
        from tantra.core.npdna.cortex_autostore import CortexAutoStore
        with tempfile.TemporaryDirectory() as tmp:
            store = CortexAutoStore(data_dir=tmp)
            for i in range(110):
                store.auto_store(f"layer_{i % 5}", {"v": [float(i)]}, step=i)
            stats = store.get_stats()
            assert stats["entries"] <= 100

    def test_persistence(self):
        from tantra.core.npdna.cortex_autostore import CortexAutoStore
        with tempfile.TemporaryDirectory() as tmp:
            s1 = CortexAutoStore(data_dir=tmp)
            s1.auto_store("layer_1", {"a": [1.0]}, step=5)
            s2 = CortexAutoStore(data_dir=tmp)
            result = s2.retrieve("layer_1", step=5)
            assert result is not None
            assert result["step"] == 5
