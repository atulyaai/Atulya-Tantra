"""Central configuration for Atulya Tantra."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AtulyaConfig:
    root_dir: Path
    data_dir: Path
    model_dir: Path
    logs_dir: Path
    config_path: Path | None = None

    @classmethod
    def load(
        cls,
        root_dir: str | Path | None = None,
        config_path: str | Path | None = None,
    ) -> "AtulyaConfig":
        root = Path(root_dir or os.environ.get("ATULYA_ROOT", Path.cwd())).resolve()
        path = Path(config_path or os.environ.get("ATULYA_CONFIG", root / "config.json"))
        values: dict[str, Any] = {}
        if path.exists():
            try:
                values = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                values = {}

        def resolve(name: str, default: str) -> Path:
            env_name = f"ATULYA_{name.upper()}"
            raw = os.environ.get(env_name, values.get(name, default))
            candidate = Path(raw)
            return candidate if candidate.is_absolute() else root / candidate

        return cls(
            root_dir=root,
            data_dir=resolve("data_dir", "assets"),
            model_dir=resolve("model_dir", "tantra/outputs"),
            logs_dir=resolve("logs_dir", "assets/logs"),
            config_path=path if path.exists() else None,
        )


def get_config() -> AtulyaConfig:
    return AtulyaConfig.load()
