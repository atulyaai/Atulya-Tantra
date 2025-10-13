"""
Atulya Tantra - Configuration Module
Centralized configuration and settings management
"""

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

__all__ = [
    'settings',
    'Settings',
    'get_prompt',
    'list_available_prompts',
    'JARVIS_CORE_PROMPT',
    'SKYNET_ORCHESTRATOR_PROMPT',
    'AGENT_CONVERSATION',
    'AGENT_CODE',
    'AGENT_RESEARCH',
    'AGENT_TASK_PLANNER',
]
