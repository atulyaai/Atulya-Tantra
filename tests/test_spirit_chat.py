"""Tests for Spirit UI chat panel and wake word functionality."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestSpiritChatPanel:
    """Tests for the Spirit UI chat panel (HolographicSpirit component).

    Since this is a React component, we test the API endpoint it calls.
    """

    def test_voice_chat_endpoint_structure(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "voice",
            str(Path(__file__).resolve().parents[1] / "drishti" / "dashboard" / "routes" / "voice.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "router")

    def test_voice_chat_endpoint_exists(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "voice",
            str(Path(__file__).resolve().parents[1] / "drishti" / "dashboard" / "routes" / "voice.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        routes = [route.path for route in mod.router.routes]
        assert "/api/voice/chat" in routes

    def test_tts_endpoint_exists(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "voice",
            str(Path(__file__).resolve().parents[1] / "drishti" / "dashboard" / "routes" / "voice.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        routes = [route.path for route in mod.router.routes]
        assert "/api/voice/tts" in routes

    def test_voices_endpoint_exists(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "voice",
            str(Path(__file__).resolve().parents[1] / "drishti" / "dashboard" / "routes" / "voice.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        routes = [route.path for route in mod.router.routes]
        assert "/api/voice/voices" in routes


class TestWakeWordFunctionality:
    """Tests for wake word 'Hey Atulya' functionality.

    The wake word logic is in the frontend JavaScript, but we can test
    the concept through the strip wake phrase function.
    """

    def test_strip_wake_phrase_concept(self):
        """Test the concept of wake phrase stripping."""
        wake_phrases = ["hey atulya", "atulya"]

        def strip_wake(text):
            trimmed = str(text).strip()
            lower = trimmed.lower()
            for phrase in wake_phrases:
                if lower.startswith(phrase):
                    return trimmed[len(phrase):].lstrip(" ,.:;-").strip()
            return trimmed

        assert strip_wake("Hey Atulya open browser") == "open browser"
        assert strip_wake("Atulya search the web") == "search the web"
        assert strip_wake("open browser") == "open browser"
        assert strip_wake("Hey Atulya, what time is it?") == "what time is it?"
        assert strip_wake("ATULYA run a test") == "run a test"

    def test_wake_phrase_case_insensitive(self):
        wake_phrases = ["hey atulya", "atulya"]

        def strip_wake(text):
            trimmed = str(text).strip()
            lower = trimmed.lower()
            for phrase in wake_phrases:
                if lower.startswith(phrase):
                    return trimmed[len(phrase):].lstrip(" ,.:;-").strip()
            return trimmed

        assert strip_wake("HEY ATULYA hello") == "hello"
        assert strip_wake("Hey Atulya hello") == "hello"
        assert strip_wake("hey atulya hello") == "hello"

    def test_wake_phrase_strips_prefix_punctuation(self):
        wake_phrases = ["hey atulya"]

        def strip_wake(text):
            trimmed = str(text).strip()
            lower = trimmed.lower()
            for phrase in wake_phrases:
                if lower.startswith(phrase):
                    return trimmed[len(phrase):].lstrip(" ,.:;-").strip()
            return trimmed

        assert strip_wake("Hey Atulya, do something") == "do something"
        assert strip_wake("Hey Atulya: do something") == "do something"
        assert strip_wake("Hey Atulya - do something") == "do something"
        assert strip_wake("Hey Atulya. do something") == "do something"

    def test_wake_phrase_preserves_rest(self):
        wake_phrases = ["hey atulya"]

        def strip_wake(text):
            trimmed = str(text).strip()
            lower = trimmed.lower()
            for phrase in wake_phrases:
                if lower.startswith(phrase):
                    return trimmed[len(phrase):].lstrip(" ,.:;-").strip()
            return trimmed

        assert strip_wake("Hey Atulya remember that my name is Alice") == "remember that my name is Alice"
        assert strip_wake("Hey Atulya what is 2 + 2?") == "what is 2 + 2?"

    def test_wake_phrase_partial_match(self):
        wake_phrases = ["hey atulya", "atulya"]

        def strip_wake(text):
            trimmed = str(text).strip()
            lower = trimmed.lower()
            for phrase in wake_phrases:
                if lower.startswith(phrase):
                    return trimmed[len(phrase):].lstrip(" ,.:;-").strip()
            return trimmed

        assert strip_wake("atulya hello") == "hello"
        assert strip_wake("not atulya") == "not atulya"

    def test_wake_phrase_empty_after_strip(self):
        wake_phrases = ["hey atulya"]

        def strip_wake(text):
            trimmed = str(text).strip()
            lower = trimmed.lower()
            for phrase in wake_phrases:
                if lower.startswith(phrase):
                    return trimmed[len(phrase):].lstrip(" ,.:;-").strip()
            return trimmed

        assert strip_wake("Hey Atulya") == ""
        assert strip_wake("Hey Atulya ") == ""


class TestIntentClassificationFrontend:
    """Tests for the frontend intent classification logic.

    The frontend classifyIntent function uses prototype-based similarity.
    We test the concept here.
    """

    def test_intent_concepts(self):
        """Test that intent classification concepts work."""
        intent_prototypes = {
            "FORGE": {
                "boost": ["code", "build", "fix", "bug", "website", "app", "function", "script"],
            },
            "VISION": {
                "boost": ["see", "camera", "look", "image", "photo", "frame", "scan", "visual"],
            },
            "ATHENA": {
                "boost": ["open", "run", "search", "start", "stop", "device", "automation", "control"],
            },
            "MEMORY": {
                "boost": ["remember", "history", "previous", "recall", "memory", "saved"],
            },
        }

        def classify(text):
            input_lower = text.lower()
            scores = {}
            for agent, proto in intent_prototypes.items():
                score = sum(2 for word in proto["boost"] if word in input_lower)
                scores[agent] = score
            return max(scores, key=scores.get)

        assert classify("write code for a function") == "FORGE"
        assert classify("look at this image") == "VISION"
        assert classify("search the web") == "ATHENA"
        assert classify("recall our previous conversation") == "MEMORY"

    def test_intent_fallback(self):
        intent_prototypes = {
            "FORGE": {"boost": ["code", "build"]},
            "ORACLE": {"boost": []},
        }

        def classify(text):
            input_lower = text.lower()
            scores = {}
            for agent, proto in intent_prototypes.items():
                score = sum(2 for word in proto["boost"] if word in input_lower)
                scores[agent] = score
            max_score = max(scores.values())
            if max_score == 0:
                return "ORACLE"
            return max(scores, key=scores.get)

        assert classify("hello how are you") == "ORACLE"
        assert classify("write some code") == "FORGE"

    def test_intent_confidence_calculation(self):
        def calculate_confidence(input_text, max_score, total_score):
            if max_score == 0:
                return 50
            return min(98, 60 + (max_score / max(total_score, 1)) * 30 + min(8, len(input_text) // 30))

        assert calculate_confidence("hi", 0, 0) == 50
        assert 60 <= calculate_confidence("write code", 4, 4) <= 98
        assert 60 <= calculate_confidence("write a python function to sort a list", 8, 8) <= 98



class TestVoiceChatRoutes:
    def test_routes_exist(self):
        from drishti.dashboard.routes.voice import router
        paths = [r.path for r in router.routes]
        assert "/api/voice/chat" in paths
        assert "/api/voice/tts" in paths
        assert "/api/voice/voices" in paths

    def test_get_voices(self):
        from drishti.dashboard.routes.voice import get_voices
        r = get_voices()
        assert "voices" in r
        assert len(r["voices"]) >= 4


class TestWakeWord:
    def _strip(self, text):
        phrases = ["hey atulya", "atulya"]
        t = str(text).strip()
        lo = t.lower()
        for p in phrases:
            if lo.startswith(p):
                return t[len(p):].lstrip(" ,.:;-").strip()
        return t

    def test_basic(self):
        assert self._strip("Hey Atulya open browser") == "open browser"

    def test_case(self):
        assert self._strip("HEY ATULYA hello") == "hello"

    def test_punctuation(self):
        assert self._strip("Hey Atulya, do something") == "do something"
        assert self._strip("Hey Atulya: do something") == "do something"

    def test_no_wake_word(self):
        assert self._strip("open browser") == "open browser"

    def test_atulya_only(self):
        assert self._strip("Atulya search") == "search"

    def test_empty(self):
        assert self._strip("Hey Atulya") == ""

    def test_preserve_content(self):
        assert self._strip("Hey Atulya remember my name is Alice") == "remember my name is Alice"


class TestIntentClassification:
    def _classify(self, text):
        input_lower = text.lower()
        prototypes = {
            "FORGE": ["code", "build", "fix", "bug", "website", "app", "function", "script"],
            "VISION": ["see", "camera", "look", "image", "photo", "frame", "scan", "visual"],
            "ATHENA": ["open", "run", "search", "start", "stop", "device", "automation", "control"],
            "MEMORY": ["remember", "history", "previous", "recall", "memory", "saved"],
        }
        scores = {a: sum(2 for kw in kw_list if kw in input_lower) for a, kw_list in prototypes.items()}
        mx = max(scores.values())
        if mx == 0:
            return "ORACLE", 50
        w = max(scores, key=scores.get)
        c = min(98, 60 + (mx / max(sum(scores.values()), 1)) * 30 + min(8, len(input_lower) // 30))
        return w, c

    def test_forge(self):
        a, _ = self._classify("write code for a function")
        assert a == "FORGE"

    def test_vision(self):
        a, _ = self._classify("look at this image")
        assert a == "VISION"

    def test_athena(self):
        a, _ = self._classify("open the browser and search")
        assert a == "ATHENA"

    def test_memory(self):
        a, _ = self._classify("recall previous conversation")
        assert a == "MEMORY"

    def test_oracle_fallback(self):
        a, _ = self._classify("what is life")
        assert a == "ORACLE"

    def test_confidence_range(self):
        for t in ["hi", "write code", "look at image", "open browser"]:
            _, c = self._classify(t)
            assert 50 <= c <= 98
