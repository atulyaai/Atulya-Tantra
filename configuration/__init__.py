"""
Atulya Tantra - Configuration Module
Centralized configuration: settings, prompts, and protocols
"""

# Settings
from .settings import settings, Settings

# Prompts
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

# Protocol configurations
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

# Protocol implementations
from .protocols import (
    JarvisInterface,
    ConversationManager,
    PersonalityEngine,
    EmotionalState,
    SkynetOrchestrator,
    BaseAgent,
    AgentType,
)

__all__ = [
    # Settings
    'settings',
    'Settings',
    
    # Prompts
    'get_prompt',
    'list_available_prompts',
    'JARVIS_CORE_PROMPT',
    'SKYNET_ORCHESTRATOR_PROMPT',
    'AGENT_CONVERSATION',
    'AGENT_CODE',
    'AGENT_RESEARCH',
    'AGENT_TASK_PLANNER',
    
    # Protocol configurations
    'ProtocolConfig',
    'JARVIS_CONFIG',
    'SKYNET_CONFIG',
    'AGENT_CONFIGS',
    'get_protocol_config',
    'get_agent_config',
    'list_protocols',
    'list_agents',
    
    # Protocol implementations
    'JarvisInterface',
    'ConversationManager',
    'PersonalityEngine',
    'EmotionalState',
    'SkynetOrchestrator',
    'BaseAgent',
    'AgentType',
]
