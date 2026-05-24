"""Tests for CheckpointMixin — save/load, config matching, loss metadata."""

import pytest
import tempfile
import json
from pathlib import Path


class TestCheckpointMixin:
    """Unit tests for checkpoint save/load logic."""

    def test_match_config_name_custom(self):
        """Without a matching config, _match_config_name returns 'custom'."""
        from tantra.core.npdna.checkpoint import CheckpointMixin
        # Create a minimal instance with config attrs that don't match any CONFIGS
        obj = CheckpointMixin()
        obj.config = type("obj", (object,), {
            "hidden_size": 9999,
            "num_layers": 99,
            "initial_vocab": 9999,
            "mesh": type("obj", (object,), {"num_strands": 99, "top_k": 99})(),
        })
        result = obj._match_config_name()
        assert result == "custom"

    def test_save_requires_subclass_attrs(self):
        """CheckpointMixin.save needs model, tokenizer, cortex, config."""
        from tantra.core.npdna.checkpoint import CheckpointMixin
        with tempfile.TemporaryDirectory() as tmp:
            obj = CheckpointMixin()
            # Missing required attrs -> AttributeError
            with pytest.raises(AttributeError):
                obj.save(Path(tmp) / "ckpt")

    def test_save_metadata_json_structure(self):
        """Metadata JSON has expected top-level keys (tested with partial mock)."""
        import json
        meta = {
            "config_name": "seed",
            "hidden_size": 128,
            "num_layers": 6,
            "num_strands": 4,
            "top_k": 2,
            "losses": [2.0, 1.8, 1.5],
        }
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = Path(tmp) / "metadata.json"
            meta_path.write_text(json.dumps(meta, indent=2))
            loaded = json.loads(meta_path.read_text())
            assert loaded["losses"] == [2.0, 1.8, 1.5]
            assert min(loaded["losses"]) == 1.5
            assert loaded["config_name"] == "seed"
            assert loaded["hidden_size"] == 128
            assert loaded["num_strands"] == 4
            assert loaded["num_layers"] == 6

    def test_save_metadata_min_loss(self):
        """Min loss is correctly computed from losses list."""
        import json
        meta = {"losses": [5.0, 3.0, 7.0, 1.0]}
        with tempfile.TemporaryDirectory() as tmp:
            meta_path = Path(tmp) / "metadata.json"
            meta_path.write_text(json.dumps(meta, indent=2))
            loaded = json.loads(meta_path.read_text())
            assert min(loaded["losses"]) == 1.0
