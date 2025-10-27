"""
Atulya Tantra AGI - Dynamic System Module
Self-installing, self-evolving, and self-adapting system components
"""

from .installer import DynamicInstaller, ComponentManager
from .agent_factory import AgentFactory, DynamicAgent
from .function_discovery import FunctionDiscovery, AutoImporter
from .self_evolution import SelfEvolutionEngine, LearningSystem
from .auto_config import AutoConfigurator, EnvironmentDetector

__all__ = [
    "DynamicInstaller",
    "ComponentManager", 
    "AgentFactory",
    "DynamicAgent",
    "FunctionDiscovery",
    "AutoImporter",
    "SelfEvolutionEngine",
    "LearningSystem",
    "AutoConfigurator",
    "EnvironmentDetector"
]