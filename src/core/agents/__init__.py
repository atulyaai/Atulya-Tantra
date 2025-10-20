"""
Atulya Tantra - Core Agents
Version: 2.5.0
Flattened agent modules for JARVIS, Skynet, and specialized agents
"""

from .agent_coordinator import AgentCoordinator

# JARVIS Intelligence Layer
from .jarvis_personality import PersonalityEngine
from .jarvis_memory import ConversationalMemory
from .jarvis_nlu import NaturalLanguageUnderstanding
from .jarvis_assistant import TaskAssistant
from .jarvis_knowledge import KnowledgeManager
from .jarvis_voice import JARVISVoiceInterface

# Skynet Autonomous Operations
from .skynet_system_control import SystemController
from .skynet_automation import DesktopAutomation
from .skynet_scheduler import TaskScheduler
from .skynet_monitor import SystemMonitor
from .skynet_healer import AutoHealer
from .skynet_decision_engine import DecisionEngine
from .skynet_coordinator import MultiAgentCoordinator
from .skynet_executor import TaskExecutor, task_executor
from .skynet_safety import SafetySystem, safety_system

# Specialized Agents
from .base_agent import BaseAgent
from .code_agent import CodeAgent
from .research_agent import ResearchAgent
from .creative_agent import CreativeAgent
from .data_agent import DataAgent

__all__ = [
    # Core
    "AgentCoordinator",
    
    # JARVIS Intelligence
    "PersonalityEngine",
    "ConversationalMemory", 
    "NaturalLanguageUnderstanding",
    "TaskAssistant",
    "KnowledgeManager",
    "JARVISVoiceInterface",
    
    # Skynet Autonomous Operations
    "SystemController",
    "DesktopAutomation",
    "TaskScheduler", 
    "SystemMonitor",
    "AutoHealer",
    "DecisionEngine",
    "MultiAgentCoordinator",
    "TaskExecutor",
    "task_executor",
    "SafetySystem",
    "safety_system",
    
    # Specialized Agents
    "BaseAgent",
    "CodeAgent",
    "ResearchAgent",
    "CreativeAgent", 
    "DataAgent"
]