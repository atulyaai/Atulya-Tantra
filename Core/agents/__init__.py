"""
Multi-agent system for Atulya Tantra AGI
Specialized agents for different tasks and capabilities
"""

from .base_agent import (
    AgentStatus,
    AgentCapability,
    AgentPriority,
    AgentTask,
    BaseAgent,
    AgentRegistry,
    AgentOrchestrator,
    get_orchestrator,
    submit_task,
    get_task_status,
    cancel_task
)
from .code_agent import CodeAgent
from .research_agent import ResearchAgent
from .creative_agent import CreativeAgent
from .data_agent import DataAgent
from .system_agent import SystemAgent

__all__ = [
    # Base framework
    "AgentStatus",
    "AgentCapability",
    "AgentPriority", 
    "AgentTask",
    "BaseAgent",
    "AgentRegistry",
    "AgentOrchestrator",
    
    # Specialized agents
    "CodeAgent",
    "ResearchAgent",
    "CreativeAgent",
    "DataAgent",
    "SystemAgent",
    
    # Orchestrator functions
    "get_orchestrator",
    "submit_task",
    "get_task_status",
    "cancel_task"
]

