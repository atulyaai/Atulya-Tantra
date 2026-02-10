"""LLM Integration Module - Multi-provider language model support with hybrid mode"""

import logging
import os
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# Dynamic imports for optional providers
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import requests
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


class LLMProvider(ABC):
    """Base class for LLM providers"""
    
    def __init__(self, name: str, config: Dict = None):
        self.name = name
        self.config = config or {}
        self.available = False
        
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate response from prompt"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available"""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI API Provider (GPT-4, GPT-3.5)"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        super().__init__("OpenAI")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.available = OPENAI_AVAILABLE and bool(self.api_key)
        
        if self.available:
            openai.api_key = self.api_key
            logger.info(f"OpenAI provider initialized with model: {model}")
    
    def is_available(self) -> bool:
        return self.available
    
    def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 500, **kwargs) -> str:
        """Generate response using OpenAI"""
        if not self.available:
            return None
        
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return None


class AnthropicProvider(LLMProvider):
    """Anthropic Claude Provider"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-sonnet-20240229"):
        super().__init__("Anthropic")
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        
        if ANTHROPIC_AVAILABLE and self.api_key:
            try:
                self.client = Anthropic(api_key=self.api_key)
                self.available = True
                logger.info(f"Anthropic provider initialized with model: {model}")
            except Exception as e:
                logger.warning(f"Anthropic initialization failed: {e}")
                self.available = False
        else:
            self.available = False
    
    def is_available(self) -> bool:
        return self.available
    
    def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 500, **kwargs) -> str:
        """Generate response using Claude"""
        if not self.available:
            return None
        
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"Anthropic error: {e}")
            return None


class OllamaProvider(LLMProvider):
    """Local Ollama Provider - Run models locally (Llama2, Mistral, Neural Chat, etc.)"""
    
    def __init__(self, model: str = "neural-chat", base_url: str = "http://localhost:11434"):
        super().__init__("Ollama")
        self.model = model
        self.base_url = base_url
        self.available = OLLAMA_AVAILABLE and self._check_connection()
        
        if self.available:
            logger.info(f"Ollama provider initialized with model: {model}")
        else:
            logger.warning(f"Ollama not available at {base_url}. Install: https://ollama.ai")
    
    def is_available(self) -> bool:
        return self.available
    
    def _check_connection(self) -> bool:
        """Check if Ollama is running"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 500, **kwargs) -> str:
        """Generate response using local Ollama model"""
        if not self.available:
            return None
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": temperature,
                    "stream": False
                },
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get("response", "")
            return None
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return None


class LocalConversationModel(LLMProvider):
    """Lightweight local conversation model using transformers (no API needed)"""
    
    def __init__(self):
        super().__init__("LocalConversation")
        self.available = False
        
        try:
            from transformers import pipeline
            # Load a lightweight conversation model
            self.pipe = pipeline("conversation", model="facebook/opt-125m", device=-1)
            self.available = True
            logger.info("LocalConversationModel initialized (facebook/opt-125m)")
        except ImportError:
            logger.warning("transformers not installed. Install: pip install transformers torch")
        except Exception as e:
            logger.warning(f"LocalConversationModel initialization failed: {e}")
    
    def is_available(self) -> bool:
        return self.available
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate response using local conversation model"""
        if not self.available:
            return None
        
        try:
            # Run conversation pipeline
            response = self.pipe(prompt)
            if response and len(response) > 0:
                return response[-1]['generated_text']
            return None
        except Exception as e:
            logger.error(f"LocalConversationModel error: {e}")
            return None


class HybridLLMEngine:
    """Hybrid LLM engine - uses templates first, then LLM fallback, with provider selection"""
    
    def __init__(self, mode: str = "hybrid", primary_provider: str = None):
        """
        Initialize hybrid LLM engine
        
        Args:
            mode: "template" (fast), "llm" (smart), "hybrid" (best of both)
            primary_provider: "openai", "anthropic", "ollama", "local", or None (auto-select)
        """
        self.mode = mode
        self.primary_provider = primary_provider
        
        # Initialize all available providers
        self.providers: Dict[str, LLMProvider] = {}
        
        # Try OpenAI
        if OPENAI_AVAILABLE:
            self.providers["openai"] = OpenAIProvider()
        
        # Try Anthropic
        if ANTHROPIC_AVAILABLE:
            self.providers["anthropic"] = AnthropicProvider()
        
        # Try Ollama
        if OLLAMA_AVAILABLE:
            self.providers["ollama"] = OllamaProvider()
        
        # Try Local model
        self.providers["local"] = LocalConversationModel()
        
        # Set active provider
        self.active_provider = self._select_provider()
        
        logger.info(f"HybridLLMEngine initialized in {mode} mode with provider: {self.active_provider.name if self.active_provider else 'None'}")
    
    def _select_provider(self) -> Optional[LLMProvider]:
        """Select best available provider based on priority"""
        # If primary specified, use it
        if self.primary_provider and self.primary_provider in self.providers:
            provider = self.providers[self.primary_provider]
            if provider.is_available():
                return provider
        
        # Priority order: local (no API cost) > ollama (local) > openai > anthropic
        priority = ["local", "ollama", "openai", "anthropic"]
        
        for name in priority:
            if name in self.providers and self.providers[name].is_available():
                return self.providers[name]
        
        return None
    
    def get_available_providers(self) -> List[str]:
        """Get list of available providers"""
        return [name for name, prov in self.providers.items() if prov.is_available()]
    
    def generate(self, prompt: str, use_llm: bool = None, **kwargs) -> str:
        """
        Generate response with hybrid logic
        
        Args:
            prompt: Input prompt
            use_llm: Override mode (True=use LLM, False=use template). None=use mode setting
            **kwargs: Provider-specific kwargs
        
        Returns:
            Generated response
        """
        # Determine if we should use LLM
        if use_llm is None:
            use_llm = self.mode in ["llm", "hybrid"]
        
        # In hybrid mode, only use LLM if available
        if self.mode == "hybrid" and not self.active_provider:
            return None  # No LLM available, return None for template fallback
        
        # If LLM requested and available
        if use_llm and self.active_provider:
            response = self.active_provider.generate(prompt, **kwargs)
            if response:
                return response
            # Fall back to None if LLM failed
            return None
        
        return None


# Export main class
__all__ = [
    "HybridLLMEngine",
    "OpenAIProvider",
    "AnthropicProvider", 
    "OllamaProvider",
    "LocalConversationModel",
    "LLMProvider"
]
