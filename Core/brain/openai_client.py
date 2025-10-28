"""
OpenAI Client for Atulya Tantra AGI
OpenAI API integration
"""

import requests
from typing import Dict, List, Any, Optional
from .llm_provider import LLMProvider

class OpenAIClient(LLMProvider):
    """OpenAI API client"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.name = "OpenAI"
        self.api_key = self.config.get('api_key', '')
        self.base_url = self.config.get('base_url', 'https://api.openai.com/v1')
        self.model = self.config.get('model', 'gpt-3.5-turbo')
    
    def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using OpenAI API"""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': self.model,
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': kwargs.get('max_tokens', 100)
            }
            
            response = requests.post(
                f'{self.base_url}/chat/completions',
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    def is_available(self) -> bool:
        """Check if OpenAI API is available"""
        return bool(self.api_key)