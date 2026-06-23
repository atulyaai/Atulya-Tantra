"""Tests for intent classification - both frontend and backend."""
from __future__ import annotations

import math

import pytest


class TestBackendTaskClassifier:
    def _get_classifier(self):
        import importlib.util
        import sys
        from pathlib import Path
        spec = importlib.util.spec_from_file_location(
            "task_classifier",
            str(Path(__file__).resolve().parents[1] / "tantra" / "core" / "task_classifier.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["task_classifier"] = mod
        spec.loader.exec_module(mod)
        return mod.TaskClassifier(), mod.TaskCategory

    def test_classify_coding(self):
        classifier, category = self._get_classifier()
        result = classifier.classify("write a python function to sort a list")
        assert result.category == category.CODING
        assert result.confidence > 0.5

    def test_classify_reasoning(self):
        classifier, category = self._get_classifier()
        result = classifier.classify("explain how quantum physics works")
        assert result.category == category.REASONING
        assert result.confidence > 0.5

    def test_classify_vision(self):
        classifier, category = self._get_classifier()
        result = classifier.classify("look at this image and describe it")
        assert result.category == category.VISION
        assert result.confidence > 0.5

    def test_classify_creative(self):
        classifier, category = self._get_classifier()
        result = classifier.classify("write a story about a brave knight")
        assert result.category == category.CREATIVE
        assert result.confidence > 0.5

    def test_classify_analysis(self):
        classifier, category = self._get_classifier()
        result = classifier.classify("compare these two options and summarize the differences")
        assert result.category == category.ANALYSIS
        assert result.confidence > 0.5

    def test_classify_fast(self):
        classifier, category = self._get_classifier()
        result = classifier.classify("what is the capital of France")
        assert result.category == category.FAST
        assert result.confidence > 0.5

    def test_confidence_range(self):
        classifier, _ = self._get_classifier()
        for prompt in ["hello", "write code", "explain physics", "look at this"]:
            result = classifier.classify(prompt)
            assert 0 <= result.confidence <= 0.98

    def test_recommended_model(self):
        classifier, category = self._get_classifier()
        result = classifier.classify("write a python function")
        assert result.recommended_model in ["fast_model", "reasoning_model", "vision_model", "coding_model"]

    def test_empty_prompt(self):
        classifier, category = self._get_classifier()
        result = classifier.classify("")
        assert result.category is not None

    def test_similar_prompts_similar_categories(self):
        classifier, category = self._get_classifier()
        r1 = classifier.classify("write a python script")
        r2 = classifier.classify("create a python function")
        assert r1.category == r2.category


class TestTFIDFSimilarity:
    def _get_similarity_fn(self):
        import importlib.util
        from pathlib import Path
        spec = importlib.util.spec_from_file_location(
            "task_classifier",
            str(Path(__file__).resolve().parents[1] / "tantra" / "core" / "task_classifier.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod._tfidf_similarity

    def test_identical_tokens(self):
        sim_fn = self._get_similarity_fn()
        sim = sim_fn(["hello", "world"], ["hello", "world"])
        assert abs(sim - 1.0) < 1e-6

    def test_no_overlap(self):
        sim_fn = self._get_similarity_fn()
        sim = sim_fn(["hello", "world"], ["goodbye", "universe"])
        assert sim == 0.0

    def test_partial_overlap(self):
        sim_fn = self._get_similarity_fn()
        sim = sim_fn(["hello", "world"], ["hello", "there"])
        assert 0 < sim < 1.0

    def test_empty_tokens(self):
        sim_fn = self._get_similarity_fn()
        assert sim_fn([], ["hello"]) == 0.0
        assert sim_fn(["hello"], []) == 0.0
        assert sim_fn([], []) == 0.0


class TestTokenize:
    def _get_tokenize_fn(self):
        import importlib.util
        from pathlib import Path
        spec = importlib.util.spec_from_file_location(
            "task_classifier",
            str(Path(__file__).resolve().parents[1] / "tantra" / "core" / "task_classifier.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod._tokenize

    def test_basic_tokenize(self):
        tokenize = self._get_tokenize_fn()
        tokens = tokenize("Hello World")
        assert tokens == ["hello", "world"]

    def test_alphanumeric(self):
        tokenize = self._get_tokenize_fn()
        tokens = tokenize("test123 value_456")
        assert "test123" in tokens

    def test_empty_string(self):
        tokenize = self._get_tokenize_fn()
        tokens = tokenize("")
        assert tokens == []

    def test_special_characters(self):
        tokenize = self._get_tokenize_fn()
        tokens = tokenize("hello, world! how's it?")
        assert "hello" in tokens
        assert "world" in tokens


class TestTaskClassifierBackend:
    def test_import(self):
        from tantra.core.task_classifier import TaskClassifier, TaskCategory, TaskClassification
        c = TaskClassifier()
        r = c.classify("write a python function")
        assert r.category == TaskCategory.CODING
        assert 0 <= r.confidence <= 0.98
        assert r.recommended_model in ["fast_model", "reasoning_model", "vision_model", "coding_model"]

    def test_reasoning(self):
        from tantra.core.task_classifier import TaskClassifier, TaskCategory
        r = TaskClassifier().classify("explain how quantum physics works")
        assert r.category == TaskCategory.REASONING

    def test_vision(self):
        from tantra.core.task_classifier import TaskClassifier, TaskCategory
        r = TaskClassifier().classify("look at this image and describe it")
        assert r.category == TaskCategory.VISION

    def test_creative(self):
        from tantra.core.task_classifier import TaskClassifier, TaskCategory
        r = TaskClassifier().classify("write a story about a brave knight")
        assert r.category == TaskCategory.CREATIVE

    def test_fast(self):
        from tantra.core.task_classifier import TaskClassifier, TaskCategory
        r = TaskClassifier().classify("what is the capital of France")
        assert r.category == TaskCategory.FAST

    def test_analysis(self):
        from tantra.core.task_classifier import TaskClassifier, TaskCategory
        r = TaskClassifier().classify("compare these options and summarize differences")
        assert r.category == TaskCategory.ANALYSIS
