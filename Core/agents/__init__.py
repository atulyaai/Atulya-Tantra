"""
Agents module for Atulya Tantra AGI
Specialized AI agents for different tasks
"""

from .base_agent import BaseAgent
from .code_agent import CodeAgent
from .creative_agent import CreativeAgent
from .data_agent import DataAgent
from .research_agent import ResearchAgent
from .system_agent import SystemAgent

__all__ = [
    'BaseAgent',
    'CodeAgent',
    'CreativeAgent', 
    'DataAgent',
    'ResearchAgent',
    'SystemAgent'
]