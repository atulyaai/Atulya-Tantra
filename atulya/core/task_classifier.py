"""Task classifier for model routing using semantic similarity."""
from __future__ import annotations

import re
import math
from dataclasses import dataclass
from enum import Enum


class TaskCategory(Enum):
    REASONING = "reasoning"
    FAST = "fast"
    VISION = "vision"
    CODING = "coding"
    CREATIVE = "creative"
    ANALYSIS = "analysis"


@dataclass
class TaskClassification:
    category: TaskCategory
    confidence: float
    estimated_tokens: int
    recommended_model: str
    estimated_cost: float


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _tfidf_similarity(query_tokens: list[str], prototype_tokens: list[str]) -> float:
    """Simple TF-IDF-like similarity without external dependencies."""
    if not query_tokens or not prototype_tokens:
        return 0.0

    query_set = set(query_tokens)
    proto_set = set(prototype_tokens)

    overlap = query_set & proto_set
    if not overlap:
        return 0.0

    query_freq = {}
    for t in query_tokens:
        query_freq[t] = query_freq.get(t, 0) + 1

    proto_freq = {}
    for t in prototype_tokens:
        proto_freq[t] = proto_freq.get(t, 0) + 1

    dot = sum(query_freq[t] * proto_freq[t] for t in overlap)
    q_norm = math.sqrt(sum(v * v for v in query_freq.values()))
    p_norm = math.sqrt(sum(v * v for v in proto_freq.values()))

    if q_norm == 0 or p_norm == 0:
        return 0.0
    return dot / (q_norm * p_norm)


class TaskClassifier:
    def __init__(self):
        self._prototypes = {
            TaskCategory.REASONING: {
                "keywords": ["think", "analyze", "why", "how", "explain", "reason", "logic", "understand", "concept", "theory", "philosophy", "deep", "complex"],
                "phrases": [
                    "explain how this works",
                    "why is this happening",
                    "think through this problem",
                    "analyze the situation",
                    "what is the reason for",
                    "help me understand",
                    "break down this concept",
                    "compare and contrast",
                ],
            },
            TaskCategory.FAST: {
                "keywords": ["quick", "simple", "what is", "define", "list", "name", "yes", "no", "true", "false", "basic", "short", "brief"],
                "phrases": [
                    "what is the capital of",
                    "define this term",
                    "list the items",
                    "give me a quick answer",
                    "is this correct",
                    "name the options",
                    "what does this mean",
                ],
            },
            TaskCategory.VISION: {
                "keywords": ["image", "photo", "picture", "visual", "see", "look", "camera", "video", "screen", "display", "show me", "capture", "frame"],
                "phrases": [
                    "what do you see",
                    "look at this image",
                    "analyze this photo",
                    "describe what you see",
                    "capture the screen",
                    "what is in this picture",
                    "scan this visual",
                ],
            },
            TaskCategory.CODING: {
                "keywords": ["code", "function", "class", "import", "def", "script", "bug", "debug", "program", "compile", "run", "execute", "syntax", "variable", "loop", "array"],
                "phrases": [
                    "write a function that",
                    "fix this bug in",
                    "create a class for",
                    "write a python script",
                    "implement an algorithm",
                    "debug this code",
                    "refactor this function",
                    "build a web application",
                    "write unit tests for",
                    "parse this data",
                ],
            },
            TaskCategory.CREATIVE: {
                "keywords": ["write", "story", "poem", "creative", "imagine", "generate", "compose", "draft", "narrative", "fiction", "essay", "article", "blog"],
                "phrases": [
                    "write a story about",
                    "compose a poem about",
                    "create a narrative",
                    "draft an essay on",
                    "write a creative piece",
                    "imagine a scenario where",
                    "generate a description of",
                    "write dialogue between",
                ],
            },
            TaskCategory.ANALYSIS: {
                "keywords": ["compare", "contrast", "summarize", "report", "data", "statistics", "trend", "evaluate", "assess", "review", "audit", "measure"],
                "phrases": [
                    "compare these two options",
                    "summarize the key points",
                    "analyze the data trends",
                    "evaluate the performance",
                    "create a report on",
                    "contrast the differences",
                    "assess the quality of",
                    "review this document",
                ],
            },
        }
        self._model_costs = {
            "fast_model": {"input": 0.0001, "output": 0.0003},
            "reasoning_model": {"input": 0.001, "output": 0.003},
            "vision_model": {"input": 0.005, "output": 0.015},
            "coding_model": {"input": 0.001, "output": 0.003},
        }

    def classify(self, prompt: str, estimated_tokens: int = 100) -> TaskClassification:
        query_tokens = _tokenize(prompt)
        scores = {}

        for category, proto in self._prototypes.items():
            keyword_score = sum(3 if t in query_tokens else 0 for t in proto["keywords"])

            phrase_score = 0
            prompt_lower = prompt.lower()
            for phrase in proto["phrases"]:
                phrase_tokens = _tokenize(phrase)
                sim = _tfidf_similarity(query_tokens, phrase_tokens)
                if sim > 0.3:
                    phrase_score += sim * 5

            if category == TaskCategory.CODING:
                code_bonus = sum(4 for kw in ["python", "javascript", "typescript", "rust", "go", "java", "c++", "sql", "html", "css"] if kw in prompt_lower)
                keyword_score += code_bonus

            scores[category] = keyword_score + phrase_score

        best_category = max(scores, key=scores.get)
        max_score = scores[best_category]
        total_score = sum(scores.values())

        if max_score == 0:
            confidence = 0.5
        else:
            confidence = min(0.98, 0.6 + (max_score / max(total_score, 1)) * 0.3 + min(0.08, len(query_tokens) * 0.003))

        model_map = {
            TaskCategory.REASONING: "reasoning_model",
            TaskCategory.FAST: "fast_model",
            TaskCategory.VISION: "vision_model",
            TaskCategory.CODING: "coding_model",
            TaskCategory.CREATIVE: "reasoning_model",
            TaskCategory.ANALYSIS: "reasoning_model",
        }

        recommended = model_map[best_category]
        costs = self._model_costs.get(recommended, {"input": 0.001, "output": 0.003})
        estimated_cost = (estimated_tokens / 1000) * (costs["input"] + costs["output"]) / 2

        return TaskClassification(
            category=best_category,
            confidence=confidence,
            estimated_tokens=estimated_tokens,
            recommended_model=recommended,
            estimated_cost=estimated_cost,
        )
