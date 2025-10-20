"""
Atulya Tantra - Core Agents
Version: 2.5.0
Flattened agent modules for JARVIS, Skynet, and specialized agents
"""

from .agent_coordinator import AgentCoordinator

# Conversational AI Layer
from .conversational_personality import PersonalityEngine
from .conversational_memory import ConversationalMemory
from .conversational_nlu import NaturalLanguageUnderstanding
from .conversational_assistant import TaskAssistant
from .conversational_knowledge import KnowledgeManager
from .conversational_voice import ConversationalVoiceInterface

# System Automation Layer
from .system_control import SystemController
from .system_automation import DesktopAutomation
from .system_scheduler import TaskScheduler
from .system_monitor import SystemMonitor
from .system_healer import AutoHealer
from .system_decision_engine import DecisionEngine
from .system_coordinator import MultiAgentCoordinator
from .system_executor import TaskExecutor, task_executor
from .system_safety import SafetySystem, safety_system

# Specialized Agents
from .specialized.base_agent import BaseAgent
from .specialized.code_agent import CodeAgent
from .specialized.research_agent import ResearchAgent
from .specialized.creative_agent import CreativeAgent
from .specialized.data_agent import DataAgent

__all__ = [
    # Core
    "AgentCoordinator",
    
    # Conversational AI
    "PersonalityEngine",
    "ConversationalMemory", 
    "NaturalLanguageUnderstanding",
    "TaskAssistant",
    "KnowledgeManager",
    "ConversationalVoiceInterface",
    
    # System Automation
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