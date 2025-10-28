"""
Base interfaces and types for LLM providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class LLMProviderBase(ABC):
    """
    Abstract base class for all LLM providers.
    Implementations must be CPU-friendly by default and support minimal configs.
    """

    @abstractmethod
    def generate(self, message: str, context: Optional[List[Dict[str, Any]]] = None,
                 max_tokens: int = 150, temperature: float = 0.3) -> str:
        """Generate a response for the given message and optional context."""
        raise NotImplementedError

    def count_tokens(self, text: str) -> int:
        """Approximate token counting; override if provider has accurate counter."""
        return int(len(text.split()) * 1.3)

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Return model metadata like name, max context, device, etc."""
        raise NotImplementedError

    def test_connection(self) -> bool:
        """Return True if the provider can generate; default True for local providers."""
        return True


