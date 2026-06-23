"""Self-improvement system with Hermes-style closed learning loop
— auto-detects patterns, generates skills, measures speedup."""
from __future__ import annotations

import json
import math
import re
import time
from collections import Counter, defaultdict
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
    usage_count: int = 0
    avg_duration_saved: float = 0.0


@dataclass
class Achievement:
    name: str
    description: str
    unlocked_at: float = field(default_factory=time.time)
    category: str = "general"


@dataclass
class PatternSignature:
    tokens: tuple[str, ...]
    frequency: int = 1
    avg_tokens_saved: int = 0
    skill_name: str = ""
    last_seen: float = field(default_factory=time.time)


class UnifiedSelfImprovement:
    """Track skills, chakras, achievements, and auto-learn patterns."""

    def __init__(self, data_dir: str | Path, learning_window: int = 100):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chakras: dict[str, ChakraState] = {}
        self.skills: dict[str, Skill] = {}
        self.achievements: list[Achievement] = []
        self.learning_log: list[dict[str, Any]] = []
        self.doctor_reports: list[dict[str, Any]] = []
        self._task_history: list[dict[str, Any]] = []
        self._patterns: dict[str, PatternSignature] = {}
        self._learning_window = learning_window
        self._load()

    def _load(self):
        sf = self.data_dir / "selfimprovement.json"
        if sf.exists():
            data = json.loads(sf.read_text())
            for n, c in data.get("chakras", {}).items():
                self.chakras[n] = ChakraState(**c)
            for n, s in data.get("skills", {}).items():
                self.skills[n] = Skill(**s)
            self.achievements = [Achievement(**a) for a in data.get("achievements", [])]
            self.learning_log = data.get("learning_log", [])
            self.doctor_reports = data.get("doctor_reports", [])
            self._task_history = data.get("task_history", [])
            self._patterns = {k: PatternSignature(**v) for k, v in data.get("patterns", {}).items()}

    def _save(self):
        sf = self.data_dir / "selfimprovement.json"
        sf.write_text(json.dumps({
            "chakras": {n: vars(c) for n, c in self.chakras.items()},
            "skills": {n: vars(s) for n, s in self.skills.items()},
            "achievements": [vars(a) for a in self.achievements],
            "learning_log": self.learning_log[-500:],
            "doctor_reports": self.doctor_reports,
            "task_history": self._task_history[-1000:],
            "patterns": {k: vars(v) for k, v in self._patterns.items()},
        }, indent=2))

    # ── chakras ──────────────────────────────────────────────

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

    # ── skills ───────────────────────────────────────────────

    def add_skill(self, name: str, category: str = "general") -> Skill:
        if name not in self.skills:
            self.skills[name] = Skill(name=name, category=category)
            self._save()
        return self.skills[name]

    def practice_skill(self, name: str, duration: float = 1.0, tokens_saved: int = 0):
        skill = self.skills.get(name)
        if skill:
            skill.level = min(10.0, skill.level + duration * 0.1)
            skill.last_practiced = time.time()
            skill.usage_count += 1
            n = skill.usage_count
            skill.avg_duration_saved = (skill.avg_duration_saved * (n - 1) + tokens_saved) / n
            self._save()

    def find_or_create_skill(self, task_description: str) -> Skill | None:
        """Match a task to existing skills or create a new one."""
        tokens = set(self._tokenize(task_description))
        best_match = None
        best_score = 0.0
        for name, skill in self.skills.items():
            skill_tokens = set(self._tokenize(name.replace("_", " ")))
            overlap = tokens & skill_tokens
            if overlap:
                score = len(overlap) / max(len(tokens | skill_tokens), 1)
                if score > best_score and score >= 0.25:
                    best_score = score
                    best_match = skill
        return best_match

    # ── pattern detection (closed learning loop) ─────────────

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def _compute_fingerprint(self, task: dict[str, Any]) -> str:
        """Compute a reproducible fingerprint for a task."""
        tokens = self._tokenize(task.get("prompt", "") + " " + task.get("response", ""))
        # Use most significant tokens as fingerprint
        sig_tokens = tuple(sorted(set(tokens))[:5])
        return ":".join(sig_tokens) if sig_tokens else "empty"

    def record_task(self, prompt: str, response: str, duration: float, provider: str = "", success: bool = True):
        """Record a task into the learning loop for pattern detection."""
        record = {
            "prompt": prompt,
            "response": response[:500],
            "duration": duration,
            "provider": provider,
            "success": success,
            "timestamp": time.time(),
        }
        self._task_history.append(record)
        self._detect_patterns(record)
        self._save()

    def _detect_patterns(self, record: dict[str, Any]):
        """Scan for repeated patterns in task history."""
        fingerprint = self._compute_fingerprint(record)
        if fingerprint and fingerprint != "empty":
            if fingerprint in self._patterns:
                self._patterns[fingerprint].frequency += 1
                self._patterns[fingerprint].last_seen = time.time()
            else:
                self._patterns[fingerprint] = PatternSignature(
                    tokens=tuple(self._tokenize(record.get("prompt", ""))[:10]),
                )

            # If a pattern repeats >= 3 times, auto-generate skill
            pat = self._patterns[fingerprint]
            if pat.frequency >= 3 and not pat.skill_name:
                tokens = sorted(set(pat.tokens), key=len, reverse=True)[:3]
                skill_name = "_".join(tokens) if tokens else f"skill_{fingerprint[:8]}"
                skill = self.add_skill(skill_name, category="auto_learned")
                pat.skill_name = skill_name
                self.log_learning("pattern_detected",
                    f"Auto-created skill '{skill_name}' from {pat.frequency} repeated tasks")
                self.unlock_achievement(f"Auto-Learner: {skill_name}",
                    f"Learned {skill_name} from repeated patterns")

    def get_learning_speedup(self) -> dict[str, Any]:
        """Measure how much faster tasks become after learning."""
        if len(self._task_history) < 4:
            return {"speedup": 0.0, "message": "Not enough data"}
        half = len(self._task_history) // 2
        first_half_avg = sum(t["duration"] for t in self._task_history[:half]) / max(half, 1)
        second_half_avg = sum(t["duration"] for t in self._task_history[half:]) / max(len(self._task_history) - half, 1)
        speedup = ((first_half_avg - second_half_avg) / max(first_half_avg, 0.001)) * 100
        return {
            "speedup_percent": round(speedup, 1),
            "first_half_avg": round(first_half_avg, 2),
            "second_half_avg": round(second_half_avg, 2),
            "tasks_analyzed": len(self._task_history),
            "patterns_detected": len(self._patterns),
            "auto_skills_created": sum(1 for s in self.skills.values() if s.category == "auto_learned"),
        }

    # ── achievements ─────────────────────────────────────────

    def unlock_achievement(self, name: str, description: str, category: str = "general"):
        if not any(a.name == name for a in self.achievements):
            self.achievements.append(Achievement(name=name, description=description, category=category))
            self._save()

    # ── learning log ─────────────────────────────────────────

    def log_learning(self, topic: str, insight: str):
        self.learning_log.append({
            "topic": topic, "insight": insight, "timestamp": time.time(),
        })
        self._save()

    # ── doctor / health checks ───────────────────────────────

    def run_doctor(self) -> dict[str, Any]:
        report = {
            "timestamp": time.time(),
            "chakras": {n: {"level": c.level, "experience": c.experience}
                        for n, c in self.chakras.items()},
            "skills_count": len(self.skills),
            "auto_skills_count": sum(1 for s in self.skills.values() if s.category == "auto_learned"),
            "achievements_count": len(self.achievements),
            "learning_speedup": self.get_learning_speedup(),
            "recommendations": [],
        }
        for name, chakra in self.chakras.items():
            if chakra.level < 3:
                report["recommendations"].append(f"Focus on {name} chakra (level {chakra.level})")
        sp = report["learning_speedup"].get("speedup_percent", 0)
        if sp < 10 and report["skills_count"] > 0:
            report["recommendations"].append("Practice auto-learned skills more to see speedup")
        self.doctor_reports.append(report)
        self._save()
        return report

    def ingest_agent_output(self, agent_name: str, output_text: str) -> dict[str, Any]:
        """Bridge: ingest agent cron output, log insights, detect patterns."""
        pattern = r"(?i)(critical|high|medium|low|info):\s*(.+)"
        findings = re.findall(pattern, output_text)
        for severity, finding in findings:
            score = {"critical": 10, "high": 5, "medium": 3, "low": 1, "info": 0.5}.get(severity.lower(), 1)
            chakra_map = {
                "code": "code_quality", "dataset": "data_wisdom",
                "agent": "orchestration", "service": "system_operation",
                "test": "evaluation", "train": "training",
                "data": "data_wisdom", "research": "research",
            }
            chakra = next((v for k, v in chakra_map.items() if k in agent_name.lower()), "general")
            self.add_chakra(chakra)
            self.gain_experience(chakra, score)
            self.log_learning(agent_name, finding)
        return {"findings": len(findings), "agent": agent_name}

    def get_stats(self) -> dict[str, Any]:
        return {
            "chakras": len(self.chakras),
            "skills": len(self.skills),
            "auto_skills": sum(1 for s in self.skills.values() if s.category == "auto_learned"),
            "achievements": len(self.achievements),
            "learning_entries": len(self.learning_log),
            "patterns_detected": len(self._patterns),
            "tasks_recorded": len(self._task_history),
            "doctor_reports": len(self.doctor_reports),
            "learning_speedup": self.get_learning_speedup(),
        }

    def generate_skill_file(self, skill_name: str) -> str:
        """Generate a SKILL.md file for a learned skill."""
        skill = self.skills.get(skill_name)
        if not skill:
            return ""
        related_tasks = [t for t in self._task_history
                        if skill_name.replace("_", " ") in t.get("prompt", "").lower()]
        content = [
            f"# Skill: {skill_name}",
            f"",
            f"- **Category:** {skill.category}",
            f"- **Level:** {skill.level:.1f}/10.0",
            f"- **Usage count:** {skill.usage_count}",
            f"- **Avg duration saved:** {skill.avg_duration_saved:.1f}s",
            f"",
            f"## Example tasks",
        ]
        for t in related_tasks[-5:]:
            content.append(f"- {t.get('prompt', '')[:100]}")
        content.append("")
        content.append("## Instructions")
        content.append(f"1. When asked about {skill_name.replace('_', ' ')}, use this skill")
        content.append(f"2. Follow the learned pattern from previous successful executions")
        content.append(f"3. Adapt the approach as needed for the specific context")

        return "\n".join(content)
