"""
Ollama client for Atulya Tantra AGI
Enhanced local AI integration with streaming support
"""

from typing import Dict, List, Any, Optional, AsyncGenerator
import json
import asyncio
import time

from .llm_provider import OllamaProvider
from ..config.settings import settings
from ..config.logging import get_logger

logger = get_logger(__name__)


class OllamaClient(OllamaProvider):
    """Enhanced Ollama client with additional features"""
    
    def __init__(self):
        super().__init__()
        self.model_loaded = False
        self.model_info: Optional[Dict[str, Any]] = None
    
    async def load_model(self, model: str = None) -> bool:
        """Pre-load a model for faster responses"""
        model = model or self.model
        
        try:
            import httpx
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Generate a simple response to load the model
                payload = {
                    "model": model,
                    "prompt": "Hello",
                    "stream": False,
                    "options": {"num_predict": 1}
                }
                
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                )
                
                if response.status_code == 200:
                    self.model_loaded = True
                    logger.info(f"Model {model} loaded successfully")
                    return True
                else:
                    logger.error(f"Failed to load model {model}: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error loading model {model}: {e}")
            return False
    
    async def get_model_info(self, model: str = None) -> Optional[Dict[str, Any]]:
        """Get information about a model"""
        model = model or self.model
        
        try:
            import httpx
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/show",
                    json={"model": model}
                )
                
                if response.status_code == 200:
                    self.model_info = response.json()
                    return self.model_info
                else:
                    logger.error(f"Failed to get model info: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting model info: {e}")
            return None
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """List all available models"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("models", [])
                else:
                    logger.error(f"Failed to list models: {response.text}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return []
    
    async def pull_model(self, model: str) -> bool:
        """Pull/download a model"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=300) as client:  # Longer timeout for downloads
                response = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": model},
                    timeout=300
                )
                
                if response.status_code == 200:
                    logger.info(f"Model {model} pulled successfully")
                    return True
                else:
                    logger.error(f"Failed to pull model {model}: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error pulling model {model}: {e}")
            return False
    
    async def generate_with_context(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Generate response with conversation context"""
        
        # Convert messages to Ollama format
        context = ""
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            
            if role == "user":
                context += f"Human: {content}\n"
            elif role == "assistant":
                context += f"Assistant: {content}\n"
            elif role == "system":
                context += f"System: {content}\n"
        
        context += "Assistant:"
        
        return await self.generate_response(context, max_tokens, temperature, stream)
    
    async def generate_with_system_prompt(
        self, 
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Generate response with system prompt"""
        
        full_prompt = f"System: {system_prompt}\n\nHuman: {user_prompt}\n\nAssistant:"
        
        return await self.generate_response(full_prompt, max_tokens, temperature, stream)
    
    async def keep_alive(self) -> None:
        """Keep the model loaded by sending periodic requests"""
        while True:
            try:
                if self.model_loaded:
                    await self.generate_response("ping", max_tokens=1)
                await asyncio.sleep(60)  # Ping every minute
            except Exception as e:
                logger.warning(f"Keep alive ping failed: {e}")
                await asyncio.sleep(30)  # Retry sooner on failure


# Global Ollama client instance
_ollama_client: Optional[OllamaClient] = None


async def get_ollama_client() -> OllamaClient:
    """Get global Ollama client instance"""
    global _ollama_client
    
    if _ollama_client is None:
        _ollama_client = OllamaClient()
        await _ollama_client.check_availability()
        
        # Start keep-alive task if model is available
        if _ollama_client.is_available:
            asyncio.create_task(_ollama_client.keep_alive())
    
    return _ollama_client


# Export public API
__all__ = [
    "OllamaClient",
    "get_ollama_client"
]
