"""Task classifier for model routing."""
from __future__ import annotations

import re
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


class TaskClassifier:
    def __init__(self):
        self._patterns = {
            TaskCategory.REASONING: [r"think", r"analyze", r"why", r"how", r"explain", r"reason", r"logic"],
            TaskCategory.FAST: [r"quick", r"simple", r"what is", r"define", r"list"],
            TaskCategory.VISION: [r"image", r"photo", r"picture", r"visual", r"see", r"look at"],
            TaskCategory.CODING: [r"code", r"function", r"class", r"import", r"def ", r"script", r"bug", r"debug"],
            TaskCategory.CREATIVE: [r"write", r"story", r"poem", r"creative", r"imagine", r"generate"],
            TaskCategory.ANALYSIS: [r"compare", r"contrast", r"summarize", r"report", r"data", r"statistics"],
        }
        self._model_costs = {
            "fast_model": {"input": 0.0001, "output": 0.0003},
            "reasoning_model": {"input": 0.001, "output": 0.003},
            "vision_model": {"input": 0.005, "output": 0.015},
            "coding_model": {"input": 0.001, "output": 0.003},
        }

    def classify(self, prompt: str, estimated_tokens: int = 100) -> TaskClassification:
        scores = {}
        for category, patterns in self._patterns.items():
            score = sum(2 if re.search(p, prompt, re.IGNORECASE) else 0 for p in patterns)
            # Bonus for coding-specific keywords
            if category == TaskCategory.CODING:
                score += sum(3 for kw in ["python", "function", "def ", "class ", "import"] if kw in prompt.lower())
            scores[category] = score

        best_category = max(scores, key=scores.get)
        confidence = scores[best_category] / max(sum(scores.values()), 1)

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
