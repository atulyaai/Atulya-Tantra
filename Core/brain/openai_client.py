"""
OpenAI client for Atulya Tantra AGI
GPT-4, GPT-4-turbo, and GPT-4V integration with streaming
"""

from typing import Dict, List, Any, Optional, AsyncGenerator, Union
import json
import time

from .llm_provider import OpenAIProvider
from ..config.settings import settings
from ..config.logging import get_logger

logger = get_logger(__name__)


class OpenAIClient(OpenAIProvider):
    """Enhanced OpenAI client with additional features"""
    
    def __init__(self):
        super().__init__()
        self.available_models = []
        self.model_capabilities: Dict[str, Dict[str, Any]] = {}
    
    async def list_models(self) -> List[str]:
        """List available OpenAI models"""
        if not self.is_available:
            return []
        
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=self.api_key)
            
            models = await client.models.list()
            self.available_models = [model.id for model in models.data]
            
            return self.available_models
            
        except Exception as e:
            logger.error(f"Error listing OpenAI models: {e}")
            return []
    
    async def get_model_capabilities(self, model: str = None) -> Dict[str, Any]:
        """Get capabilities of a specific model"""
        model = model or self.model
        
        # Define known capabilities
        capabilities = {
            "gpt-4": {
                "max_tokens": 8192,
                "supports_vision": False,
                "supports_function_calling": True,
                "supports_streaming": True,
                "context_window": 8192
            },
            "gpt-4-turbo": {
                "max_tokens": 4096,
                "supports_vision": False,
                "supports_function_calling": True,
                "supports_streaming": True,
                "context_window": 128000
            },
            "gpt-4-vision-preview": {
                "max_tokens": 4096,
                "supports_vision": True,
                "supports_function_calling": True,
                "supports_streaming": True,
                "context_window": 128000
            },
            "gpt-3.5-turbo": {
                "max_tokens": 4096,
                "supports_vision": False,
                "supports_function_calling": True,
                "supports_streaming": True,
                "context_window": 16384
            }
        }
        
        return capabilities.get(model, {
            "max_tokens": 4096,
            "supports_vision": False,
            "supports_function_calling": False,
            "supports_streaming": True,
            "context_window": 4096
        })
    
    async def generate_with_vision(
        self, 
        text_prompt: str,
        image_urls: List[str],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Generate response with vision capabilities"""
        
        if not self.is_available:
            raise ModelNotAvailableError(self.provider_name, self.model)
        
        # Check if model supports vision
        capabilities = await self.get_model_capabilities()
        if not capabilities.get("supports_vision", False):
            raise AIProviderError(self.provider_name, f"Model {self.model} does not support vision")
        
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=self.api_key)
            
            # Prepare messages with images
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": text_prompt}
                    ]
                }
            ]
            
            # Add images to the message
            for image_url in image_urls:
                messages[0]["content"].append({
                    "type": "image_url",
                    "image_url": {"url": image_url}
                })
            
            if stream:
                return self._stream_openai_response(client, messages, max_tokens, temperature)
            else:
                response = await client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                
                return response.choices[0].message.content.strip()
                
        except Exception as e:
            raise AIProviderError(self.provider_name, str(e))
    
    async def generate_with_functions(
        self, 
        prompt: str,
        functions: List[Dict[str, Any]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stream: bool = False
    ) -> Union[str, Dict[str, Any]]:
        """Generate response with function calling capabilities"""
        
        if not self.is_available:
            raise ModelNotAvailableError(self.provider_name, self.model)
        
        # Check if model supports function calling
        capabilities = await self.get_model_capabilities()
        if not capabilities.get("supports_function_calling", False):
            raise AIProviderError(self.provider_name, f"Model {self.model} does not support function calling")
        
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=self.api_key)
            
            messages = [{"role": "user", "content": prompt}]
            
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                functions=functions,
                function_call="auto",
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            message = response.choices[0].message
            
            # Check if function was called
            if message.function_call:
                return {
                    "type": "function_call",
                    "function_name": message.function_call.name,
                    "arguments": json.loads(message.function_call.arguments)
                }
            else:
                return {
                    "type": "text",
                    "content": message.content.strip()
                }
                
        except Exception as e:
            raise AIProviderError(self.provider_name, str(e))
    
    async def generate_with_conversation(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Generate response with conversation history"""
        
        if not self.is_available:
            raise ModelNotAvailableError(self.provider_name, self.model)
        
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=self.api_key)
            
            if stream:
                return self._stream_openai_response(client, messages, max_tokens, temperature)
            else:
                response = await client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                
                return response.choices[0].message.content.strip()
                
        except Exception as e:
            raise AIProviderError(self.provider_name, str(e))
    
    async def create_embedding(self, text: str, model: str = "text-embedding-ada-002") -> List[float]:
        """Create embedding for text"""
        if not self.is_available:
            raise ModelNotAvailableError(self.provider_name, self.model)
        
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=self.api_key)
            
            response = await client.embeddings.create(
                model=model,
                input=text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            raise AIProviderError(self.provider_name, f"Embedding error: {e}")
    
    async def create_embeddings_batch(self, texts: List[str], model: str = "text-embedding-ada-002") -> List[List[float]]:
        """Create embeddings for multiple texts"""
        if not self.is_available:
            raise ModelNotAvailableError(self.provider_name, self.model)
        
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=self.api_key)
            
            response = await client.embeddings.create(
                model=model,
                input=texts
            )
            
            return [data.embedding for data in response.data]
            
        except Exception as e:
            raise AIProviderError(self.provider_name, f"Batch embedding error: {e}")
    
    async def moderate_content(self, text: str) -> Dict[str, Any]:
        """Moderate content using OpenAI's moderation API"""
        if not self.is_available:
            raise ModelNotAvailableError(self.provider_name, self.model)
        
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=self.api_key)
            
            response = await client.moderations.create(input=text)
            
            return {
                "flagged": response.results[0].flagged,
                "categories": response.results[0].categories,
                "category_scores": response.results[0].category_scores
            }
            
        except Exception as e:
            raise AIProviderError(self.provider_name, f"Moderation error: {e}")


# Global OpenAI client instance
_openai_client: Optional[OpenAIClient] = None


async def get_openai_client() -> OpenAIClient:
    """Get global OpenAI client instance"""
    global _openai_client
    
    if _openai_client is None:
        _openai_client = OpenAIClient()
        await _openai_client.check_availability()
    
    return _openai_client


# Export public API
__all__ = [
    "OpenAIClient",
    "get_openai_client"
]
