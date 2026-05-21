"""Cortex auto-store during training."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class CortexAutoStore:
    def __init__(self, data_dir: str | Path = "data/cortex"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._store: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self):
        store_file = self.data_dir / "cortex_store.json"
        if store_file.exists():
            self._store = json.loads(store_file.read_text())

    def _save(self):
        store_file = self.data_dir / "cortex_store.json"
        store_file.write_text(json.dumps(self._store, indent=2))

    def auto_store(self, layer_name: str, representations: dict[str, Any], step: int):
        """Auto-store intermediate representations during training."""
        key = f"{layer_name}_step_{step}"
        self._store[key] = {
            "layer": layer_name,
            "step": step,
            "timestamp": time.time(),
            "representation_keys": list(representations.keys()),
            "representation_sizes": {k: len(v) if hasattr(v, "__len__") else 1 for k, v in representations.items()},
        }
        # Keep only last 100 entries
        if len(self._store) > 100:
            oldest = sorted(self._store.keys(), key=lambda k: self._store[k].get("timestamp", 0))[:10]
            for k in oldest:
                del self._store[k]
        self._save()

    def retrieve(self, layer_name: str, step: int) -> dict[str, Any] | None:
        key = f"{layer_name}_step_{step}"
        return self._store.get(key)

    def get_stats(self) -> dict[str, Any]:
        return {"entries": len(self._store), "layers": list(set(v.get("layer") for v in self._store.values()))}
