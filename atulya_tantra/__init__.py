"""
Atulya Tantra - Voice AI System
Main package initialization
"""

# Core components
from .core import TantraEngine
from .text_ai import TextAI
from .conversation_manager import ConversationManager
from .memory import MemoryManager
from .memory_extractor import MemoryExtractor

# Tools
from .mcp_client import MCPClient
from .tools import (
    PriceChecker,
    KnowledgeCache,
    IntelligentRouter,
    SearchEngine
)

# Voice I/O
from .voice_input import VoiceInput
from .voice_output import VoiceOutput

# Configuration and utilities
from .config_loader import get_config, ConfigLoader
from .constants import *
from .utils import setup_logging

__version__ = "2.0.0"

__all__ = [
    # Core
    "TantraEngine",
    "TextAI",
    "ConversationManager",
    "MemoryManager",
    "MemoryExtractor",
    # Tools
    "MCPClient",
    "PriceChecker",
    "KnowledgeCache",
    "IntelligentRouter",
    "SearchEngine",
    # Voice
    "VoiceInput",
    "VoiceOutput",
    # Config
    "get_config",
    "ConfigLoader",
    "setup_logging",
]

# Package metadata
__author__ = "Atulya Tantra Team"
__description__ = "Multimodal AI Assistant with Vision, Voice, and Text"
