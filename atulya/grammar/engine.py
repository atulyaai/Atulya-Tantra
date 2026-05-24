"""Grammar & Language Quality — trilingual fluency, human not robotic."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LanguageRule:
    name: str
    language: str
    pattern: str
    replacement: str
    description: str = ""
    enabled: bool = True


@dataclass
class GrammarCheck:
    text: str
    language: str
    issues: list[dict[str, Any]] = field(default_factory=list)
    score: float = 1.0
    suggestions: list[str] = field(default_factory=list)


class GrammarEngine:
    """Grammar and language quality for Hindi, English, Sanskrit."""

    def __init__(self, data_dir: str | Path = "data/grammar"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._rules: list[LanguageRule] = []
        self._load_rules()

    def _load_rules(self):
        rules_file = self.data_dir / "grammar_rules.json"
        if rules_file.exists():
            data = json.loads(rules_file.read_text())
            for r in data.get("rules", []):
                self._rules.append(LanguageRule(**r))
        else:
            self._load_default_rules()
            self._save_rules()

    def _load_default_rules(self):
        """Default grammar rules for trilingual support."""
        self._rules = [
            # English rules
            LanguageRule("en_double_space", "en", r"  +", " ", "Remove double spaces"),
            LanguageRule("en_capital_i", "en", r"\bi\b", "I", "Capitalize pronoun I"),
            LanguageRule("en_period_space", "en", r"\.(?=[^\s.])", ". ", "Ensure space after period — not at line end"),
            LanguageRule("en_comma_space", "en", r",\s*", ", ", "Ensure space after comma"),
            LanguageRule("en_apostrophe", "en", r"(\w)'(\w)", r"\1'\2", "Fix apostrophe spacing"),
            # Hindi rules (Devanagari)
            LanguageRule("hi_half_consonant", "hi", r"([\u0900-\u097F])\s+([\u0900-\u097F])", r"\1\2", "Join half consonants"),
            LanguageRule("hi_vowel_sign", "hi", r"([\u0905-\u0914])\s+([\u093E-\u094F])", r"\1\2", "Join vowel signs"),
            # Sanskrit rules
            LanguageRule("sa_sandhi", "sa", r"([\u0900-\u097F])\s+([\u0900-\u097F])", r"\1\2", "Apply sandhi rules"),
            LanguageRule("sa_virama", "sa", r"([\u0900-\u097F])\s+([\u094D])", r"\1\2", "Apply virama"),
        ]

    def _save_rules(self):
        rules_file = self.data_dir / "grammar_rules.json"
        data = {"rules": [vars(r) for r in self._rules]}
        rules_file.write_text(json.dumps(data, indent=2))

    def check(self, text: str, language: str = "en") -> GrammarCheck:
        """Check grammar and return issues."""
        issues = []
        suggestions = []
        score = 1.0

        for rule in self._rules:
            if rule.language != language or not rule.enabled:
                continue
            matches = list(re.finditer(rule.pattern, text))
            if matches:
                for match in matches:
                    issues.append({
                        "rule": rule.name, "description": rule.description,
                        "position": match.start(), "text": match.group(),
                    })
                    suggestions.append(re.sub(rule.pattern, rule.replacement, match.group()))
                score -= 0.05 * len(matches)

        score = max(0.0, min(1.0, score))
        return GrammarCheck(text=text, language=language, issues=issues, score=score, suggestions=suggestions)

    def fix(self, text: str, language: str = "en") -> str:
        """Fix grammar issues."""
        result = text
        for rule in self._rules:
            if rule.language != language or not rule.enabled:
                continue
            result = re.sub(rule.pattern, rule.replacement, result)
        return result

    def add_rule(self, name: str, language: str, pattern: str, replacement: str, description: str = ""):
        rule = LanguageRule(name=name, language=language, pattern=pattern, replacement=replacement, description=description)
        self._rules.append(rule)
        self._save_rules()

    def get_stats(self) -> dict[str, Any]:
        return {"total_rules": len(self._rules), "languages": list(set(r.language for r in self._rules))}


class FluencyEnhancer:
    """Enhance text fluency for natural human-like output."""

    FILLERS_EN = ["well", "you know", "I mean", "actually", "basically"]
    FILLERS_HI = ["तो", "अच्छा", "देखिए", "सच कहूं तो", "मतलब"]
    FILLERS_SA = ["तथा", "अथवा", "वास्तविकतया", "निश्चित रूप से"]

    def enhance(self, text: str, language: str = "en", naturalness: float = 0.5) -> str:
        """Make text more natural and human-like."""
        if naturalness <= 0:
            return text

        # Add natural transitions
        transitions = {
            "en": ["Additionally", "Furthermore", "On the other hand", "In fact", "Moreover"],
            "hi": ["इसके अलावा", "दूसरी ओर", "वास्तव में", "इसके साथ ही"],
            "sa": ["अपि च", "अन्यथा", "वास्तवतः", "तथापि"],
        }

        sentences = re.split(r'(?<=[.!?])\s+', text)
        if len(sentences) < 2:
            return text

        enhanced = [sentences[0]]
        trans_list = transitions.get(language, transitions["en"])
        for i, sentence in enumerate(sentences[1:], 1):
            if i % 3 == 0 and naturalness > 0.3:
                import random
                transition = random.choice(trans_list)
                enhanced.append(f"{transition}, {sentence}")
            else:
                enhanced.append(sentence)

        return " ".join(enhanced)

    def humanize(self, text: str, language: str = "en") -> str:
        """Make text sound more conversational."""
        # Replace formal phrases with conversational ones
        replacements = {
            "en": {
                "I would like to inform you that": "Just so you know",
                "It is important to note that": "Also worth noting",
                "In conclusion": "So basically",
                "Furthermore": "Plus",
                "However": "But",
                "Therefore": "So",
            },
            "hi": {
                "यह ध्यान देने योग्य है": "यह भी देखो",
                "निष्कर्षतः": "तो basically",
                "इसके अतिरिक्त": "और भी",
            },
        }
        result = text
        for formal, casual in replacements.get(language, {}).items():
            result = result.replace(formal, casual)
        return result
