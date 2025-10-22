"""
LLM Provider
Unified interface for different language model providers
"""

import requests
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

class LLMProvider:
    """
    Unified interface for different language model providers
    Supports Ollama, OpenAI, and other LLM services
    """
    
    def __init__(self, provider: str = "ollama", config: Dict[str, Any] = None):
        self.provider = provider
        self.config = config or {}
        self.session = requests.Session()
        
        # Provider-specific configurations
        self.providers = {
            "ollama": {
                "base_url": "http://localhost:11434",
                "model": "gemma2:2b",
                "timeout": 30
            },
            "openai": {
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-3.5-turbo",
                "timeout": 30
            }
        }
        
        # Set up provider configuration
        if provider in self.providers:
            self.provider_config = self.providers[provider]
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def generate_response(self, message: str, context: List[Dict[str, Any]] = None, 
                         max_tokens: int = 150) -> str:
        """
        Generate response using the configured LLM provider
        """
        if self.provider == "ollama":
            return self._generate_ollama_response(message, context, max_tokens)
        elif self.provider == "openai":
            return self._generate_openai_response(message, context, max_tokens)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def _generate_ollama_response(self, message: str, context: List[Dict[str, Any]] = None, 
                                 max_tokens: int = 150) -> str:
        """
        Generate response using Ollama
        """
        try:
            # Build context-aware prompt
            prompt = self._build_ollama_prompt(message, context)
            
            response = self.session.post(
                f"{self.provider_config['base_url']}/api/generate",
                json={
                    'model': self.provider_config['model'],
                    'prompt': prompt,
                    'stream': False,
                    'options': {
                        'temperature': 0.3,
                        'max_tokens': max_tokens,
                        'num_predict': max_tokens
                    }
                },
                timeout=self.provider_config['timeout']
            )
            
            if response.status_code == 200:
                data = response.json()
                return data['response'].strip()
            else:
                return "I'm having trouble processing your request right now. Please try again."
        
        except Exception as e:
            print(f"Ollama error: {e}")
            return "I'm experiencing technical difficulties. Please try again later."
    
    def _generate_openai_response(self, message: str, context: List[Dict[str, Any]] = None, 
                                 max_tokens: int = 150) -> str:
        """
        Generate response using OpenAI API
        """
        try:
            # Build messages for OpenAI format
            messages = self._build_openai_messages(message, context)
            
            response = self.session.post(
                f"{self.provider_config['base_url']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.get('api_key', '')}",
                    "Content-Type": "application/json"
                },
                json={
                    'model': self.provider_config['model'],
                    'messages': messages,
                    'max_tokens': max_tokens,
                    'temperature': 0.3
                },
                timeout=self.provider_config['timeout']
            )
            
            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content'].strip()
            else:
                return "I'm having trouble processing your request right now. Please try again."
        
        except Exception as e:
            print(f"OpenAI error: {e}")
            return "I'm experiencing technical difficulties. Please try again later."
    
    def _build_ollama_prompt(self, message: str, context: List[Dict[str, Any]] = None) -> str:
        """
        Build context-aware prompt for Ollama
        """
        prompt = """You are a professional AI assistant. You are helpful, knowledgeable, and can assist with various tasks.

CAPABILITIES:
- System control (open/close applications, manage windows, control volume)
- Web searches and information retrieval
- Communication (emails, messages, notifications)
- Scheduling and calendar management
- General conversation and problem-solving

Be helpful, direct, and provide comprehensive information when asked about capabilities.

"""
        
        # Add conversation context if available
        if context:
            prompt += "Recent conversation:\n"
            for msg in context[-6:]:  # Last 6 messages
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                if role == 'user':
                    prompt += f"User: {content}\n"
                else:
                    prompt += f"Assistant: {content}\n"
            prompt += "\n"
        
        # Add current message
        prompt += f"User asks: {message}\n"
        prompt += "Assistant responds:"
        
        return prompt
    
    def _build_openai_messages(self, message: str, context: List[Dict[str, Any]] = None) -> List[Dict[str, str]]:
        """
        Build messages for OpenAI API format
        """
        messages = [
            {
                "role": "system",
                "content": "You are a professional AI assistant. You are helpful, knowledgeable, and can assist with various tasks including system control, web searches, communication, scheduling, and general conversation. Be helpful, direct, and provide comprehensive information when asked about capabilities."
            }
        ]
        
        # Add conversation context if available
        if context:
            for msg in context[-10:]:  # Last 10 messages
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                if role in ['user', 'assistant']:
                    messages.append({"role": role, "content": content})
        
        # Add current message
        messages.append({"role": "user", "content": message})
        
        return messages
    
    def test_connection(self) -> bool:
        """
        Test connection to the LLM provider
        """
        try:
            if self.provider == "ollama":
                response = self.session.get(f"{self.provider_config['base_url']}/api/tags", timeout=5)
                return response.status_code == 200
            elif self.provider == "openai":
                # Test with a simple request
                response = self.session.get(f"{self.provider_config['base_url']}/models", 
                                          headers={"Authorization": f"Bearer {self.config.get('api_key', '')}"}, 
                                          timeout=5)
                return response.status_code == 200
            return False
        except:
            return False
    
    def get_available_models(self) -> List[str]:
        """
        Get list of available models for the provider
        """
        try:
            if self.provider == "ollama":
                response = self.session.get(f"{self.provider_config['base_url']}/api/tags", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return [model['name'] for model in data.get('models', [])]
            elif self.provider == "openai":
                response = self.session.get(f"{self.provider_config['base_url']}/models",
                                          headers={"Authorization": f"Bearer {self.config.get('api_key', '')}"}, 
                                          timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return [model['id'] for model in data.get('data', [])]
            return []
        except:
            return []
    
    def set_model(self, model: str):
        """
        Set the model to use
        """
        self.provider_config['model'] = model
    
    def get_model(self) -> str:
        """
        Get the current model
        """
        return self.provider_config.get('model', '')
