"""
Atulya Tantra - Unified Configuration System
Version: 2.0.1
Centralized configuration management for the AGI system
"""

# Import unified configuration system
from .unified_config import (
    Config,
    ConfigLoader,
    get_config,
    reload_config,
    get_setting,
    is_feature_enabled,
    get_model_config,
    get_database_config,
    get_cache_config,
    get_security_config,
    is_debug,
    get_log_level,
    get_server_host,
    get_server_port,
    get_database_url
)

# Import legacy modules for backward compatibility
from .settings import settings, Settings
from .prompts import (
    get_prompt,
    list_available_prompts,
    JARVIS_CORE_PROMPT,
    SKYNET_ORCHESTRATOR_PROMPT,
    AGENT_CONVERSATION,
    AGENT_CODE,
    AGENT_RESEARCH,
    AGENT_TASK_PLANNER,
)
from .protocol_configs import (
    ProtocolConfig,
    JARVIS_CONFIG,
    SKYNET_CONFIG,
    AGENT_CONFIGS,
    get_protocol_config,
    get_agent_config,
    list_protocols,
    list_agents,
)
from .protocols import (
    JarvisInterface,
    ConversationManager,
    PersonalityEngine,
    EmotionalState,
    SkynetOrchestrator,
    BaseAgent,
    AgentType,
)

# Export unified configuration as default
__all__ = [
    # Unified configuration
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
    "get_database_url",
    
    # Legacy exports
    "settings",
    "Settings",
    "get_prompt",
    "list_available_prompts",
    "JARVIS_CORE_PROMPT",
    "SKYNET_ORCHESTRATOR_PROMPT",
    "AGENT_CONVERSATION",
    "AGENT_CODE",
    "AGENT_RESEARCH",
    "AGENT_TASK_PLANNER",
    "ProtocolConfig",
    "JARVIS_CONFIG",
    "SKYNET_CONFIG",
    "AGENT_CONFIGS",
    "get_protocol_config",
    "get_agent_config",
    "list_protocols",
    "list_agents",
    "JarvisInterface",
    "ConversationManager",
    "PersonalityEngine",
    "EmotionalState",
    "SkynetOrchestrator",
    "BaseAgent",
    "AgentType",
]
