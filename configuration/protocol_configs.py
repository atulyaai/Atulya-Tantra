"""
Atulya Tantra - Protocol Configurations
Centralized configuration for JARVIS, SKYNET, and all protocols
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class ProtocolConfig:
    """Base configuration for protocols"""
    name: str
    enabled: bool = True
    settings: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.settings is None:
            self.settings = {}


# ============================================================================
# JARVIS PROTOCOL CONFIGURATION
# ============================================================================

JARVIS_CONFIG = ProtocolConfig(
    name="JARVIS",
    enabled=True,
    settings={
        "max_conversation_history": 50,
        "emotion_detection": True,
        "personality_adaptation": True,
        "context_aware": True,
        "response_brevity": "adaptive",  # adaptive, brief, detailed
    }
)


# ============================================================================
# SKYNET PROTOCOL CONFIGURATION
# ============================================================================

SKYNET_CONFIG = ProtocolConfig(
    name="SKYNET",
    enabled=True,
    settings={
        "max_agents": 10,
        "task_timeout": 300,  # seconds
        "parallel_execution": True,
        "auto_routing": True,
        "fallback_agent": "conversation",
    }
)


# ============================================================================
# AGENT CONFIGURATIONS
# ============================================================================

AGENT_CONFIGS = {
    "conversation": {
        "model": "gemma2:2b",
        "max_tokens": 20,
        "temperature": 0.7,
        "system_prompt_key": "conversation"
    },
    "code": {
        "model": "gemma2:2b",
        "max_tokens": 200,
        "temperature": 0.5,
        "system_prompt_key": "code"
    },
    "research": {
        "model": "gemma2:2b",
        "max_tokens": 200,
        "temperature": 0.6,
        "system_prompt_key": "research"
    },
    "task_planner": {
        "model": "gemma2:2b",
        "max_tokens": 150,
        "temperature": 0.6,
        "system_prompt_key": "task_planner"
    }
}


# ============================================================================
# PROTOCOL UTILITIES
# ============================================================================

def get_protocol_config(protocol_name: str) -> Optional[ProtocolConfig]:
    """
    Get protocol configuration by name
    
    Args:
        protocol_name: Name of protocol (jarvis, skynet)
        
    Returns:
        ProtocolConfig or None
    """
    configs = {
        "jarvis": JARVIS_CONFIG,
        "skynet": SKYNET_CONFIG,
    }
    return configs.get(protocol_name.lower())


def get_agent_config(agent_type: str) -> Optional[Dict[str, Any]]:
    """
    Get agent configuration by type
    
    Args:
        agent_type: Type of agent
        
    Returns:
        Agent configuration dict or None
    """
    return AGENT_CONFIGS.get(agent_type.lower())


def list_protocols() -> list:
    """List available protocols"""
    return ["jarvis", "skynet"]


def list_agents() -> list:
    """List available agent types"""
    return list(AGENT_CONFIGS.keys())


__all__ = [
    'ProtocolConfig',
    'JARVIS_CONFIG',
    'SKYNET_CONFIG',
    'AGENT_CONFIGS',
    'get_protocol_config',
    'get_agent_config',
    'list_protocols',
    'list_agents',
]

