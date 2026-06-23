"""Token usage estimation (lightweight, no external deps)."""
from __future__ import annotations

import math
import re

# Average bytes per token heuristic for various model families
MODEL_TOKEN_RATES = {
    "gpt-4": 4.0,
    "gpt-3.5": 4.5,
    "claude": 3.8,
    "llama": 4.2,
    "gemini": 4.1,
    "mistral": 4.3,
    "deepseek": 4.0,
    "default": 4.0,
}


def _chars_per_token(text: str) -> float:
    """Estimate average char-per-token ratio based on text composition."""
    ascii_count = len(re.findall(r"[ -~]", text))
    unicode_count = len(text) - ascii_count
    total = max(len(text), 1)
    ratio = (ascii_count * 1.0 + unicode_count * 3.0) / total
    return max(1.5, min(6.0, ratio))


def estimate_tokens(text: str, model: str = "default") -> int:
    """Estimate token count for a given text and model family."""
    rate = MODEL_TOKEN_RATES.get(model, MODEL_TOKEN_RATES["default"])
    cpt = _chars_per_token(text)
    return max(1, int(len(text) / (rate * cpt / 4.0)))


def estimate_cost(input_tokens: int, output_tokens: int, model: str = "default") -> float:
    """Estimate API cost in USD for given token counts."""
    rates = {
        "gpt-4": (0.00003, 0.00006),
        "gpt-3.5": (0.0000015, 0.000002),
        "claude": (0.000015, 0.000075),
        "llama": (0.000002, 0.000002),
        "gemini": (0.00000125, 0.000005),
        "default": (0.00001, 0.00003),
    }
    inp_rate, out_rate = rates.get(model, rates["default"])
    return (input_tokens * inp_rate) + (output_tokens * out_rate)
