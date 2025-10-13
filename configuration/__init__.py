"""
Atulya Tantra - Configuration Module
Centralized configuration, settings, and prompts
"""

from .settings import settings, Settings
from .prompts import (
    get_prompt,
    list_available_prompts,
    # Protocol prompts
    JARVIS_CORE_PROMPT,
    SKYNET_ORCHESTRATOR_PROMPT,
    # Agent prompts
    AGENT_CONVERSATION,
    AGENT_CODE,
    AGENT_RESEARCH,
    AGENT_TASK_PLANNER,
    # System prompts
    MCP_SYSTEM_PROMPT,
    SENTIMENT_ANALYSIS_PROMPT,
    MEMORY_SYSTEM_PROMPT,
    VOICE_SYSTEM_PROMPT,
)

__all__ = [
    # Settings
    'settings',
    'Settings',
    
    # Prompt utilities
    'get_prompt',
    'list_available_prompts',
    
    # Protocol prompts
    'JARVIS_CORE_PROMPT',
    'SKYNET_ORCHESTRATOR_PROMPT',
    
    # Agent prompts  
    'AGENT_CONVERSATION',
    'AGENT_CODE',
    'AGENT_RESEARCH',
    'AGENT_TASK_PLANNER',
    
    # System prompts
    'MCP_SYSTEM_PROMPT',
    'SENTIMENT_ANALYSIS_PROMPT',
    'MEMORY_SYSTEM_PROMPT',
    'VOICE_SYSTEM_PROMPT',
]
