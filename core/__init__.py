"""
Atulya Tantra - Core Module
Version: 2.0.1
Foundation utilities and base components for the AGI system
"""

from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Import key components
from .config import GlobalConfig, get_config, reload_config
from .logger import get_logger
from .exceptions import *
from .utils import *
from .base import BaseProtocol, BaseAgent, BaseManager
from .memory import *
from .monitoring import *
from .version import *

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
    
    # Memory Management
    'Memory',
    'KnowledgeNode',
    'VectorStore',
    'KnowledgeGraph',
    'MemoryManager',
    'PreferenceLearning',
    'get_memory_manager',
    'get_vector_store',
    'get_knowledge_graph',
    'get_preference_learning',
    
    # Monitoring
    'Metric',
    'HealthStatus',
    'MetricsCollector',
    'HealthChecker',
    'ContextMonitor',
    'MonitoringSystem',
    'get_metrics_collector',
    'get_health_checker',
    'get_context_monitor',
    'get_monitoring_system',
    
    # Version Management
    'VersionType',
    'VersionInfo',
    'VersionManager',
    'get_version_manager',
    'get_current_version',
    'get_version_info',
    'get_changelog',
    'get_roadmap',
    'get_release_notes'
]
