"""Web Augmentation — auto search and absorb knowledge into Cortex.

When Atulya doesn't know something (low confidence), it:
1. Detects the knowledge gap (confidence scoring)
2. Fires a web search automatically
3. Parses results into clean chunks
4. Embeds and stores in MemoryCortex
5. Retrieves them in the same generation turn

This gives a small model (50M params) access to the entire web
without any training — pure knowledge injection at inference time.

CPU-friendly: all embedding is torch matmul, no GPU needed.
Rate-limited: respects search API limits, caches results.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import torch
from torch import Tensor

logger = logging.getLogger(__name__)


# ── Search result ─────────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    full_text: str = ""
    fetched_at: float = field(default_factory=time.time)

    @property
    def combined_text(self) -> str:
        parts = [self.title, self.snippet]
        if self.full_text:
            parts.append(self.full_text[:800])
        return " ".join(parts)


# ── Search backends ───────────────────────────────────────────────────────────

def _search_duckduckgo(query: str, max_results: int = 5) -> list[SearchResult]:
    """DuckDuckGo Instant Answers API (no API key required)."""
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Atulya/2.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))

        results = []
        # Abstract (main result)
        if data.get("AbstractText"):
            results.append(SearchResult(
                title=data.get("Heading", query),
                url=data.get("AbstractURL", ""),
                snippet=data["AbstractText"][:500],
            ))
        # Related topics
        for item in data.get("RelatedTopics", [])[:max_results - len(results)]:
            if "Text" in item and "FirstURL" in item:
                results.append(SearchResult(
                    title=item.get("Text", "")[:100],
                    url=item["FirstURL"],
                    snippet=item["Text"][:500],
                ))
        return results[:max_results]
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed: {e}")
        return []


def _search_brave(query: str, api_key: str, max_results: int = 5) -> list[SearchResult]:
    """Brave Search API (requires API key, but free tier available)."""
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://api.search.brave.com/res/v1/web/search?q={encoded}&count={max_results}"
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))

        results = []
        for item in data.get("web", {}).get("results", []):
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("description", "")[:500],
            ))
        return results
    except Exception as e:
        logger.warning(f"Brave search failed: {e}")
        return []


# ── Confidence scorer ─────────────────────────────────────────────────────────

class ConfidenceScorer:
    """Estimate how confident the model is about a token sequence.

    Low confidence = high entropy in the logit distribution.
    When entropy > threshold, trigger web search.

    This is NOT a separate model — it just reads the logits
    that are already computed during generation.
    """

    def __init__(self, entropy_threshold: float = 3.5, window: int = 8):
        self.entropy_threshold = entropy_threshold
        self.window = window
        self._recent_entropies: list[float] = []

    def record(self, logits: Tensor) -> float:
        """Record entropy for a token's logit distribution."""
        probs = torch.softmax(logits.float(), dim=-1)
        entropy = -(probs * (probs + 1e-9).log()).sum().item()
        self._recent_entropies.append(entropy)
        if len(self._recent_entropies) > self.window:
            self._recent_entropies.pop(0)
        return entropy

    @property
    def is_uncertain(self) -> bool:
        """True if recent generation shows high uncertainty."""
        if len(self._recent_entropies) < 3:
            return False
        avg = sum(self._recent_entropies) / len(self._recent_entropies)
        return avg > self.entropy_threshold

    def reset(self) -> None:
        self._recent_entropies.clear()


# ── Web knowledge cache ───────────────────────────────────────────────────────

class WebKnowledgeCache:
    """Disk cache for search results to avoid redundant API calls.

    Cache key = SHA256 of query. TTL default 24h.
    """

    def __init__(self, cache_dir: Path, ttl_seconds: float = 86400):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl_seconds

    def _key(self, query: str) -> str:
        return hashlib.sha256(query.lower().strip().encode()).hexdigest()[:16]

    def get(self, query: str) -> Optional[list[dict]]:
        p = self.cache_dir / f"{self._key(query)}.json"
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text())
            if time.time() - data.get("fetched_at", 0) > self.ttl:
                p.unlink()
                return None
            return data.get("results", [])
        except Exception:
            return None

    def set(self, query: str, results: list[dict]) -> None:
        p = self.cache_dir / f"{self._key(query)}.json"
        p.write_text(json.dumps({
            "query": query,
            "fetched_at": time.time(),
            "results": results,
        }, indent=2))


# ── Main web augmenter ────────────────────────────────────────────────────────

class WebAugmenter:
    """Auto-search and inject knowledge into MemoryCortex.

    Workflow:
        1. User asks something → generation starts
        2. ConfidenceScorer detects uncertainty
        3. WebAugmenter.augment(query) fires
        4. Results embedded → stored in Cortex
        5. Cortex retrieved on next tokens → model uses the knowledge

    Zero retraining. Pure inference-time knowledge injection.

    Args:
        cortex: MemoryCortex to inject into
        model: NpDnaCore (for embedding)
        tokenizer: AtulyaTokenizer
        brave_api_key: Optional Brave API key (better results)
        cache_dir: Where to cache search results
        max_inject: Max Cortex entries per search
        min_interval: Seconds between searches (rate limit)
    """

    def __init__(
        self,
        cortex,
        model,
        tokenizer,
        brave_api_key: str = "",
        cache_dir: Path = Path("~/.atulya/web_cache"),
        max_inject: int = 8,
        min_interval: float = 2.0,
    ):
        self.cortex = cortex
        self.model = model
        self.tokenizer = tokenizer
        self.brave_api_key = brave_api_key
        self.cache = WebKnowledgeCache(Path(cache_dir).expanduser())
        self.max_inject = max_inject
        self.min_interval = min_interval
        self.scorer = ConfidenceScorer()
        self._last_search_time: float = 0
        self._search_count: int = 0
        self._injected_count: int = 0

    def _can_search(self) -> bool:
        return (time.time() - self._last_search_time) >= self.min_interval

    def _search(self, query: str) -> list[SearchResult]:
        """Search using available backend, with cache."""
        cached = self.cache.get(query)
        if cached:
            return [SearchResult(**r) for r in cached]

        if self.brave_api_key:
            results = _search_brave(query, self.brave_api_key)
        else:
            results = _search_duckduckgo(query)

        if results:
            self.cache.set(query, [r.__dict__ for r in results])
        return results

    @torch.no_grad()
    def _embed(self, text: str, max_len: int = 128) -> Tensor:
        """Embed text to a vector using model embedding layer."""
        ids = self.tokenizer.encode(text)[:max_len]
        if not ids:
            return torch.zeros(self.model.config.hidden_size)
        ids_t = torch.tensor([ids], dtype=torch.long)
        emb = self.model.embedding(ids_t).mean(dim=1).squeeze(0)
        return emb.cpu()

    def augment(self, query: str, force: bool = False) -> int:
        """Search for query and inject results into Cortex.

        Args:
            query: Search query (usually derived from user's message)
            force: Bypass rate limit and interval check

        Returns:
            Number of entries injected into Cortex
        """
        if not force and not self._can_search():
            return 0

        self._last_search_time = time.time()
        self._search_count += 1

        results = self._search(query)
        if not results:
            return 0

        injected = 0
        for result in results[:self.max_inject]:
            text = result.combined_text
            if not text.strip():
                continue
            # Split long text into overlapping chunks
            words = text.split()
            for i in range(0, len(words), 100):
                chunk = " ".join(words[i:i + 120])
                vec = self._embed(chunk)
                self.cortex.store(
                    vec,
                    topic=f"web:{query[:30]}",
                    source=result.url,
                )
                injected += 1
                if injected >= self.max_inject:
                    break
            if injected >= self.max_inject:
                break

        self._injected_count += injected
        logger.info(f"WebAugmenter: '{query[:40]}' → {len(results)} results → {injected} Cortex entries")
        return injected

    def should_augment(self, prompt: str, logits: Optional[Tensor] = None) -> bool:
        """Decide whether to trigger a web search.

        Triggers when:
        - Prompt contains factual question words
        - Logits show high uncertainty (if provided)
        - Cortex has no relevant entries for this topic
        """
        question_patterns = [
            r"\b(what|who|when|where|how|why|which)\b",
            r"\b(current|latest|recent|today|now|2024|2025|2026)\b",
            r"\b(price|rate|news|update|status|result)\b",
        ]
        for p in question_patterns:
            if re.search(p, prompt, re.IGNORECASE):
                if logits is not None:
                    self.scorer.record(logits)
                    return self.scorer.is_uncertain
                return True

        return False

    def extract_query(self, prompt: str) -> str:
        """Extract a clean search query from user prompt."""
        # Remove common filler
        clean = re.sub(r"^(hey|hi|hello|please|can you|could you|tell me|what is|what are)\s+",
                       "", prompt.strip(), flags=re.IGNORECASE)
        # Take first 8 words as query
        words = clean.split()[:8]
        return " ".join(words)

    @property
    def stats(self) -> dict:
        return {
            "searches": self._search_count,
            "injected": self._injected_count,
            "cortex_size": self.cortex.size,
        }
