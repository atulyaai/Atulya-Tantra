"""Unified self-improvement system."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ChakraState:
    name: str
    level: int = 0
    max_level: int = 10
    experience: float = 0.0
    last_updated: float = field(default_factory=time.time)


@dataclass
class Skill:
    name: str
    level: float = 0.0
    category: str = "general"
    last_practiced: float = field(default_factory=time.time)


@dataclass
class Achievement:
    name: str
    description: str
    unlocked_at: float = field(default_factory=time.time)
    category: str = "general"


class UnifiedSelfImprovement:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chakras: dict[str, ChakraState] = {}
        self.skills: dict[str, Skill] = {}
        self.achievements: list[Achievement] = []
        self.learning_log: list[dict[str, Any]] = []
        self.doctor_reports: list[dict[str, Any]] = []
        self._load()

    def _load(self):
        state_file = self.data_dir / "selfimprovement.json"
        if state_file.exists():
            data = json.loads(state_file.read_text())
            for name, c in data.get("chakras", {}).items():
                self.chakras[name] = ChakraState(**c)
            for name, s in data.get("skills", {}).items():
                self.skills[name] = Skill(**s)
            self.achievements = [Achievement(**a) for a in data.get("achievements", [])]
            self.learning_log = data.get("learning_log", [])
            self.doctor_reports = data.get("doctor_reports", [])

    def _save(self):
        state_file = self.data_dir / "selfimprovement.json"
        data = {
            "chakras": {n: vars(c) for n, c in self.chakras.items()},
            "skills": {n: vars(s) for n, s in self.skills.items()},
            "achievements": [vars(a) for a in self.achievements],
            "learning_log": self.learning_log,
            "doctor_reports": self.doctor_reports,
        }
        state_file.write_text(json.dumps(data, indent=2))

    def add_chakra(self, name: str):
        if name not in self.chakras:
            self.chakras[name] = ChakraState(name=name)
            self._save()

    def gain_experience(self, chakra_name: str, amount: float):
        chakra = self.chakras.get(chakra_name)
        if chakra:
            chakra.experience += amount
            needed = (chakra.level + 1) * 100
            if chakra.experience >= needed and chakra.level < chakra.max_level:
                chakra.level += 1
                chakra.experience -= needed
            chakra.last_updated = time.time()
            self._save()

    def add_skill(self, name: str, category: str = "general"):
        if name not in self.skills:
            self.skills[name] = Skill(name=name, category=category)
            self._save()

    def practice_skill(self, name: str, duration: float = 1.0):
        skill = self.skills.get(name)
        if skill:
            skill.level = min(10.0, skill.level + duration * 0.1)
            skill.last_practiced = time.time()
            self._save()

    def unlock_achievement(self, name: str, description: str, category: str = "general"):
        if not any(a.name == name for a in self.achievements):
            self.achievements.append(Achievement(name=name, description=description, category=category))
            self._save()

    def log_learning(self, topic: str, insight: str):
        self.learning_log.append({
            "topic": topic, "insight": insight, "timestamp": time.time(),
        })
        self._save()

    def run_doctor(self) -> dict[str, Any]:
        report = {
            "timestamp": time.time(),
            "chakras": {n: {"level": c.level, "experience": c.experience} for n, c in self.chakras.items()},
            "skills_count": len(self.skills),
            "achievements_count": len(self.achievements),
            "recommendations": [],
        }
        for name, chakra in self.chakras.items():
            if chakra.level < 3:
                report["recommendations"].append(f"Focus on {name} chakra (level {chakra.level})")
        self.doctor_reports.append(report)
        self._save()
        return report

    def get_stats(self) -> dict[str, Any]:
        return {
            "chakras": len(self.chakras),
            "skills": len(self.skills),
            "achievements": len(self.achievements),
            "learning_entries": len(self.learning_log),
            "doctor_reports": len(self.doctor_reports),
        }
