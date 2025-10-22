"""
Multi-provider LLM integration for Atulya Tantra AGI
Supports Ollama, OpenAI, and Anthropic with streaming and fallback
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, AsyncGenerator, Union
from datetime import datetime
import json
import asyncio
import time

from ..config.settings import settings, AIProvider, get_ai_provider_config
from ..config.exceptions import AIProviderError, ModelNotAvailableError, TokenLimitExceededError, AIProviderTimeoutError
from ..config.logging import get_logger, log_llm_call


logger = get_logger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.config = get_ai_provider_config(AIProvider(provider_name))
        self.is_available = False
    
    @abstractmethod
    async def check_availability(self) -> bool:
        """Check if the provider is available"""
        pass
    
    @abstractmethod
    async def generate_response(
        self, 
        prompt: str, 
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Generate a response from the LLM"""
        pass
    
    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        pass
    
    def get_model_name(self) -> str:
        """Get the model name being used"""
        return self.config.get("model", "unknown")


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider"""
    
    def __init__(self):
        super().__init__("ollama")
        self.base_url = self.config["base_url"]
        self.model = self.config["model"]
        self.timeout = self.config["timeout"]
    
    async def check_availability(self) -> bool:
        """Check if Ollama is running and model is available"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [model["name"] for model in models]
                    self.is_available = self.model in model_names
                    return self.is_available
                return False
        except Exception as e:
            logger.warning(f"Ollama availability check failed: {e}")
            self.is_available = False
            return False
    
    async def generate_response(
        self, 
        prompt: str, 
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Generate response from Ollama"""
        if not self.is_available:
            await self.check_availability()
        
        if not self.is_available:
            raise ModelNotAvailableError(self.provider_name, self.model)
        
        start_time = time.time()
        
        try:
            import httpx
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": stream,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                        "stop": ["</s>", "Human:", "Assistant:"]
                    }
                }
                
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                )
                
                if response.status_code != 200:
                    raise AIProviderError(self.provider_name, f"HTTP {response.status_code}: {response.text}")
                
                if stream:
                    return self._stream_response(response)
                else:
                    data = response.json()
                    response_text = data.get("response", "").strip()
                    
                    # Log the call
                    duration_ms = (time.time() - start_time) * 1000
                    tokens_used = await self.count_tokens(prompt + response_text)
                    log_llm_call(logger, self.provider_name, self.model, tokens_used, duration_ms)
                    
                    return response_text
                    
        except asyncio.TimeoutError:
            raise AIProviderTimeoutError(self.provider_name, self.timeout)
        except Exception as e:
            raise AIProviderError(self.provider_name, str(e))
    
    async def _stream_response(self, response) -> AsyncGenerator[str, None]:
        """Stream response from Ollama"""
        try:
            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        data = json.loads(line)
                        if "response" in data:
                            yield data["response"]
                        if data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            raise AIProviderError(self.provider_name, f"Streaming error: {e}")
    
    async def count_tokens(self, text: str) -> int:
        """Estimate token count for Ollama (rough approximation)"""
        # Simple approximation: ~4 characters per token
        return len(text) // 4


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider"""
    
    def __init__(self):
        super().__init__("openai")
        self.api_key = self.config["api_key"]
        self.model = self.config["model"]
        self.max_tokens = self.config["max_tokens"]
        self.temperature = self.config["temperature"]
        
        if not self.api_key:
            self.is_available = False
        else:
            self.is_available = True
    
    async def check_availability(self) -> bool:
        """Check if OpenAI API is accessible"""
        if not self.api_key:
            return False
        
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=self.api_key)
            
            # Test with a simple request
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            
            self.is_available = True
            return True
            
        except Exception as e:
            logger.warning(f"OpenAI availability check failed: {e}")
            self.is_available = False
            return False
    
    async def generate_response(
        self, 
        prompt: str, 
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Generate response from OpenAI"""
        if not self.is_available:
            raise ModelNotAvailableError(self.provider_name, self.model)
        
        # Check token limits
        estimated_tokens = await self.count_tokens(prompt)
        if estimated_tokens + max_tokens > self.max_tokens:
            raise TokenLimitExceededError(self.provider_name, estimated_tokens + max_tokens, self.max_tokens)
        
        start_time = time.time()
        
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=self.api_key)
            
            messages = [{"role": "user", "content": prompt}]
            
            if stream:
                return self._stream_openai_response(client, messages, max_tokens, temperature)
            else:
                response = await client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                
                response_text = response.choices[0].message.content.strip()
                
                # Log the call
                duration_ms = (time.time() - start_time) * 1000
                tokens_used = response.usage.total_tokens
                log_llm_call(logger, self.provider_name, self.model, tokens_used, duration_ms)
                
                return response_text
                
        except Exception as e:
            raise AIProviderError(self.provider_name, str(e))
    
    async def _stream_openai_response(self, client, messages, max_tokens, temperature) -> AsyncGenerator[str, None]:
        """Stream response from OpenAI"""
        try:
            stream = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            raise AIProviderError(self.provider_name, f"Streaming error: {e}")
    
    async def count_tokens(self, text: str) -> int:
        """Count tokens using OpenAI's tiktoken"""
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model(self.model)
            return len(encoding.encode(text))
        except ImportError:
            # Fallback approximation if tiktoken not available
            return len(text) // 4
        except Exception:
            return len(text) // 4


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider"""
    
    def __init__(self):
        super().__init__("anthropic")
        self.api_key = self.config["api_key"]
        self.model = self.config["model"]
        self.max_tokens = self.config["max_tokens"]
        self.temperature = self.config["temperature"]
        
        if not self.api_key:
            self.is_available = False
        else:
            self.is_available = True
    
    async def check_availability(self) -> bool:
        """Check if Anthropic API is accessible"""
        if not self.api_key:
            return False
        
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            
            # Test with a simple request
            response = await client.messages.create(
                model=self.model,
                max_tokens=5,
                messages=[{"role": "user", "content": "Hello"}]
            )
            
            self.is_available = True
            return True
            
        except Exception as e:
            logger.warning(f"Anthropic availability check failed: {e}")
            self.is_available = False
            return False
    
    async def generate_response(
        self, 
        prompt: str, 
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Generate response from Anthropic"""
        if not self.is_available:
            raise ModelNotAvailableError(self.provider_name, self.model)
        
        # Check token limits
        estimated_tokens = await self.count_tokens(prompt)
        if estimated_tokens + max_tokens > self.max_tokens:
            raise TokenLimitExceededError(self.provider_name, estimated_tokens + max_tokens, self.max_tokens)
        
        start_time = time.time()
        
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            
            if stream:
                return self._stream_anthropic_response(client, prompt, max_tokens, temperature)
            else:
                response = await client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                response_text = response.content[0].text.strip()
                
                # Log the call
                duration_ms = (time.time() - start_time) * 1000
                tokens_used = response.usage.input_tokens + response.usage.output_tokens
                log_llm_call(logger, self.provider_name, self.model, tokens_used, duration_ms)
                
                return response_text
                
        except Exception as e:
            raise AIProviderError(self.provider_name, str(e))
    
    async def _stream_anthropic_response(self, client, prompt, max_tokens, temperature) -> AsyncGenerator[str, None]:
        """Stream response from Anthropic"""
        try:
            async with client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                    
        except Exception as e:
            raise AIProviderError(self.provider_name, f"Streaming error: {e}")
    
    async def count_tokens(self, text: str) -> int:
        """Count tokens using Anthropic's tokenizer"""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            return client.count_tokens(text)
        except Exception:
            # Fallback approximation
            return len(text) // 4


class LLMProviderRouter:
    """Router for managing multiple LLM providers with fallback"""
    
    def __init__(self):
        self.providers: Dict[str, LLMProvider] = {}
        self.primary_provider = settings.primary_ai_provider
        self.fallback_chain = [AIProvider.OLLAMA, AIProvider.OPENAI, AIProvider.ANTHROPIC]
        
        # Initialize providers
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize all available providers"""
        self.providers["ollama"] = OllamaProvider()
        self.providers["openai"] = OpenAIProvider()
        self.providers["anthropic"] = AnthropicProvider()
    
    async def check_all_providers(self) -> Dict[str, bool]:
        """Check availability of all providers"""
        results = {}
        for name, provider in self.providers.items():
            results[name] = await provider.check_availability()
        return results
    
    async def get_available_provider(self, preferred: Optional[str] = None) -> Optional[LLMProvider]:
        """Get an available provider, preferring the specified one"""
        preferred = preferred or self.primary_provider
        
        # Try preferred provider first
        if preferred in self.providers:
            provider = self.providers[preferred]
            if await provider.check_availability():
                return provider
        
        # Try fallback chain
        for provider_name in self.fallback_chain:
            if provider_name in self.providers:
                provider = self.providers[provider_name]
                if await provider.check_availability():
                    logger.info(f"Using fallback provider: {provider_name}")
                    return provider
        
        return None
    
    async def generate_response(
        self, 
        prompt: str, 
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stream: bool = False,
        preferred_provider: Optional[str] = None
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Generate response using available provider"""
        provider = await self.get_available_provider(preferred_provider)
        
        if not provider:
            raise AIProviderError("all", "No LLM providers available")
        
        try:
            return await provider.generate_response(prompt, max_tokens, temperature, stream)
        except Exception as e:
            logger.error(f"Provider {provider.provider_name} failed: {e}")
            
            # Try fallback providers
            for provider_name in self.fallback_chain:
                if provider_name != provider.provider_name and provider_name in self.providers:
                    fallback_provider = self.providers[provider_name]
                    if await fallback_provider.check_availability():
                        logger.info(f"Trying fallback provider: {provider_name}")
                        try:
                            return await fallback_provider.generate_response(prompt, max_tokens, temperature, stream)
                        except Exception as fallback_error:
                            logger.error(f"Fallback provider {provider_name} also failed: {fallback_error}")
                            continue
            
            # All providers failed
            raise AIProviderError("all", f"All providers failed. Last error: {e}")
    
    async def count_tokens(self, text: str, provider_name: Optional[str] = None) -> int:
        """Count tokens using specified provider or primary provider"""
        provider_name = provider_name or self.primary_provider
        
        if provider_name in self.providers:
            provider = self.providers[provider_name]
            if await provider.check_availability():
                return await provider.count_tokens(text)
        
        # Fallback to any available provider
        provider = await self.get_available_provider()
        if provider:
            return await provider.count_tokens(text)
        
        # Ultimate fallback
        return len(text) // 4


# Global provider router instance
_provider_router: Optional[LLMProviderRouter] = None


async def get_llm_router() -> LLMProviderRouter:
    """Get global LLM provider router"""
    global _provider_router
    
    if _provider_router is None:
        _provider_router = LLMProviderRouter()
        await _provider_router.check_all_providers()
    
    return _provider_router


async def generate_response(
    prompt: str, 
    max_tokens: int = 1000,
    temperature: float = 0.7,
    stream: bool = False,
    preferred_provider: Optional[str] = None
) -> Union[str, AsyncGenerator[str, None]]:
    """Generate response using the best available provider"""
    router = await get_llm_router()
    return await router.generate_response(prompt, max_tokens, temperature, stream, preferred_provider)


async def count_tokens(text: str, provider_name: Optional[str] = None) -> int:
    """Count tokens in text"""
    router = await get_llm_router()
    return await router.count_tokens(text, provider_name)


async def get_provider_status() -> Dict[str, Any]:
    """Get status of all providers"""
    router = await get_llm_router()
    availability = await router.check_all_providers()
    
    status = {
        "primary_provider": settings.primary_ai_provider,
        "providers": {}
    }
    
    for name, provider in router.providers.items():
        status["providers"][name] = {
            "available": availability.get(name, False),
            "model": provider.get_model_name(),
            "config": provider.config
        }
    
    return status


# Export public API
__all__ = [
    "LLMProvider",
    "OllamaProvider",
    "OpenAIProvider", 
    "AnthropicProvider",
    "LLMProviderRouter",
    "get_llm_router",
    "generate_response",
    "count_tokens",
    "get_provider_status"
]
