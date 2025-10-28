"""
Ollama Client for Atulya Tantra AGI
Ollama local LLM integration
"""

import requests
from typing import Dict, List, Any, Optional
from .llm_provider import LLMProvider

class OllamaClient(LLMProvider):
    """Ollama local LLM client"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.name = "Ollama"
        self.base_url = self.config.get('base_url', 'http://localhost:11434')
        self.model = self.config.get('model', 'gemma2:2b')
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Ollama"""
        try:
            data = {
                'model': self.model,
                'prompt': prompt,
                'stream': False,
                'options': {
                    'temperature': kwargs.get('temperature', 0.7),
                    'max_tokens': kwargs.get('max_tokens', 100)
                }
            }
            
            response = requests.post(
                f'{self.base_url}/api/generate',
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', 'No response generated')
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    async def is_available(self) -> bool:
        """Check if Ollama is available"""
        try:
            response = requests.get(f'{self.base_url}/api/tags', timeout=5)
            return response.status_code == 200
        except:
            return False