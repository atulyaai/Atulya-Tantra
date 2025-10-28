"""
Atulya Tantra AGI - Core Module
Main AGI system components
"""

from .agi_core import AGICore
from .assistant_core import AssistantCore
from .unified_agi_system import UnifiedAGISystem

__all__ = [
    'AGICore',
    'AssistantCore', 
    'UnifiedAGISystem'
]

__version__ = "3.0.0"