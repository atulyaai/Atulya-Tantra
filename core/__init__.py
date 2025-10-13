"""
Atulya Tantra - Core Module
Foundation utilities and base components
"""

__version__ = "1.0.2"
__codename__ = "JARVIS"

from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Import key components
from .config import GlobalConfig, get_config, reload_config
from .logger import get_logger
from .exceptions import *
from .utils import *
from .base import BaseProtocol, BaseAgent, BaseManager

__all__ = [
    # Version info
    '__version__',
    '__codename__',
    'PROJECT_ROOT',
    
    # Configuration
    'GlobalConfig',
    'get_config',
    'reload_config',
    
    # Logging
    'get_logger',
    
    # Exceptions
    'AtulyaException',
    'ModelException',
    'ConfigurationException',
    'VoiceException',
    'AgentException',
    'MCPException',
    'MemoryException',
    'NetworkException',
    'SecurityException',
    
    # Base Classes
    'BaseProtocol',
    'BaseAgent',
    'BaseManager',
    
    # Utilities (from utils)
    'get_project_root',
    'get_system_info',
    'format_uptime',
    'ensure_directory',
    'Timer',
]
