"""
LLM router that selects a primary provider and supports category-based overrides.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import LLMProviderBase


class LLMRouter:
    """Simple router for LLM providers with category mapping."""

    def __init__(self, primary: str, providers: Dict[str, LLMProviderBase],
                 category_map: Optional[Dict[str, str]] = None):
        self.primary = primary
        self.providers = providers
        self.category_map = category_map or {}

    def get_provider(self, category: Optional[str] = None) -> LLMProviderBase:
        if category and category in self.category_map:
            name = self.category_map[category]
            if name in self.providers:
                return self.providers[name]
        return self.providers[self.primary]

    def generate(self, message: str, *, category: Optional[str] = None,
                 context: Optional[List[Dict[str, Any]]] = None,
                 max_tokens: int = 150, temperature: float = 0.3) -> str:
        provider = self.get_provider(category)
        return provider.generate(message, context=context, max_tokens=max_tokens, temperature=temperature)

    def test_connection(self, category: Optional[str] = None) -> bool:
        return self.get_provider(category).test_connection()


