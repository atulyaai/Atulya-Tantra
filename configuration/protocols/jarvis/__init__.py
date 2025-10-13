"""
JARVIS Protocol - Just A Rather Very Intelligent System
Core AI assistant functionality inspired by Iron Man's JARVIS
"""

from .interface import JarvisInterface
from .conversation import ConversationManager
from .personality import PersonalityEngine, EmotionalState

__all__ = [
    'JarvisInterface',
    'ConversationManager',
    'PersonalityEngine',
    'EmotionalState',
]

