"""
Atulya Tantra - AI Model Clients
Version: 2.5.0
Enhanced model clients for Ollama, OpenAI, and Anthropic
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import logging
import asyncio
import json

logger = logging.getLogger(__name__)


@dataclass
class ModelResponse:
    """Standardized model response"""
    content: str
    model: str
    provider: str
    usage: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ModelRequest:
    """Standardized model request"""
    messages: List[Dict[str, str]]
    model: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False


class BaseModelClient(ABC):
    """Base class for all model clients"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.base_url = config.get("base_url")
        self.api_key = config.get("api_key")
        self.models = config.get("models", {})
    
    @abstractmethod
    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate response from model"""
        pass
    
    @abstractmethod
    async def list_models(self) -> List[str]:
        """List available models"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if model client is healthy"""
        pass


class OllamaClient(BaseModelClient):
    """Ollama model client"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Ollama client"""
        try:
            import ollama
            self.client = ollama
            logger.info("Ollama client initialized successfully")
        except ImportError:
            logger.warning("Ollama not installed, client will be disabled")
            self.client = None
    
    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate response using Ollama"""
        if not self.client:
            raise RuntimeError("Ollama client not available")
        
        try:
            # Convert messages to Ollama format
            ollama_messages = []
            for msg in request.messages:
                ollama_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Generate response
            response = self.client.chat(
                model=request.model,
                messages=ollama_messages,
                options={
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens or 1000,
                    "top_p": 0.9,
                    "top_k": 40
                }
            )
            
            return ModelResponse(
                content=response["message"]["content"],
                model=request.model,
                provider="ollama",
                usage={
                    "prompt_tokens": response.get("prompt_eval_count", 0),
                    "completion_tokens": response.get("eval_count", 0),
                    "total_tokens": response.get("prompt_eval_count", 0) + response.get("eval_count", 0)
                },
                metadata={
                    "eval_duration": response.get("eval_duration", 0),
                    "load_duration": response.get("load_duration", 0),
                    "total_duration": response.get("total_duration", 0)
                }
            )
            
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise
    
    async def list_models(self) -> List[str]:
        """List available Ollama models"""
        if not self.client:
            return []
        
        try:
            models_response = self.client.list()
            return [model["name"] for model in models_response["models"]]
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []
    
    async def health_check(self) -> bool:
        """Check Ollama health"""
        if not self.client:
            return False
        
        try:
            # Try to list models as health check
            await self.list_models()
            return True
        except Exception:
            return False


class OpenAIClient(BaseModelClient):
    """OpenAI model client"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize OpenAI client"""
        if not self.api_key:
            logger.warning("OpenAI API key not provided, client will be disabled")
            return
        
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            logger.info("OpenAI client initialized successfully")
        except ImportError:
            logger.warning("OpenAI library not installed, client will be disabled")
            self.client = None
    
    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate response using OpenAI"""
        if not self.client:
            raise RuntimeError("OpenAI client not available")
        
        try:
            # Generate response
            response = await self.client.chat.completions.create(
                model=request.model,
                messages=request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=request.stream
            )
            
            return ModelResponse(
                content=response.choices[0].message.content,
                model=request.model,
                provider="openai",
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                metadata={
                    "finish_reason": response.choices[0].finish_reason,
                    "model": response.model
                }
            )
            
        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            raise
    
    async def list_models(self) -> List[str]:
        """List available OpenAI models"""
        if not self.client:
            return []
        
        try:
            models_response = await self.client.models.list()
            return [model.id for model in models_response.data]
        except Exception as e:
            logger.error(f"Failed to list OpenAI models: {e}")
            return []
    
    async def health_check(self) -> bool:
        """Check OpenAI health"""
        if not self.client:
            return False
        
        try:
            # Try to list models as health check
            await self.list_models()
            return True
        except Exception:
            return False


class AnthropicClient(BaseModelClient):
    """Anthropic model client"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Anthropic client"""
        if not self.api_key:
            logger.warning("Anthropic API key not provided, client will be disabled")
            return
        
        try:
            from anthropic import AsyncAnthropic
            self.client = AsyncAnthropic(
                api_key=self.api_key,
                base_url=self.base_url
            )
            logger.info("Anthropic client initialized successfully")
        except ImportError:
            logger.warning("Anthropic library not installed, client will be disabled")
            self.client = None
    
    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate response using Anthropic"""
        if not self.client:
            raise RuntimeError("Anthropic client not available")
        
        try:
            # Convert messages format for Anthropic
            system_msg = None
            anthropic_messages = []
            
            for msg in request.messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                else:
                    anthropic_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            
            # Generate response
            response = await self.client.messages.create(
                model=request.model,
                max_tokens=request.max_tokens or 1000,
                messages=anthropic_messages,
                system=system_msg or "You are a helpful AI assistant.",
                temperature=request.temperature
            )
            
            return ModelResponse(
                content=response.content[0].text,
                model=request.model,
                provider="anthropic",
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                },
                metadata={
                    "stop_reason": response.stop_reason,
                    "model": response.model
                }
            )
            
        except Exception as e:
            logger.error(f"Anthropic generation failed: {e}")
            raise
    
    async def list_models(self) -> List[str]:
        """List available Anthropic models"""
        if not self.client:
            return []
        
        try:
            # Anthropic doesn't have a models.list() endpoint
            # Return known models from config
            return list(self.models.keys())
        except Exception as e:
            logger.error(f"Failed to list Anthropic models: {e}")
            return []
    
    async def health_check(self) -> bool:
        """Check Anthropic health"""
        if not self.client:
            return False
        
        try:
            # Try a simple request as health check
            test_request = ModelRequest(
                messages=[{"role": "user", "content": "Hello"}],
                model=list(self.models.keys())[0] if self.models else "claude-3-haiku-20240307"
            )
            await self.generate(test_request)
            return True
        except Exception:
            return False


class ModelClientManager:
    """Manages all model clients and provides unified interface"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.clients: Dict[str, BaseModelClient] = {}
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize all available model clients"""
        
        # Initialize Ollama
        if "ollama" in self.config:
            try:
                self.clients["ollama"] = OllamaClient(self.config["ollama"])
                logger.info("Ollama client registered")
            except Exception as e:
                logger.warning(f"Failed to initialize Ollama client: {e}")
        
        # Initialize OpenAI
        if "openai" in self.config:
            try:
                self.clients["openai"] = OpenAIClient(self.config["openai"])
                logger.info("OpenAI client registered")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}")
        
        # Initialize Anthropic
        if "anthropic" in self.config:
            try:
                self.clients["anthropic"] = AnthropicClient(self.config["anthropic"])
                logger.info("Anthropic client registered")
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic client: {e}")
    
    async def generate(
        self,
        provider: str,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> ModelResponse:
        """Generate response using specified provider and model"""
        
        if provider not in self.clients:
            raise ValueError(f"Provider {provider} not available")
        
        client = self.clients[provider]
        
        request = ModelRequest(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return await client.generate(request)
    
    async def get_available_models(self) -> Dict[str, List[str]]:
        """Get all available models from all providers"""
        
        available_models = {}
        
        for provider, client in self.clients.items():
            try:
                models = await client.list_models()
                available_models[provider] = models
            except Exception as e:
                logger.warning(f"Failed to get models from {provider}: {e}")
                available_models[provider] = []
        
        return available_models
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all clients"""
        
        health_status = {}
        
        for provider, client in self.clients.items():
            try:
                health_status[provider] = await client.health_check()
            except Exception as e:
                logger.warning(f"Health check failed for {provider}: {e}")
                health_status[provider] = False
        
        return health_status
