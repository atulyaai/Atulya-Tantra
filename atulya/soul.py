"""SOUL.md personality system — wired into agent pipeline."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SoulConfig:
    name: str = "Atulya"
    personality: str = "helpful, curious, creative"
    tone: str = "friendly and professional"
    language: str = "en"
    constraints: list[str] = field(default_factory=lambda: ["be honest", "admit uncertainty"])
    goals: list[str] = field(default_factory=lambda: ["help the user", "learn and improve"])
    created_at: float = field(default_factory=time.time)


class SOULSystem:
    def __init__(self, data_dir: str | Path = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._config: SoulConfig | None = None
        self._load()

    def _load(self):
        soul_file = self.data_dir / "SOUL.md"
        if soul_file.exists():
            content = soul_file.read_text()
            self._config = self._parse_soul_md(content)
        else:
            self._config = SoulConfig()

    def _parse_soul_md(self, content: str) -> SoulConfig:
        config = SoulConfig()
        for line in content.split("\n"):
            if line.startswith("# "):
                config.name = line[2:].strip()
            elif line.startswith("- personality:"):
                config.personality = line.split(":", 1)[1].strip()
            elif line.startswith("- tone:"):
                config.tone = line.split(":", 1)[1].strip()
        return config

    def build_system_prompt(self, context: dict[str, Any] | None = None) -> str:
        """Build system prompt with SOUL personality — wired into agent pipeline."""
        config = self._config or SoulConfig()
        prompt = f"""You are {config.name}.

Personality: {config.personality}
Tone: {config.tone}
Language: {config.language}

Constraints:
"""
        for c in config.constraints:
            prompt += f"- {c}\n"

        prompt += "\nGoals:\n"
        for g in config.goals:
            prompt += f"- {g}\n"

        if context:
            if context.get("user_name"):
                prompt += f"\nYou are speaking with {context['user_name']}.\n"
            if context.get("session_topic"):
                prompt += f"Current topic: {context['session_topic']}\n"

        return prompt

    def update_config(self, **kwargs: Any):
        if self._config:
            for key, value in kwargs.items():
                if hasattr(self._config, key):
                    setattr(self._config, key, value)
            self._save()

    def _save(self):
        if self._config:
            soul_file = self.data_dir / "SOUL.md"
            content = f"""# {self._config.name}

- personality: {self._config.personality}
- tone: {self._config.tone}
- language: {self._config.language}

Constraints:
"""
            for c in self._config.constraints:
                content += f"- {c}\n"
            content += "\nGoals:\n"
            for g in self._config.goals:
                content += f"- {g}\n"
            soul_file.write_text(content)

    def get_config(self) -> dict[str, Any]:
        if self._config:
            return vars(self._config)
        return {}
