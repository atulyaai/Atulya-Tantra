"""Multi-provider web search with fallbacks."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str
    timestamp: float = field(default_factory=time.time)


class MultiProviderSearch:
    def __init__(self):
        self._providers = ["duckduckgo", "wikipedia", "arxiv"]
        self._total_searches = 0

    def search(self, query: str, max_results: int = 10, region: str = "wt-wt") -> list[SearchResult]:
        """Search with fallback providers."""
        self._total_searches += 1
        results = []

        # Try DuckDuckGo first
        try:
            from duckduckgo_search import DDGS
            ddg_results = DDGS().text(query, max_results=max_results)
            for r in ddg_results:
                results.append(SearchResult(
                    title=r.get("title", ""), url=r.get("href", ""),
                    snippet=r.get("body", ""), source="duckduckgo",
                ))
        except Exception:
            pass

        # Fallback to Wikipedia
        if not results:
            try:
                import wikipedia
                wiki_results = wikipedia.search(query, results=5)
                for title in wiki_results:
                    page = wikipedia.page(title, auto_suggest=False)
                    results.append(SearchResult(
                        title=page.title, url=page.url,
                        snippet=page.summary[:300], source="wikipedia",
                    ))
            except Exception:
                pass

        # Fallback to arXiv for academic queries
        if not results or any(kw in query.lower() for kw in ["paper", "research", "study", "arxiv"]):
            try:
                import arxiv
                search = arxiv.Search(query=query, max_results=5)
                for paper in search.results():
                    results.append(SearchResult(
                        title=paper.title, url=paper.entry_id,
                        snippet=paper.summary[:300], source="arxiv",
                    ))
            except Exception:
                pass

        return results[:max_results]

    def get_providers(self) -> list[str]:
        return self._providers

    @property
    def stats(self) -> dict[str, Any]:
        """Return usage statistics."""
        return {
            "total_searches": self._total_searches,
            "providers": len(self._providers),
            "configured_providers": list(self._providers),
        }
