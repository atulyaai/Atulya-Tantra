"""
Anthropic Client for Atulya Tantra AGI
Anthropic API integration
"""

import requests
from typing import Dict, List, Any, Optional
from .llm_provider import LLMProvider

class AnthropicClient(LLMProvider):
    """Anthropic API client"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.name = "Anthropic"
        self.api_key = self.config.get('api_key', '')
        self.base_url = self.config.get('base_url', 'https://api.anthropic.com/v1')
        self.model = self.config.get('model', 'claude-3-sonnet-20240229')
    
    def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Anthropic API"""
        try:
            headers = {
                'x-api-key': self.api_key,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            }
            
            data = {
                'model': self.model,
                'max_tokens': kwargs.get('max_tokens', 100),
                'messages': [{'role': 'user', 'content': prompt}]
            }
            
            response = requests.post(
                f'{self.base_url}/messages',
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['content'][0]['text']
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    def is_available(self) -> bool:
        """Check if Anthropic API is available"""
        return bool(self.api_key)