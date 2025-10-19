"""
Atulya Tantra - Configuration Management
Version: 2.5.0
Simplified configuration loading with environment variable support
"""

import os
import yaml
from typing import Optional, Dict, Any
from pathlib import Path


class Settings:
    """Application settings"""
    
    def __init__(self, config_dict: Dict[str, Any]):
        self.app_name = config_dict.get("app", {}).get("name", "Atulya Tantra")
        self.app_version = config_dict.get("app", {}).get("version", "2.5.0")
        self.environment = os.getenv("ENV", config_dict.get("app", {}).get("environment", "development"))
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        
        self.server_host = os.getenv("HOST", config_dict.get("server", {}).get("host", "0.0.0.0"))
        port_value = config_dict.get("server", {}).get("port", 8000)
        if isinstance(port_value, str) and port_value.startswith("${") and port_value.endswith("}"):
            # Extract default value from ${VAR:default} syntax
            default_value = port_value.split(":")[-1].rstrip("}")
            port_value = int(default_value)
        self.server_port = int(os.getenv("PORT", port_value))
        workers_value = config_dict.get("server", {}).get("workers", 1)
        if isinstance(workers_value, str) and workers_value.startswith("${") and workers_value.endswith("}"):
            default_value = workers_value.split(":")[-1].rstrip("}")
            workers_value = int(default_value)
        self.server_workers = int(os.getenv("WORKERS", workers_value))
        self.server_reload = os.getenv("RELOAD", "false").lower() == "true"
        
        # AI configuration
        self.ai = config_dict.get("ai", {})
        
        # Database configuration
        self.database = config_dict.get("database", {})
        
        # Cache configuration
        self.cache = config_dict.get("cache", {})
        
        # Security configuration
        self.security = config_dict.get("security", {})
        
        # Monitoring configuration
        self.monitoring = config_dict.get("monitoring", {})
        
        # Features configuration
        self.features = config_dict.get("features", {})


def merge_dicts(dict1: Dict, dict2: Dict) -> Dict:
    """Recursively merge two dictionaries"""
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> Settings:
    """Load and merge configuration from YAML and environment"""
    config_path = Path("config/config.yaml")
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path) as f:
        config_dict = yaml.safe_load(f)
    
    # Environment-specific overrides
    env = os.getenv("ENV", "development")
    env_config_path = Path(f"config/config.{env}.yaml")
    if env_config_path.exists():
        with open(env_config_path) as f:
            env_config = yaml.safe_load(f)
            config_dict = merge_dicts(config_dict, env_config)
    
    return Settings(config_dict)


# Global singleton
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get global settings instance"""
    global _settings
    if _settings is None:
        _settings = load_config()
    return _settings


def reload_settings() -> Settings:
    """Reload settings (useful for testing)"""
    global _settings
    _settings = load_config()
    return _settings