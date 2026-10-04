"""Emotion & mood layer for Atulya's human-feeling responses.

Two lightweight, model-free pieces:

* ``detect_emotion(text)`` — a fast lexical/heuristic read of the *user's*
  emotional state from their message. No extra ML model; the local brain can
  refine this later, but this gives an instant, dependency-free signal.
* ``MoodState`` — Atulya's own rolling mood, persisted to disk, nudged by the
  emotions it perceives. This is what makes replies feel continuous instead of
  stateless.

Both feed :func:`build_emotional_directive`, which returns a short block that is
appended to the system prompt so the model shapes tone accordingly, and
:func:`emotion_to_tts` which maps a mood onto speaking-rate/voice hints.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Core emotions we track. Kept small on purpose — enough to shape tone,
# not a research-grade taxonomy.
EMOTIONS = ("happy", "sad", "angry", "anxious", "tired", "excited", "neutral")

# Keyword cues. Ordered by rough specificity; first strong hit wins ties.
_CUES: dict[str, tuple[str, ...]] = {
    "angry": ("angry", "furious", "pissed", "annoyed", "frustrated", "hate", "stupid", "wtf", "ridiculous"),
    "sad": ("sad", "depressed", "unhappy", "miserable", "lonely", "crying", "hurt", "disappointed", "down"),
    "anxious": ("anxious", "worried", "scared", "nervous", "stressed", "panic", "afraid", "overwhelmed"),
    "tired": ("tired", "exhausted", "sleepy", "drained", "burnt out", "burned out", "no energy", "worn out"),
    "excited": ("excited", "can't wait", "cant wait", "amazing", "awesome", "thrilled", "pumped", "let's go", "lets go"),
    "happy": ("happy", "glad", "great", "good", "love", "wonderful", "fantastic", "nice", "thank"),
}

# Simple emoji / punctuation amplifiers.
_POSITIVE_MARKS = ("!", ":)", ":D", "😀", "😄", "🎉", "❤", "🙏")
_NEGATIVE_MARKS = (":(", "😔", "😢", "😭", "😡", "💔")


@dataclass
class EmotionReading:
    """Perceived emotional state of a single user message."""

    label: str = "neutral"
    intensity: float = 0.0  # 0.0 – 1.0
    scores: dict[str, float] = field(default_factory=dict)

    @property
    def is_negative(self) -> bool:
        return self.label in ("sad", "angry", "anxious", "tired")


def detect_emotion(text: str) -> EmotionReading:
    """Heuristic, dependency-free emotion read of a user message.

    Returns a :class:`EmotionReading`. This is deliberately conservative: when
    no cue fires it returns ``neutral`` with zero intensity so callers can
    decide whether to bother adjusting tone.
    """
    if not text or not text.strip():
        return EmotionReading()

    lowered = text.lower()
    scores: dict[str, float] = {}
    for emotion, cues in _CUES.items():
        hits = sum(1 for cue in cues if cue in lowered)
        if hits:
            scores[emotion] = float(hits)

    # Punctuation / emoji nudges.
    pos_marks = sum(lowered.count(m) for m in _POSITIVE_MARKS)
    neg_marks = sum(text.count(m) for m in _NEGATIVE_MARKS)
    if pos_marks:
        scores["happy"] = scores.get("happy", 0.0) + 0.5 * pos_marks
    if neg_marks:
        scores["sad"] = scores.get("sad", 0.0) + 0.5 * neg_marks

    if not scores:
        return EmotionReading(scores={})

    label = max(scores, key=scores.get)
    raw = scores[label]
    # Normalise to 0..1 with diminishing returns; 3+ cues ~= full intensity.
    intensity = min(1.0, raw / 3.0)
    return EmotionReading(label=label, intensity=round(intensity, 3), scores=scores)


@dataclass
class MoodState:
    """Atulya's own persisted mood.

    ``valence`` runs -1 (low) .. +1 (upbeat); ``energy`` runs 0 (calm) .. 1
    (animated). A named ``label`` is derived for prompt/TTS convenience.
    """

    valence: float = 0.2
    energy: float = 0.5
    label: str = "content"
    updated_at: float = field(default_factory=time.time)

    # --- persistence -----------------------------------------------------
    @classmethod
    def load(cls, path: str | Path = "kosh/state/mood.json") -> "MoodState":
        p = Path(path)
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return cls(**{k: data[k] for k in ("valence", "energy", "label", "updated_at") if k in data})
            except Exception:
                pass
        return cls()

    def save(self, path: str | Path = "kosh/state/mood.json") -> None:
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            # Mood is best-effort; never break a reply over failing to persist.
            pass

    # --- update ----------------------------------------------------------
    def nudge(self, reading: EmotionReading, empathy: float = 0.3) -> "MoodState":
        """Shift mood gently toward an empathetic response to the user.

        Atulya doesn't mirror the user 1:1 — it leans supportive: when the user
        is down, Atulya becomes warmer and calmer (lower energy, steady
        valence) rather than also "sad"; when the user is up, it brightens.
        """
        if reading.label == "neutral" or reading.intensity == 0:
            # Drift slowly back toward baseline calm-positive.
            self.valence += (0.2 - self.valence) * 0.1
            self.energy += (0.5 - self.energy) * 0.1
        else:
            target_valence, target_energy = _EMPATHY_TARGETS.get(reading.label, (0.2, 0.5))
            weight = empathy * reading.intensity
            self.valence += (target_valence - self.valence) * weight
            self.energy += (target_energy - self.energy) * weight

        self.valence = max(-1.0, min(1.0, round(self.valence, 3)))
        self.energy = max(0.0, min(1.0, round(self.energy, 3)))
        self.label = _derive_label(self.valence, self.energy)
        self.updated_at = time.time()
        return self


# Where Atulya's mood should head when it perceives each user emotion.
# (valence, energy) — supportive, not mirroring.
_EMPATHY_TARGETS: dict[str, tuple[float, float]] = {
    "sad": (0.15, 0.3),       # warm, calm, present
    "angry": (0.1, 0.35),     # steady, de-escalating
    "anxious": (0.25, 0.3),   # reassuring, grounded
    "tired": (0.2, 0.25),     # gentle, low-key
    "happy": (0.6, 0.6),      # brighten with them
    "excited": (0.7, 0.85),   # match the energy
}


def _derive_label(valence: float, energy: float) -> str:
    if valence >= 0.5:
        return "cheerful" if energy >= 0.55 else "warm"
    if valence <= -0.1:
        return "concerned"
    return "focused" if energy >= 0.55 else "calm"


def build_emotional_directive(reading: EmotionReading, mood: MoodState) -> str:
    """Short guidance block appended to the system prompt.

    Empty string when there is nothing worth signalling, so we don't dilute the
    prompt on ordinary neutral turns.
    """
    lines: list[str] = []
    if reading.label != "neutral" and reading.intensity >= 0.34:
        lines.append(
            f"The user seems {reading.label}. Acknowledge how they feel in one "
            "natural sentence before helping — don't diagnose or over-apologise."
        )
    lines.append(
        f"Your current mood is {mood.label}. Let it colour your wording lightly "
        "(warmth, energy) without ever stating it outright."
    )
    return "Emotional context:\n" + "\n".join(f"- {line}" for line in lines)


def emotion_to_tts(mood: MoodState) -> dict[str, float | str]:
    """Map mood onto TTS hints (rate multiplier + a coarse style tag).

    Consumed by the voice pipeline; safe defaults keep it usable even if the
    synthesiser ignores unknown keys.
    """
    # Higher energy → slightly faster; low valence → slightly slower/softer.
    rate = 1.0 + (mood.energy - 0.5) * 0.3 - (0.2 - mood.valence) * 0.2
    rate = round(max(0.75, min(1.25, rate)), 3)
    return {"rate": rate, "style": mood.label}
