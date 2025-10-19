"""
Atulya Tantra - Enhanced Model Client Manager
Version: 2.5.0
Unified interface for all AI model providers with real connections
"""

import asyncio
import aiohttp
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ModelResponse:
    """Model response data structure"""
    content: str
    usage: Optional[Dict] = None
    metadata: Optional[Dict] = None


class OllamaClient:
    """Ollama local model client"""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def generate(self, model: str, messages: List[Dict], **kwargs) -> ModelResponse:
        """Generate response using Ollama"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 1000)
                }
            }
            
            async with self.session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return ModelResponse(
                        content=data.get("message", {}).get("content", ""),
                        usage=data.get("usage"),
                        metadata={"provider": "ollama", "model": model}
                    )
                else:
                    error_text = await response.text()
                    raise Exception(f"Ollama API error {response.status}: {error_text}")
        
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            raise
    
    async def get_available_models(self) -> List[str]:
        """Get available Ollama models"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    return [model["name"] for model in data.get("models", [])]
                else:
                    return []
        except Exception as e:
            logger.error(f"Error getting Ollama models: {e}")
            return []
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Ollama health"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                return {
                    "status": "healthy" if response.status == 200 else "unhealthy",
                    "models_count": len(await self.get_available_models())
                }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


class OpenAIClient:
    """OpenAI API client"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1"
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def generate(self, model: str, messages: List[Dict], **kwargs) -> ModelResponse:
        """Generate response using OpenAI"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": messages,
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 1000)
            }
            
            async with self.session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return ModelResponse(
                        content=data["choices"][0]["message"]["content"],
                        usage=data.get("usage"),
                        metadata={"provider": "openai", "model": model}
                    )
                else:
                    error_text = await response.text()
                    raise Exception(f"OpenAI API error {response.status}: {error_text}")
        
        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            raise
    
    async def get_available_models(self) -> List[str]:
        """Get available OpenAI models"""
        return ["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"]
    
    async def health_check(self) -> Dict[str, Any]:
        """Check OpenAI health"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with self.session.get(f"{self.base_url}/models", headers=headers) as response:
                return {
                    "status": "healthy" if response.status == 200 else "unhealthy",
                    "models_count": len(await self.get_available_models())
                }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


class AnthropicClient:
    """Anthropic Claude API client"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1"
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def generate(self, model: str, messages: List[Dict], **kwargs) -> ModelResponse:
        """Generate response using Anthropic"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            headers = {
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            
            # Convert messages format for Anthropic
            system_message = ""
            user_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    user_messages.append(msg)
            
            payload = {
                "model": model,
                "max_tokens": kwargs.get("max_tokens", 1000),
                "temperature": kwargs.get("temperature", 0.7),
                "messages": user_messages
            }
            
            if system_message:
                payload["system"] = system_message
            
            async with self.session.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return ModelResponse(
                        content=data["content"][0]["text"],
                        usage=data.get("usage"),
                        metadata={"provider": "anthropic", "model": model}
                    )
                else:
                    error_text = await response.text()
                    raise Exception(f"Anthropic API error {response.status}: {error_text}")
        
        except Exception as e:
            logger.error(f"Anthropic generation error: {e}")
            raise
    
    async def get_available_models(self) -> List[str]:
        """Get available Anthropic models"""
        return ["claude-3-sonnet-20240229", "claude-3-haiku-20240307", "claude-3-opus-20240229"]
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Anthropic health"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            headers = {"x-api-key": self.api_key}
            async with self.session.get(f"{self.base_url}/messages", headers=headers) as response:
                return {
                    "status": "healthy" if response.status in [200, 400] else "unhealthy",
                    "models_count": len(await self.get_available_models())
                }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


class ModelClientManager:
    """Unified model client manager"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.clients = {}
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize all available clients"""
        try:
            # Ollama client
            ollama_config = self.config.get("ollama", {})
            if ollama_config:
                self.clients["ollama"] = OllamaClient(
                    base_url=ollama_config.get("base_url", "http://localhost:11434")
                )
            
            # OpenAI client
            openai_config = self.config.get("openai", {})
            if openai_config and openai_config.get("api_key"):
                self.clients["openai"] = OpenAIClient(
                    api_key=openai_config["api_key"]
                )
            
            # Anthropic client
            anthropic_config = self.config.get("anthropic", {})
            if anthropic_config and anthropic_config.get("api_key"):
                self.clients["anthropic"] = AnthropicClient(
                    api_key=anthropic_config["api_key"]
                )
        
        except Exception as e:
            logger.error(f"Error initializing model clients: {e}")
    
    async def generate(
        self,
        provider: str,
        model: str,
        messages: List[Dict],
        **kwargs
    ) -> ModelResponse:
        """Generate response using specified provider and model"""
        if provider not in self.clients:
            raise ValueError(f"Provider {provider} not available")
        
        client = self.clients[provider]
        async with client:
            return await client.generate(model, messages, **kwargs)
    
    async def get_available_models(self) -> Dict[str, List[str]]:
        """Get available models from all providers"""
        available_models = {}
        
        for provider, client in self.clients.items():
            try:
                async with client:
                    models = await client.get_available_models()
                    available_models[provider] = models
            except Exception as e:
                logger.error(f"Error getting models from {provider}: {e}")
                available_models[provider] = []
        
        return available_models
    
    async def health_check(self) -> Dict[str, Dict[str, Any]]:
        """Check health of all providers"""
        health_status = {}
        
        for provider, client in self.clients.items():
            try:
                async with client:
                    health_status[provider] = await client.health_check()
            except Exception as e:
                health_status[provider] = {"status": "unhealthy", "error": str(e)}
        
        return health_status
