"""Compatibility wrapper for the unified persona system."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .persona import Persona, SoulConfig


class SOULSystem(Persona):
    def __init__(self, data_dir: str | Path = "assets"):
        data_path = Path(data_dir)
        super().__init__(config_path=data_path / "persona.json", data_dir=data_path)

    def build_system_prompt(self, context: dict[str, Any] | None = None) -> str:
        return super().build_system_prompt(context=context)

    def get_config(self) -> dict[str, Any]:
        return vars(self.soul)

__all__ = ["Persona", "SOULSystem", "SoulConfig"]
