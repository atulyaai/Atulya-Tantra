"""
Dynamic Configuration Loader
Loads configuration based on environment with validation
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging

from .constants import (
    PROJECT_ROOT,
    DEFAULT_ENVIRONMENT,
    DEFAULT_MODELS,
    GENERATION_PARAMS,
    DEFAULT_SYSTEM_PROMPT
)

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Load and manage configuration with environment support"""
    
    def __init__(self, config_path: Optional[str] = None, environment: Optional[str] = None):
        """
        Initialize configuration loader
        
        Args:
            config_path: Path to config file (default: config.yaml in project root)
            environment: Environment name (default: from TANTRA_ENV or 'production')
        """
        self.config_path = Path(config_path) if config_path else PROJECT_ROOT / "config.yaml"
        self.environment = environment or DEFAULT_ENVIRONMENT
        self._config = None
        self._load_config()
    
    def _load_config(self):
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                self._config = yaml.safe_load(f)
            logger.info(f"✓ Configuration loaded from {self.config_path}")
        except FileNotFoundError:
            logger.warning(f"Config file not found: {self.config_path}. Using defaults.")
            self._config = self._get_default_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}. Using defaults.")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "model": {
                "name": DEFAULT_MODELS["text_fast"],
                "device": "cpu",
                "dtype": "auto",
                "max_memory": "60GB"
            },
            "generation": GENERATION_PARAMS["fast"],
            "speech_to_text": {
                "model_size": "small",
                "language": "en",
                "device": "cpu",
                "compute_type": "int8",
                "sample_rate": 16000,
                "vad_enabled": True,
                "vad_threshold": 0.5
            },
            "text_to_speech": {
                "engine": "piper",
                "voice": "en_US-lessac-medium",
                "speaking_rate": 1.0,
                "volume": 0.8
            },
            "wake_word": {
                "enabled": True,
                "keyword": "hey_atulya",
                "sensitivity": 0.5
            },
            "audio": {
                "sample_rate": 16000,
                "channels": 1,
                "chunk_size": 1024,
                "mic_device_index": None,
                "speaker_device_index": None
            },
            "conversation": {
                "max_history": 10,
                "max_images_in_context": 5,
                "context_window": 8000
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key (supports dot notation)
        
        Args:
            key: Configuration key (e.g., 'model.name' or 'generation.temperature')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_model_config(self) -> Dict[str, Any]:
        """Get model configuration"""
        return self._config.get('model', {})
    
    def get_generation_config(self) -> Dict[str, Any]:
        """Get generation parameters"""
        return self._config.get('generation', {})
    
    def get_model_name(self) -> str:
        """Get model name with environment variable override"""
        return os.getenv('MODEL_NAME', self.get('model.name', DEFAULT_MODELS["text_fast"]))
    
    def get_device(self) -> str:
        """Get device with environment variable override"""
        return os.getenv('DEVICE', self.get('model.device', 'cpu'))
    
    def get_max_tokens(self) -> int:
        """Get max tokens for generation"""
        return self.get('generation.max_tokens', 128)
    
    def get_temperature(self) -> float:
        """Get temperature for generation"""
        return self.get('generation.temperature', 0.6)
    
    def get_system_prompt(self) -> str:
        """Get system prompt"""
        return self.get('system_prompt', DEFAULT_SYSTEM_PROMPT)
    
    def reload(self):
        """Reload configuration from file"""
        self._load_config()
    
    def __repr__(self):
        return f"ConfigLoader(environment={self.environment}, config_path={self.config_path})"


# Global config instance
_config_instance: Optional[ConfigLoader] = None


def get_config(config_path: Optional[str] = None, environment: Optional[str] = None) -> ConfigLoader:
    """
    Get global configuration instance (singleton pattern)
    
    Args:
        config_path: Path to config file (only used on first call)
        environment: Environment name (only used on first call)
        
    Returns:
        ConfigLoader instance
    """
    global _config_instance
    
    if _config_instance is None:
        _config_instance = ConfigLoader(config_path, environment)
    
    return _config_instance


def reload_config():
    """Reload global configuration"""
    global _config_instance
    if _config_instance:
        _config_instance.reload()
