"""
LLM Provider for Atulya Tantra AGI
Base class for LLM providers
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

class LLMProvider(ABC):
    """Base class for LLM providers"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.name = "BaseLLMProvider"
    
    @abstractmethod
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response from LLM"""
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider is available"""
        pass