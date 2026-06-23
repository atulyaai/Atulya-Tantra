"""TokenJuice — token usage optimization and management engine."""
from __future__ import annotations

import json
import math
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .estimator import estimate_tokens, estimate_cost


@dataclass
class TokenUsage:
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost: float = 0.0
    timestamp: float = field(default_factory=time.time)
    session_id: str = ""
    task_type: str = ""


@dataclass
class TokenBudget:
    daily_token_limit: int = 1_000_000
    monthly_cost_limit: float = 50.0
    per_session_limit: int = 100_000
    enabled: bool = True


@dataclass
class CompressionResult:
    original_tokens: int
    compressed_tokens: int
    ratio: float
    text: str


class TokenJuice:
    """Token optimization engine. Tracks usage, enforces budgets,
    compresses prompts, and provides cost analytics."""

    def __init__(self, data_dir: str | Path, budget: TokenBudget | None = None,
                 max_records: int = 10_000, max_cache: int = 500):
        self.data_dir = Path(data_dir) / "tokenjuice"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.budget = budget or TokenBudget()
        self.max_records = max_records
        self.max_cache = max_cache
        self._lock = threading.Lock()
        self._usage: list[TokenUsage] = []
        self._sessions: dict[str, list[TokenUsage]] = {}
        self._compression_cache: dict[str, CompressionResult] = {}
        self._load()

    # ── persistence ──────────────────────────────────────────

    def _load(self):
        f = self.data_dir / "usage.json"
        if f.exists():
            try:
                data = json.loads(f.read_text())
                for u in data.get("usage", []):
                    rec = TokenUsage(**u)
                    self._usage.append(rec)
                    sid = rec.session_id
                    if sid:
                        self._sessions.setdefault(sid, []).append(rec)
            except Exception:
                pass

    def _save(self):
        f = self.data_dir / "usage.json"
        f.write_text(json.dumps({"usage": [vars(u) for u in self._usage]}, indent=2))

    # ── tracking ─────────────────────────────────────────────

    def track(self, provider: str, model: str, prompt: str, completion: str,
              session_id: str = "", task_type: str = "") -> TokenUsage:
        pt = estimate_tokens(prompt, model)
        ct = estimate_tokens(completion, model)
        cost = estimate_cost(pt, ct, model)
        rec = TokenUsage(
            provider=provider, model=model,
            prompt_tokens=pt, completion_tokens=ct,
            cost=cost, session_id=session_id, task_type=task_type,
        )
        with self._lock:
            self._usage.append(rec)
            if session_id:
                self._sessions.setdefault(session_id, []).append(rec)
            if len(self._usage) > self.max_records:
                self._usage = self._usage[-self.max_records:]
            if len(self._compression_cache) > self.max_cache:
                self._compression_cache.clear()
        self._save()
        return rec

    def track_raw(self, provider: str, model: str, prompt_tokens: int,
                  completion_tokens: int, session_id: str = "",
                  task_type: str = "") -> TokenUsage:
        cost = estimate_cost(prompt_tokens, completion_tokens, model)
        rec = TokenUsage(
            provider=provider, model=model,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            cost=cost, session_id=session_id, task_type=task_type,
        )
        with self._lock:
            self._usage.append(rec)
            if session_id:
                self._sessions.setdefault(session_id, []).append(rec)
            if len(self._usage) > self.max_records:
                self._usage = self._usage[-self.max_records:]
        self._save()
        return rec

    # ── budgets ──────────────────────────────────────────────

    def check_budget(self, session_id: str = "") -> dict[str, Any]:
        now = time.time()
        today_start = now - 86400
        month_start = now - 2592000

        daily_tokens = sum(u.prompt_tokens + u.completion_tokens
                           for u in self._usage if u.timestamp > today_start)
        monthly_cost = sum(u.cost for u in self._usage if u.timestamp > month_start)
        session_tokens = sum(u.prompt_tokens + u.completion_tokens
                             for u in self._sessions.get(session_id, []))

        violations = []
        if self.budget.enabled:
            if daily_tokens >= self.budget.daily_token_limit:
                violations.append("daily_token_limit")
            if monthly_cost >= self.budget.monthly_cost_limit:
                violations.append("monthly_cost_limit")
            if session_id and session_tokens >= self.budget.per_session_limit:
                violations.append("per_session_limit")

        return {
            "within_budget": len(violations) == 0,
            "daily_tokens": daily_tokens,
            "daily_limit": self.budget.daily_token_limit,
            "monthly_cost": round(monthly_cost, 4),
            "monthly_limit": self.budget.monthly_cost_limit,
            "session_tokens": session_tokens,
            "session_limit": self.budget.per_session_limit,
            "violations": violations,
        }

    # ── compression ──────────────────────────────────────────

    def compress_prompt(self, text: str, model: str = "default",
                        aggressive: bool = False) -> CompressionResult:
        cache_key = hash(text)
        if cache_key in self._compression_cache:
            return self._compression_cache[cache_key]

        original = estimate_tokens(text, model)
        compressed = self._compress_text(text, aggressive)
        compressed_tokens = estimate_tokens(compressed, model)
        ratio = compressed_tokens / max(original, 1)

        result = CompressionResult(
            original_tokens=original,
            compressed_tokens=compressed_tokens,
            ratio=ratio,
            text=compressed,
        )
        self._compression_cache[cache_key] = result
        return result

    @staticmethod
    def _compress_text(text: str, aggressive: bool = False) -> str:
        lines = text.split("\n")
        kept = []
        seen = set()
        for line in lines:
            stripped = line.strip()
            if not stripped:
                kept.append(line)
                continue
            norm = stripped.lower()
            # Remove duplicate lines
            if norm in seen and aggressive:
                continue
            seen.add(norm)
            # Remove single-word lines that are filler
            if aggressive and len(stripped.split()) == 1 and stripped in ("ok", "yes", "no", "and", "the"):
                continue
            kept.append(line)
        result = "\n".join(kept)

        if aggressive:
            result = re.sub(r"\n{3,}", "\n\n", result)
        return result

    # ── analytics ────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        total_prompt = sum(u.prompt_tokens for u in self._usage)
        total_completion = sum(u.completion_tokens for u in self._usage)
        total_cost = sum(u.cost for u in self._usage)

        by_provider: dict[str, int] = {}
        by_model: dict[str, dict[str, Any]] = {}
        for u in self._usage:
            by_provider[u.provider] = by_provider.get(u.provider, 0) + u.prompt_tokens + u.completion_tokens
            if u.model not in by_model:
                by_model[u.model] = {"calls": 0, "tokens": 0, "cost": 0.0}
            by_model[u.model]["calls"] += 1
            by_model[u.model]["tokens"] += u.prompt_tokens + u.completion_tokens
            by_model[u.model]["cost"] += u.cost

        return {
            "total_calls": len(self._usage),
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_prompt + total_completion,
            "total_cost": round(total_cost, 4),
            "by_provider": by_provider,
            "by_model": by_model,
            "cache_entries": len(self._compression_cache),
            "budget": self.check_budget(),
        }

    def get_optimization_suggestions(self) -> list[dict[str, Any]]:
        suggestions = []
        total_tokens = sum(u.prompt_tokens + u.completion_tokens for u in self._usage)
        if total_tokens == 0:
            return suggestions

        # Check if repetitive calls
        by_session = len(self._sessions)
        if by_session > 0 and total_tokens / by_session > 50000:
            suggestions.append({
                "type": "compression",
                "message": "Enable prompt compression for long sessions",
                "savings_estimate": "30-50% token reduction",
            })

        # Check model cost efficiency
        for model, data in self.get_stats()["by_model"].items():
            if data["tokens"] > 100000 and model in ("gpt-4", "claude"):
                suggestions.append({
                    "type": "model_switch",
                    "message": f"Consider switching {model} to a lighter model for bulk tasks",
                    "savings_estimate": f"~${data['cost'] * 0.6:.2f} monthly",
                })

        # Check cache utilization
        if len(self._compression_cache) < 10 and total_tokens > 50000:
            suggestions.append({
                "type": "caching",
                "message": "Enable response caching for repeated prompts",
                "savings_estimate": "20-40% API calls reduction",
            })

        suggestions.append({
            "type": "budget",
            "message": "Set daily token budget to prevent cost overruns",
            "savings_estimate": "100% cost predictability",
        })

        return suggestions
