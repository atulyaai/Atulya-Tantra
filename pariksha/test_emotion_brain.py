"""Tests for the human layer (emotion/mood) and the Brain confidence path."""
from __future__ import annotations

import pytest

from atulya.bhava import EmotionReading, MoodState, build_emotional_directive, detect_emotion, emotion_to_tts


# --- emotion detection ---------------------------------------------------

def test_detect_neutral_on_empty():
    r = detect_emotion("")
    assert r.label == "neutral"
    assert r.intensity == 0.0


@pytest.mark.parametrize(
    "text,expected",
    [
        ("I'm so tired and exhausted today", "tired"),
        ("this is ridiculous, I'm furious", "angry"),
        ("I feel sad and lonely", "sad"),
        ("I'm really worried and stressed about this", "anxious"),
        ("this is amazing, can't wait!", "excited"),
        ("thank you, that's wonderful", "happy"),
    ],
)
def test_detect_emotion_labels(text, expected):
    assert detect_emotion(text).label == expected


def test_detect_intensity_scales_with_cues():
    weak = detect_emotion("I'm a bit sad")
    strong = detect_emotion("I'm sad, unhappy, lonely and hurt")
    assert strong.intensity > weak.intensity


def test_is_negative_flag():
    assert detect_emotion("I'm exhausted").is_negative
    assert not detect_emotion("thanks, great job").is_negative


# --- mood state ----------------------------------------------------------

def test_mood_nudge_toward_support_when_user_down():
    mood = MoodState()
    before = mood.energy
    mood.nudge(detect_emotion("I'm exhausted and drained"), empathy=0.5)
    # Supportive response to tiredness = calmer (lower energy).
    assert mood.energy < before
    assert mood.label in ("calm", "warm", "focused", "concerned")


def test_mood_brightens_with_excited_user():
    mood = MoodState()
    mood.nudge(detect_emotion("this is awesome, let's go!"), empathy=0.6)
    assert mood.valence > 0.2


def test_mood_persist_roundtrip(tmp_path):
    path = tmp_path / "mood.json"
    mood = MoodState(valence=0.4, energy=0.7)
    mood.save(path)
    loaded = MoodState.load(path)
    assert loaded.valence == 0.4
    assert loaded.energy == 0.7


def test_mood_load_missing_returns_default(tmp_path):
    assert MoodState.load(tmp_path / "nope.json").label == "content"


# --- directives / tts mapping -------------------------------------------

def test_directive_mentions_feeling_when_strong():
    reading = detect_emotion("I'm so anxious and overwhelmed and scared")
    text = build_emotional_directive(reading, MoodState())
    assert "anxious" in text.lower()


def test_directive_skips_feeling_when_neutral():
    text = build_emotional_directive(EmotionReading(), MoodState())
    assert "the user seems" not in text.lower()
    assert "mood" in text.lower()  # still carries Atulya's own mood


def test_emotion_to_tts_bounds():
    hints = emotion_to_tts(MoodState(valence=1.0, energy=1.0))
    assert 0.75 <= hints["rate"] <= 1.25
    assert isinstance(hints["style"], str)


def test_local_model_skips_hidden_thinking_unless_asked(monkeypatch):
    from atulya.mastishk import _with_think_switch

    monkeypatch.delenv("ATULYA_LOCAL_THINK", raising=False)
    assert _with_think_switch("hi").endswith("/no_think")
    monkeypatch.setenv("ATULYA_LOCAL_THINK", "1")
    assert _with_think_switch("hi") == "hi"
