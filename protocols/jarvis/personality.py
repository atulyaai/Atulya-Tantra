"""
JARVIS Protocol - Personality Engine
Manages AI personality, emotional intelligence, and response adaptation
"""

from typing import Dict, Any, Optional
from enum import Enum
from core.logger import get_logger

logger = get_logger('protocols.jarvis.personality')


class EmotionalState(Enum):
    """Emotional states for personality adaptation"""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    CONCERNED = "concerned"
    SUPPORTIVE = "supportive"
    ENTHUSIASTIC = "enthusiastic"
    PROFESSIONAL = "professional"


class PersonalityEngine:
    """
    JARVIS Personality Engine
    
    Manages emotional intelligence and personality traits
    Adapts responses based on user emotion and context
    """
    
    def __init__(self):
        """Initialize personality engine"""
        self.current_state = EmotionalState.NEUTRAL
        self.user_emotion = "neutral"
        self.traits = {
            'warmth': 0.8,
            'professionalism': 0.9,
            'enthusiasm': 0.7,
            'empathy': 0.85,
            'humor': 0.5
        }
        
        logger.info("JARVIS Personality Engine initialized")
    
    def detect_emotion(self, text: str) -> str:
        """
        Detect emotion from user text
        
        Args:
            text: User input text
            
        Returns:
            Detected emotion
        """
        text_lower = text.lower()
        
        # Simple rule-based emotion detection
        # TODO: Implement ML-based emotion detection in Phase 2
        
        if any(word in text_lower for word in ['happy', 'great', 'excellent', 'wonderful', 'love']):
            return 'happy'
        elif any(word in text_lower for word in ['sad', 'upset', 'worried', 'concerned', 'anxious']):
            return 'sad'
        elif any(word in text_lower for word in ['angry', 'frustrated', 'annoyed', 'mad']):
            return 'angry'
        elif any(word in text_lower for word in ['help', 'please', 'need', 'urgent']):
            return 'needs_help'
        else:
            return 'neutral'
    
    def adapt_response_tone(self, emotion: str) -> EmotionalState:
        """
        Adapt personality state based on detected emotion
        
        Args:
            emotion: Detected user emotion
            
        Returns:
            Appropriate emotional state
        """
        emotion_map = {
            'happy': EmotionalState.ENTHUSIASTIC,
            'sad': EmotionalState.SUPPORTIVE,
            'angry': EmotionalState.PROFESSIONAL,
            'needs_help': EmotionalState.CONCERNED,
            'neutral': EmotionalState.NEUTRAL
        }
        
        self.current_state = emotion_map.get(emotion, EmotionalState.NEUTRAL)
        logger.debug(f"Personality adapted to: {self.current_state.value}")
        
        return self.current_state
    
    def get_response_modifiers(self) -> Dict[str, Any]:
        """
        Get response modifiers based on current personality state
        
        Returns:
            Dictionary of response modifiers
        """
        modifiers = {
            EmotionalState.NEUTRAL: {
                'tone': 'professional and helpful',
                'brevity': 'balanced',
                'warmth': 0.7
            },
            EmotionalState.HAPPY: {
                'tone': 'enthusiastic and warm',
                'brevity': 'slightly verbose',
                'warmth': 0.9
            },
            EmotionalState.CONCERNED: {
                'tone': 'attentive and supportive',
                'brevity': 'detailed',
                'warmth': 0.85
            },
            EmotionalState.SUPPORTIVE: {
                'tone': 'empathetic and caring',
                'brevity': 'patient',
                'warmth': 0.95
            },
            EmotionalState.ENTHUSIASTIC: {
                'tone': 'energetic and positive',
                'brevity': 'concise but warm',
                'warmth': 0.9
            },
            EmotionalState.PROFESSIONAL: {
                'tone': 'calm and composed',
                'brevity': 'clear and direct',
                'warmth': 0.6
            }
        }
        
        return modifiers.get(self.current_state, modifiers[EmotionalState.NEUTRAL])
    
    def get_status(self) -> Dict[str, Any]:
        """Get current personality status"""
        return {
            'current_state': self.current_state.value,
            'user_emotion': self.user_emotion,
            'traits': self.traits,
            'modifiers': self.get_response_modifiers()
        }


__all__ = ['PersonalityEngine', 'EmotionalState']

