"""
Atulya Tantra - Global Configuration Manager
Centralized configuration for entire system
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class GlobalConfig:
    """
    Global configuration for Atulya Tantra
    Single source of truth for all settings
    """
    
    # Version Info
    version: str = "1.0.2"
    codename: str = "JARVIS"
    
    # AI Model Settings
    default_model: str = field(default_factory=lambda: os.getenv("DEFAULT_MODEL", "phi3:mini"))
    temperature: float = field(default_factory=lambda: float(os.getenv("TEMPERATURE", "0.7")))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("MAX_TOKENS", "4096")))
    
    # Voice Settings
    wake_word: str = field(default_factory=lambda: os.getenv("WAKE_WORD", "atulya"))
    tts_voice: str = field(default_factory=lambda: os.getenv("TTS_VOICE", "en-US-AriaNeural"))
    
    # System Settings
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    
    # Paths
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    data_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent / "data")
    logs_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent / "logs")
    
    # Ollama Settings
    ollama_host: str = field(default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    
    def __post_init__(self):
        """Ensure directories exist"""
        self.data_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'version': self.version,
            'codename': self.codename,
            'default_model': self.default_model,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'wake_word': self.wake_word,
            'tts_voice': self.tts_voice,
            'debug': self.debug,
            'log_level': self.log_level,
            'ollama_host': self.ollama_host,
        }


# Global singleton instance
_global_config: Optional[GlobalConfig] = None


def get_config() -> GlobalConfig:
    """
    Get global configuration instance (singleton)
    
    Returns:
        GlobalConfig instance
    """
    global _global_config
    if _global_config is None:
        _global_config = GlobalConfig()
    return _global_config


def reload_config() -> GlobalConfig:
    """
    Reload configuration from environment
    
    Returns:
        New GlobalConfig instance
    """
    global _global_config
    _global_config = GlobalConfig()
    return _global_config


__all__ = ['GlobalConfig', 'get_config', 'reload_config']

