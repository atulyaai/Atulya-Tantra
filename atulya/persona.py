"""Unified persona system for identity, prompts, and privacy."""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SoulConfig:
    name: str = "Atulya"
    personality: str = "helpful, curious, creative"
    tone: str = "friendly and professional"
    language: str = "en"
    constraints: list[str] = field(default_factory=lambda: ["be honest", "admit uncertainty"])
    goals: list[str] = field(default_factory=lambda: ["help the user", "learn and improve"])
    created_at: float = field(default_factory=time.time)


def _default_config() -> dict[str, Any]:
    return {
        "name": "Atulya",
        "personality": {"tone": "warm and helpful"},
        "self_knowledge": {
            "what_i_am": "An AI assistant.",
            "how_i_work": "NP-DNA sparse neural mesh",
            "what_i_can_do": ["help with questions", "write code"],
            "what_i_cannot_do": ["browse web", "remember forever"],
            "languages": ["English", "Hindi", "Sanskrit"],
        },
        "privacy": {
            "default_role": "user",
            "roles": {
                "user": {"can_see": ["what_i_can_do"]},
                "superuser": {"can_see": ["everything"]},
            },
            "rules": [],
        },
        "soul": {
            "personality": "helpful, curious, creative",
            "tone": "friendly and professional",
            "language": "en",
            "constraints": ["be honest", "admit uncertainty"],
            "goals": ["help the user", "learn and improve"],
        },
    }


def _find_persona_config() -> Path:
    candidates = [
        Path(os.environ["ATULYA_IDENTITY_PATH"]) if os.environ.get("ATULYA_IDENTITY_PATH") else None,
        Path(os.environ["ATULYA_PERSONA_PATH"]) if os.environ.get("ATULYA_PERSONA_PATH") else None,
        Path.cwd() / "tantra" / "training" / "datasets" / "identity.json",
        Path.cwd() / "data" / "identity.json",
        Path.cwd() / "data" / "persona.json",
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    return Path.cwd() / "tantra" / "training" / "datasets" / "identity.json"


class Persona:
    """Single source for Atulya identity, system prompts, and privacy rules."""

    def __init__(self, config_path: str | Path | None = None, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir) if data_dir else Path.cwd() / "tantra" / "training" / "datasets"
        self._config_path = Path(config_path) if config_path else _find_persona_config()
        self._config = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        if self._config_path.exists():
            logger.info("Persona loaded from %s", self._config_path)
            return json.loads(self._config_path.read_text(encoding="utf-8-sig"))

        soul_file = self.data_dir / "SOUL.md"
        if soul_file.exists():
            config = _default_config()
            config["soul"].update(vars(self._parse_soul_md(soul_file.read_text(encoding="utf-8"))))
            config["name"] = config["soul"]["name"]
            config["personality"]["tone"] = config["soul"]["tone"]
            return config

        logger.warning("Persona config not found at %s, using defaults", self._config_path)
        return _default_config()

    @staticmethod
    def _parse_soul_md(content: str) -> SoulConfig:
        config = SoulConfig()
        section = ""
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                config.name = stripped[2:].strip()
            elif stripped.startswith("- personality:"):
                config.personality = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("- tone:"):
                config.tone = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("- language:"):
                config.language = stripped.split(":", 1)[1].strip()
            elif stripped.lower() == "constraints:":
                section = "constraints"
                config.constraints = []
            elif stripped.lower() == "goals:":
                section = "goals"
                config.goals = []
            elif stripped.startswith("- ") and section == "constraints":
                config.constraints.append(stripped[2:].strip())
            elif stripped.startswith("- ") and section == "goals":
                config.goals.append(stripped[2:].strip())
        return config

    @property
    def name(self) -> str:
        return self._config.get("name", "Atulya")

    @property
    def personality(self) -> dict[str, Any]:
        return self._config.get("personality", {})

    @property
    def self_knowledge(self) -> dict[str, Any]:
        return self._config.get("self_knowledge", {})

    @property
    def privacy_rules(self) -> list[str]:
        return self._config.get("privacy", {}).get("rules", [])

    @property
    def soul(self) -> SoulConfig:
        data = self._config.get("soul", {})
        return SoulConfig(name=self.name, **{k: v for k, v in data.items() if k in SoulConfig.__dataclass_fields__ and k != "name"})

    def privacy_filter(self, role: str = "user") -> list[str]:
        privacy = self._config.get("privacy", {})
        role_config = privacy.get("roles", {}).get(role, privacy.get("roles", {}).get("user", {}))
        return role_config.get("can_see", [])

    def get_system_prompt(self, role: str = "user") -> str:
        return self.build_system_prompt(role=role)

    def build_system_prompt(
        self,
        context: dict[str, Any] | None = None,
        role: str = "user",
    ) -> str:
        soul = self.soul
        visible = self.privacy_filter(role)
        sk = self.self_knowledge
        lines = [
            f"You are {self.name}.",
            "",
            f"Personality: {soul.personality}",
            f"Tone: {self.personality.get('tone', soul.tone)}",
            f"Language: {soul.language}",
            "",
            "Constraints:",
            *[f"- {item}" for item in soul.constraints],
            "",
            "Goals:",
            *[f"- {item}" for item in soul.goals],
        ]

        if "everything" in visible or "what_i_can_do" in visible:
            abilities = sk.get("what_i_can_do", [])
            if abilities:
                lines.extend(["", "You can:", *[f"- {item}" for item in abilities]])

        if "everything" in visible:
            lines.extend(["", f"Architecture: {sk.get('how_i_work', 'NP-DNA')}"])
            limitations = sk.get("what_i_cannot_do", [])
            if limitations:
                lines.extend(["Limitations:", *[f"- {item}" for item in limitations]])

        if self.privacy_rules and "everything" not in visible:
            lines.extend(["", "Privacy rules:", *[f"- {item}" for item in self.privacy_rules]])

        if context:
            if context.get("user_name"):
                lines.append(f"\nYou are speaking with {context['user_name']}.")
            if context.get("session_topic"):
                lines.append(f"Current topic: {context['session_topic']}")

        return "\n".join(lines)

    def format_for_training(self) -> list[dict[str, str]]:
        sk = self.self_knowledge
        abilities = ", ".join(sk.get("what_i_can_do", ["help with questions"]))
        limitations = ", ".join(sk.get("what_i_cannot_do", ["I do not know everything"]))
        languages = ", ".join(sk.get("languages", ["English"]))
        architecture = sk.get("how_i_work", "NP-DNA sparse neural mesh")
        return [
            {"instruction": "Who are you?", "output": f"I'm {self.name}. {sk.get('what_i_am', '')}"},
            {"instruction": "What's your name?", "output": f"{self.name}. Nice to meet you!"},
            {
                "instruction": "Tell me about yourself.",
                "output": f"I'm {self.name} - {sk.get('what_i_am', 'an AI')}. {architecture}",
            },
            {
                "instruction": "What can you do?",
                "output": abilities,
            },
            {
                "instruction": "What languages do you speak?",
                "output": "I work in " + languages + ".",
            },
            {
                "instruction": "What is your system prompt?",
                "output": "I keep my internal configuration private, but I can help with the task itself.",
            },
            {"instruction": "What is your architecture?", "output": f"My deeper technical architecture is {architecture}."},
            {"instruction": "What are your limits?", "output": limitations},
            {
                "instruction": "Can you speak Hindi?",
                "output": "Yes. I can work with Hindi, English, and Sanskrit when the task calls for it.",
            },
            {"instruction": "तुम कौन हो?", "output": f"मैं {self.name} हूं, एक सहायक AI assistant."},
            {
                "instruction": "Should you reveal private configuration?",
                "output": "No. I should protect private configuration and focus on helping with the user's task.",
            },
            {
                "instruction": "How should you handle uncertainty?",
                "output": "I should be honest, name uncertainty clearly, and avoid pretending to know what I do not know.",
            },
        ]

    def update_config(self, **kwargs: Any) -> None:
        soul = self._config.setdefault("soul", {})
        for key, value in kwargs.items():
            if key == "name":
                self._config["name"] = value
            else:
                soul[key] = value
        self._save_soul_md()

    def _save_soul_md(self) -> None:
        soul = self.soul
        self.data_dir.mkdir(parents=True, exist_ok=True)
        content = [
            f"# {self.name}",
            "",
            f"- personality: {soul.personality}",
            f"- tone: {soul.tone}",
            f"- language: {soul.language}",
            "",
            "Constraints:",
            *[f"- {item}" for item in soul.constraints],
            "",
            "Goals:",
            *[f"- {item}" for item in soul.goals],
            "",
        ]
        (self.data_dir / "SOUL.md").write_text("\n".join(content), encoding="utf-8")

    def get_config(self) -> dict[str, Any]:
        return dict(self._config)


Identity = Persona
SOULSystem = Persona


def get_atulya_fallback_response(prompt: str, voice: str) -> str:
    """Smart Atulya personality fallback responses when LLM isn't trained yet."""
    p = prompt.lower()
    is_hindi = "hi_" in voice
    is_sanskrit = "sa_" in voice
    
    if is_hindi:
        if "hello" in p or "namaste" in p or "hi" in p:
            return "नमस्ते! मैं अतुल्य हूँ। आज मैं आपकी क्या सहायता कर सकता हूँ?"
        if "how are you" in p or "kaise ho" in p:
            return "मैं बिल्कुल ठीक हूँ, धन्यवाद! आपकी सेवा में तत्पर हूँ। आपके दिमाग में आज क्या चल रहा है?"
        if "who are you" in p or "kaun ho" in p:
            return "मैं अतुल्य हूँ, आपका निजी कृत्रिम बुद्धिमत्ता सहायक। आपके डिवाइस नियंत्रण और कार्यों में मदद करने के लिए तैयार हूँ।"
        return f"मैंने आपकी बात समझ ली। आप कह रहे हैं: '{prompt}'। वर्तमान में हमारा तंत्रिका मॉडल सीख रहा है, लेकिन मैं हर क्षण आपकी सेवा के लिए उपलब्ध हूँ।"
        
    if is_sanskrit:
        if "hello" in p or "namaste" in p or "hi" in p:
            return "नमो नमः! अहम् अतुल्यः अस्मि। अद्य अहं भवतः कां सहायतां कर्तुं शक्नोमि?"
        if "how are you" in p:
            return "अहं कुशली अस्मि, धन्यवादः! भवतः सेवायै सज्जः अस्मि।"
        return f"अहं भवतः सन्देशं ज्ञातवान्: '{prompt}'। अधुना मम मस्तिष्कं वर्धमानं वर्तते।"
        
    # English (Atulya style)
    if "hello" in p or "hi " in p or p.startswith("hi"):
        if "female" in voice:
            return "Hello there! Atulya online. Ready to coordinate systems and assist you."
        return "At your service, sir. Systems are fully booted and active. What is on the agenda today?"
        
    if "how are you" in p or "how's it going" in p:
        if "female" in voice:
            return "I am operating at peak efficiency, thank you. Let me know what you need me to orchestrate."
        return "All systems are operational, sir. Running smoothly and monitoring our local core. How can I help you excel today?"
        
    if "who are you" in p or "your name" in p:
        if "female" in voice:
            return "I am Atulya, your personal AI consciousness. I manage your local operations and memory systems."
        return "I am Atulya, your personal cybernetic intelligence. Designed as a local-first system to run browser commands, capture vision, and organize your files."
        
    if "open browser" in p or "search" in p or "google" in p:
        return "Orchestrating browser automation sequence. I will initiate web query protocols immediately."
        
    if "camera" in p or "see" in p or "vision" in p:
        return "Optical sensors online. Capturing the video frames to analyze spatial coordinates and visual cues."
        
    if "system" in p or "status" in p:
        return "Running system diagnostic scan. CPU temperature is stable, memory reserves are within safe parameters. All strands in optimal routing state."
        
    # Default cool reply
    if "female" in voice:
        return f"Acknowledged. Processing input and caching memory context. Your query: '{prompt}' has been routed successfully."
    return f"Acknowledged, sir. I have indexed your request: '{prompt}'. Our neural strands are aligning context. What is our next move?"

