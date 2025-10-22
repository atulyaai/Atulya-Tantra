"""
Anthropic client for Atulya Tantra AGI
Claude 3.5 Sonnet, Claude 3 Opus integration with streaming
"""

from typing import Dict, List, Any, Optional, AsyncGenerator, Union
import json
import time

from .llm_provider import AnthropicProvider
from ..config.settings import settings
from ..config.logging import get_logger

logger = get_logger(__name__)


class AnthropicClient(AnthropicProvider):
    """Enhanced Anthropic client with additional features"""
    
    def __init__(self):
        super().__init__()
        self.available_models = []
        self.model_capabilities: Dict[str, Dict[str, Any]] = {}
    
    async def list_models(self) -> List[str]:
        """List available Anthropic models"""
        if not self.is_available:
            return []
        
        # Anthropic doesn't have a public models list API
        # Return known models
        known_models = [
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-2.1",
            "claude-2.0",
            "claude-instant-1.2"
        ]
        
        self.available_models = known_models
        return known_models
    
    async def get_model_capabilities(self, model: str = None) -> Dict[str, Any]:
        """Get capabilities of a specific model"""
        model = model or self.model
        
        # Define known capabilities
        capabilities = {
            "claude-3-5-sonnet-20241022": {
                "max_tokens": 8192,
                "supports_vision": True,
                "supports_streaming": True,
                "context_window": 200000,
                "supports_tools": True
            },
            "claude-3-opus-20240229": {
                "max_tokens": 4096,
                "supports_vision": True,
                "supports_streaming": True,
                "context_window": 200000,
                "supports_tools": True
            },
            "claude-3-sonnet-20240229": {
                "max_tokens": 4096,
                "supports_vision": True,
                "supports_streaming": True,
                "context_window": 200000,
                "supports_tools": True
            },
            "claude-3-haiku-20240307": {
                "max_tokens": 4096,
                "supports_vision": True,
                "supports_streaming": True,
                "context_window": 200000,
                "supports_tools": True
            },
            "claude-2.1": {
                "max_tokens": 4096,
                "supports_vision": False,
                "supports_streaming": True,
                "context_window": 200000,
                "supports_tools": False
            },
            "claude-2.0": {
                "max_tokens": 4096,
                "supports_vision": False,
                "supports_streaming": True,
                "context_window": 100000,
                "supports_tools": False
            }
        }
        
        return capabilities.get(model, {
            "max_tokens": 4096,
            "supports_vision": False,
            "supports_streaming": True,
            "context_window": 100000,
            "supports_tools": False
        })
    
    async def generate_with_vision(
        self, 
        text_prompt: str,
        image_data: str,  # Base64 encoded image
        media_type: str = "image/jpeg",
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
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            
            # Prepare messages with image
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": text_prompt},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data
                            }
                        }
                    ]
                }
            ]
            
            if stream:
                return self._stream_anthropic_response(client, messages, max_tokens, temperature)
            else:
                response = await client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=messages
                )
                
                return response.content[0].text.strip()
                
        except Exception as e:
            raise AIProviderError(self.provider_name, str(e))
    
    async def generate_with_tools(
        self, 
        prompt: str,
        tools: List[Dict[str, Any]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stream: bool = False
    ) -> Union[str, Dict[str, Any]]:
        """Generate response with tool calling capabilities"""
        
        if not self.is_available:
            raise ModelNotAvailableError(self.provider_name, self.model)
        
        # Check if model supports tools
        capabilities = await self.get_model_capabilities()
        if not capabilities.get("supports_tools", False):
            raise AIProviderError(self.provider_name, f"Model {self.model} does not support tools")
        
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            
            messages = [{"role": "user", "content": prompt}]
            
            response = await client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
                tools=tools
            )
            
            message = response.content[0]
            
            # Check if tool was used
            if hasattr(message, 'type') and message.type == 'tool_use':
                return {
                    "type": "tool_use",
                    "tool_name": message.name,
                    "tool_id": message.id,
                    "arguments": message.input
                }
            else:
                return {
                    "type": "text",
                    "content": message.text.strip()
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
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            
            if stream:
                return self._stream_anthropic_response(client, messages, max_tokens, temperature)
            else:
                response = await client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=messages
                )
                
                return response.content[0].text.strip()
                
        except Exception as e:
            raise AIProviderError(self.provider_name, str(e))
    
    async def generate_with_system_prompt(
        self, 
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Generate response with system prompt"""
        
        if not self.is_available:
            raise ModelNotAvailableError(self.provider_name, self.model)
        
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            
            messages = [{"role": "user", "content": user_prompt}]
            
            if stream:
                return self._stream_anthropic_response(client, messages, max_tokens, temperature, system_prompt)
            else:
                response = await client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=messages,
                    system=system_prompt
                )
                
                return response.content[0].text.strip()
                
        except Exception as e:
            raise AIProviderError(self.provider_name, str(e))
    
    async def _stream_anthropic_response(
        self, 
        client, 
        messages, 
        max_tokens, 
        temperature, 
        system: str = None
    ) -> AsyncGenerator[str, None]:
        """Stream response from Anthropic with optional system prompt"""
        try:
            kwargs = {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages
            }
            
            if system:
                kwargs["system"] = system
            
            async with client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
                    
        except Exception as e:
            raise AIProviderError(self.provider_name, f"Streaming error: {e}")


# Global Anthropic client instance
_anthropic_client: Optional[AnthropicClient] = None


async def get_anthropic_client() -> AnthropicClient:
    """Get global Anthropic client instance"""
    global _anthropic_client
    
    if _anthropic_client is None:
        _anthropic_client = AnthropicClient()
        await _anthropic_client.check_availability()
    
    return _anthropic_client


# Export public API
__all__ = [
    "AnthropicClient",
    "get_anthropic_client"
]
