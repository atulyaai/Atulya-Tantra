"""
Atulya Tantra - Unified Configuration System
Version: 2.0.1
This module provides a unified configuration system that loads settings from
multiple sources and provides a single interface for accessing configuration.
"""

import os
import yaml
import json
from pathlib import Path
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass, field
from functools import lru_cache

@dataclass
class Config:
    """Unified configuration class"""
    
    # System settings
    system_name: str = "Atulya Tantra"
    system_version: str = "2.0.1"
    debug: bool = False
    log_level: str = "INFO"
    
    # Server settings
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    cors_origins: list = field(default_factory=lambda: ["http://localhost:8000"])
    
    # AI Model settings
    default_model_provider: str = "openai"
    default_model: str = "gpt-4"
    model_temperature: float = 0.7
    model_max_tokens: int = 4096
    
    # Voice settings
    wake_word_enabled: bool = True
    wake_word_phrase: str = "hey jarvis"
    stt_provider: str = "openai"
    tts_provider: str = "edge"
    
    # Security settings
    jwt_secret: str = ""
    encryption_key: str = ""
    two_factor_enabled: bool = True
    
    # Database settings
    database_url: str = "sqlite:///./data/database/atulya_tantra.db"
    
    # Cache settings
    redis_url: str = "redis://localhost:6379/0"
    cache_enabled: bool = True
    
    # Feature flags
    features: Dict[str, bool] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize default feature flags"""
        if not self.features:
            self.features = {
                "voice_interface": True,
                "desktop_control": True,
                "vision_capabilities": True,
                "multi_agent_system": True,
                "real_time_analytics": True,
                "advanced_security": True,
                "caching": True,
                "monitoring": True,
                "testing": True
            }

class ConfigLoader:
    """Configuration loader with support for multiple sources"""
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path(__file__).parent
        self._config_cache: Optional[Config] = None
    
    def load_config(self, reload: bool = False) -> Config:
        """Load configuration from all sources"""
        if self._config_cache is not None and not reload:
            return self._config_cache
        
        config = Config()
        
        # Load from YAML file
        yaml_config = self._load_yaml_config()
        if yaml_config:
            self._merge_config(config, yaml_config)
        
        # Load from environment variables
        env_config = self._load_env_config()
        if env_config:
            self._merge_config(config, env_config)
        
        # Load from .env file
        env_file_config = self._load_env_file()
        if env_file_config:
            self._merge_config(config, env_file_config)
        
        self._config_cache = config
        return config
    
    def _load_yaml_config(self) -> Optional[Dict[str, Any]]:
        """Load configuration from YAML file"""
        yaml_file = self.config_dir / "config.yaml"
        if not yaml_file.exists():
            return None
        
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Failed to load YAML config: {e}")
            return None
    
    def _load_env_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables"""
        config = {}
        
        # Map environment variables to config keys
        env_mapping = {
            "ATULYA_DEBUG": ("debug", bool),
            "ATULYA_LOG_LEVEL": ("log_level", str),
            "ATULYA_SERVER_HOST": ("server_host", str),
            "ATULYA_SERVER_PORT": ("server_port", int),
            "ATULYA_DATABASE_URL": ("database_url", str),
            "ATULYA_REDIS_URL": ("redis_url", str),
            "ATULYA_JWT_SECRET": ("jwt_secret", str),
            "ATULYA_ENCRYPTION_KEY": ("encryption_key", str),
            "OPENAI_API_KEY": ("openai_api_key", str),
            "ANTHROPIC_API_KEY": ("anthropic_api_key", str),
            "GOOGLE_API_KEY": ("google_api_key", str),
        }
        
        for env_var, (config_key, config_type) in env_mapping.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    if config_type == bool:
                        config[config_key] = value.lower() in ('true', '1', 'yes', 'on')
                    elif config_type == int:
                        config[config_key] = int(value)
                    else:
                        config[config_key] = value
                except ValueError:
                    print(f"Warning: Invalid value for {env_var}: {value}")
        
        return config
    
    def _load_env_file(self) -> Dict[str, Any]:
        """Load configuration from .env file"""
        env_file = Path.cwd() / ".env"
        if not env_file.exists():
            return {}
        
        config = {}
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')
                        config[key.lower()] = value
        except Exception as e:
            print(f"Warning: Failed to load .env file: {e}")
        
        return config
    
    def _merge_config(self, config: Config, source_config: Dict[str, Any]) -> None:
        """Merge source configuration into config object"""
        for key, value in source_config.items():
            if hasattr(config, key):
                setattr(config, key, value)
            elif key == "system":
                if isinstance(value, dict):
                    for sys_key, sys_value in value.items():
                        attr_name = f"system_{sys_key}"
                        if hasattr(config, attr_name):
                            setattr(config, attr_name, sys_value)
            elif key == "server":
                if isinstance(value, dict):
                    for srv_key, srv_value in value.items():
                        attr_name = f"server_{srv_key}"
                        if hasattr(config, attr_name):
                            setattr(config, attr_name, srv_value)
            elif key == "features":
                if isinstance(value, dict):
                    config.features.update(value)

@lru_cache(maxsize=1)
def get_config() -> Config:
    """Get cached configuration instance"""
    loader = ConfigLoader()
    return loader.load_config()

def reload_config() -> Config:
    """Reload configuration from all sources"""
    loader = ConfigLoader()
    return loader.load_config(reload=True)

def get_setting(key: str, default: Any = None) -> Any:
    """Get a specific setting value"""
    config = get_config()
    return getattr(config, key, default)

def is_feature_enabled(feature: str) -> bool:
    """Check if a feature is enabled"""
    config = get_config()
    return config.features.get(feature, False)

def get_model_config(provider: str) -> Dict[str, Any]:
    """Get model configuration for a specific provider"""
    config = get_config()
    
    # Default model configurations
    model_configs = {
        "openai": {
            "api_key": os.getenv("OPENAI_API_KEY"),
            "base_url": "https://api.openai.com/v1",
            "models": ["gpt-4", "gpt-3.5-turbo"],
            "default_model": "gpt-4"
        },
        "anthropic": {
            "api_key": os.getenv("ANTHROPIC_API_KEY"),
            "base_url": "https://api.anthropic.com",
            "models": ["claude-3-opus-20240229", "claude-3-sonnet-20240229"],
            "default_model": "claude-3-sonnet-20240229"
        },
        "google": {
            "api_key": os.getenv("GOOGLE_API_KEY"),
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "models": ["gemini-pro"],
            "default_model": "gemini-pro"
        },
        "ollama": {
            "base_url": "http://localhost:11434",
            "models": ["llama2", "mistral"],
            "default_model": "llama2"
        }
    }
    
    return model_configs.get(provider, {})

def get_database_config() -> Dict[str, Any]:
    """Get database configuration"""
    config = get_config()
    return {
        "url": config.database_url,
        "echo": config.debug,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
        "pool_recycle": 3600
    }

def get_cache_config() -> Dict[str, Any]:
    """Get cache configuration"""
    config = get_config()
    return {
        "redis_url": config.redis_url,
        "enabled": config.cache_enabled,
        "timeout": 5,
        "max_connections": 10
    }

def get_security_config() -> Dict[str, Any]:
    """Get security configuration"""
    config = get_config()
    return {
        "jwt_secret": config.jwt_secret,
        "encryption_key": config.encryption_key,
        "two_factor_enabled": config.two_factor_enabled,
        "max_login_attempts": 5,
        "lockout_duration": 900
    }

# Convenience functions for common settings
def is_debug() -> bool:
    """Check if debug mode is enabled"""
    return get_setting("debug", False)

def get_log_level() -> str:
    """Get log level"""
    return get_setting("log_level", "INFO")

def get_server_host() -> str:
    """Get server host"""
    return get_setting("server_host", "0.0.0.0")

def get_server_port() -> int:
    """Get server port"""
    return get_setting("server_port", 8000)

def get_database_url() -> str:
    """Get database URL"""
    return get_setting("database_url", "sqlite:///./data/database/atulya_tantra.db")

# Export main functions
__all__ = [
    "Config",
    "ConfigLoader", 
    "get_config",
    "reload_config",
    "get_setting",
    "is_feature_enabled",
    "get_model_config",
    "get_database_config",
    "get_cache_config",
    "get_security_config",
    "is_debug",
    "get_log_level",
    "get_server_host",
    "get_server_port",
    "get_database_url"
]
