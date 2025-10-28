"""
Settings for Atulya Tantra AGI
Configuration management
"""

import os
from typing import Dict, Any, Optional

class Settings:
    """Application settings"""
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from environment and defaults"""
        return {
            'ai_provider': os.getenv('PRIMARY_AI_PROVIDER', 'ollama'),
            'ollama_url': os.getenv('OLLAMA_URL', 'http://localhost:11434'),
            'ollama_model': os.getenv('OLLAMA_MODEL', 'gemma2:2b'),
            'openai_api_key': os.getenv('OPENAI_API_KEY', ''),
            'anthropic_api_key': os.getenv('ANTHROPIC_API_KEY', ''),
            'voice_enabled': os.getenv('VOICE_ENABLED', 'true').lower() == 'true',
            'autonomous_operations': os.getenv('AUTONOMOUS_OPERATIONS', 'false').lower() == 'true',
            'streaming_enabled': os.getenv('STREAMING_ENABLED', 'true').lower() == 'true'
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set configuration value"""
        self.config[key] = value