"""
AI brain and LLM integrations for Atulya Tantra AGI
Multi-provider LLM system with streaming and fallback support
"""

from .llm_provider import (
    LLMProvider,
    OllamaProvider,
    OpenAIProvider,
    AnthropicProvider,
    LLMProviderRouter,
    get_llm_router,
    generate_response,
    count_tokens,
    get_provider_status
)
from .ollama_client import OllamaClient, get_ollama_client
from .openai_client import OpenAIClient, get_openai_client
from .anthropic_client import AnthropicClient, get_anthropic_client

__all__ = [
    # Base providers
    "LLMProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "LLMProviderRouter",
    
    # Enhanced clients
    "OllamaClient",
    "OpenAIClient", 
    "AnthropicClient",
    
    # Global instances
    "get_llm_router",
    "get_ollama_client",
    "get_openai_client",
    "get_anthropic_client",
    
    # Utility functions
    "generate_response",
    "count_tokens",
    "get_provider_status"
]

