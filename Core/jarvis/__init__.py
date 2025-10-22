"""
JARVIS Features for Atulya Tantra AGI
Personality engine, voice interface, and proactive assistance
"""

from .personality_engine import (
    PersonalityTrait,
    EmotionalState,
    ConversationContext,
    PersonalityEngine,
    ConversationalAI,
    get_conversational_ai,
    process_user_message,
    get_conversation_summary,
    reset_conversation
)
from .voice_interface import (
    VoiceInterface,
    VoiceAssistant,
    get_voice_assistant,
    start_voice_conversation,
    process_voice_command,
    test_voice_interface
)
from .proactive_assistance import (
    AssistanceType,
    AssistancePriority,
    ProactiveAssistance,
    ContextAwareAssistant,
    get_context_assistant,
    process_with_assistance,
    schedule_assistance,
    get_assistance_statistics
)

__all__ = [
    # Personality Engine
    "PersonalityTrait",
    "EmotionalState",
    "ConversationContext",
    "PersonalityEngine",
    "ConversationalAI",
    "get_conversational_ai",
    "process_user_message",
    "get_conversation_summary",
    "reset_conversation",
    
    # Voice Interface
    "VoiceInterface",
    "VoiceAssistant",
    "get_voice_assistant",
    "start_voice_conversation",
    "process_voice_command",
    "test_voice_interface",
    
    # Proactive Assistance
    "AssistanceType",
    "AssistancePriority",
    "ProactiveAssistance",
    "ContextAwareAssistant",
    "get_context_assistant",
    "process_with_assistance",
    "schedule_assistance",
    "get_assistance_statistics"
]

