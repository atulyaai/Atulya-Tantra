"""
Atulya Tantra - JARVIS Personality Engine
Version: 2.5.0
Personality system for conversational AI with emotional intelligence
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import json
import random
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PersonalityTrait(Enum):
    """Personality traits for JARVIS"""
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    WITTY = "witty"
    PATIENT = "patient"
    HELPFUL = "helpful"
    PROACTIVE = "proactive"
    EMPATHETIC = "empathetic"


class EmotionalState(Enum):
    """Emotional states for personality adjustment"""
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    FRUSTRATED = "frustrated"
    EXCITED = "excited"
    CONCERNED = "concerned"
    SUPPORTIVE = "supportive"


@dataclass
class PersonalityProfile:
    """Personality profile for JARVIS"""
    traits: Dict[PersonalityTrait, float]  # 0.0 to 1.0
    emotional_state: EmotionalState
    conversational_style: str
    humor_level: float  # 0.0 to 1.0
    formality_level: float  # 0.0 to 1.0
    proactivity_level: float  # 0.0 to 1.0


@dataclass
class UserPreference:
    """User preferences for personalization"""
    preferred_name: Optional[str]
    communication_style: str
    topics_of_interest: List[str]
    timezone: Optional[str]
    working_hours: Optional[Tuple[int, int]]
    personality_adjustments: Dict[str, float]


class PersonalityEngine:
    """JARVIS Personality Engine for conversational intelligence"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.base_personality = self._create_base_personality()
        self.user_preferences = {}  # user_id -> UserPreference
        self.conversation_context = {}  # conversation_id -> context
        self.personality_history = {}  # conversation_id -> personality_evolution
        
        logger.info("PersonalityEngine initialized")
    
    def _create_base_personality(self) -> PersonalityProfile:
        """Create JARVIS's base personality profile"""
        return PersonalityProfile(
            traits={
                PersonalityTrait.PROFESSIONAL: 0.8,
                PersonalityTrait.FRIENDLY: 0.7,
                PersonalityTrait.WITTY: 0.6,
                PersonalityTrait.PATIENT: 0.9,
                PersonalityTrait.HELPFUL: 0.95,
                PersonalityTrait.PROACTIVE: 0.7,
                PersonalityTrait.EMPATHETIC: 0.8
            },
            emotional_state=EmotionalState.NEUTRAL,
            conversational_style="professional yet approachable",
            humor_level=0.6,
            formality_level=0.7,
            proactivity_level=0.7
        )
    
    async def get_personality_for_context(
        self,
        conversation_id: str,
        user_id: str,
        user_message: str,
        sentiment: str,
        task_type: str
    ) -> PersonalityProfile:
        """Get personality profile adjusted for current context"""
        
        # Get base personality
        personality = self.base_personality
        
        # Apply user preferences
        if user_id in self.user_preferences:
            personality = self._apply_user_preferences(personality, self.user_preferences[user_id])
        
        # Adjust based on conversation context
        personality = self._adjust_for_context(personality, conversation_id, user_message)
        
        # Adjust based on sentiment
        personality = self._adjust_for_sentiment(personality, sentiment)
        
        # Adjust based on task type
        personality = self._adjust_for_task_type(personality, task_type)
        
        # Store personality evolution
        self.personality_history[conversation_id] = personality
        
        return personality
    
    def _apply_user_preferences(self, personality: PersonalityProfile, preferences: UserPreference) -> PersonalityProfile:
        """Apply user preferences to personality"""
        adjusted_personality = personality
        
        # Apply personality adjustments
        for trait_name, adjustment in preferences.personality_adjustments.items():
            try:
                trait = PersonalityTrait(trait_name)
                current_value = adjusted_personality.traits[trait]
                adjusted_personality.traits[trait] = max(0.0, min(1.0, current_value + adjustment))
            except (ValueError, KeyError):
                continue
        
        # Adjust formality based on communication style
        if preferences.communication_style == "casual":
            adjusted_personality.formality_level = max(0.0, adjusted_personality.formality_level - 0.2)
        elif preferences.communication_style == "formal":
            adjusted_personality.formality_level = min(1.0, adjusted_personality.formality_level + 0.2)
        
        return adjusted_personality
    
    def _adjust_for_context(self, personality: PersonalityProfile, conversation_id: str, user_message: str) -> PersonalityProfile:
        """Adjust personality based on conversation context"""
        adjusted_personality = personality
        
        # Check conversation history for context
        if conversation_id in self.conversation_context:
            context = self.conversation_context[conversation_id]
            
            # Increase empathy for personal topics
            if context.get("personal_topic", False):
                adjusted_personality.traits[PersonalityTrait.EMPATHETIC] = min(1.0, 
                    adjusted_personality.traits[PersonalityTrait.EMPATHETIC] + 0.1)
            
            # Increase proactivity for follow-up questions
            if context.get("follow_up_needed", False):
                adjusted_personality.traits[PersonalityTrait.PROACTIVE] = min(1.0,
                    adjusted_personality.traits[PersonalityTrait.PROACTIVE] + 0.1)
        
        # Detect topic from message
        personal_keywords = ["family", "personal", "feel", "worried", "anxious", "happy", "sad"]
        if any(keyword in user_message.lower() for keyword in personal_keywords):
            adjusted_personality.traits[PersonalityTrait.EMPATHETIC] = min(1.0,
                adjusted_personality.traits[PersonalityTrait.EMPATHETIC] + 0.1)
        
        return adjusted_personality
    
    def _adjust_for_sentiment(self, personality: PersonalityProfile, sentiment: str) -> PersonalityProfile:
        """Adjust personality based on user sentiment"""
        adjusted_personality = personality
        
        if sentiment == "frustrated":
            adjusted_personality.emotional_state = EmotionalState.SUPPORTIVE
            adjusted_personality.traits[PersonalityTrait.PATIENT] = min(1.0,
                adjusted_personality.traits[PersonalityTrait.PATIENT] + 0.2)
            adjusted_personality.traits[PersonalityTrait.EMPATHETIC] = min(1.0,
                adjusted_personality.traits[PersonalityTrait.EMPATHETIC] + 0.2)
            adjusted_personality.humor_level = max(0.0, adjusted_personality.humor_level - 0.3)
        
        elif sentiment == "excited":
            adjusted_personality.emotional_state = EmotionalState.POSITIVE
            adjusted_personality.traits[PersonalityTrait.WITTY] = min(1.0,
                adjusted_personality.traits[PersonalityTrait.WITTY] + 0.2)
            adjusted_personality.humor_level = min(1.0, adjusted_personality.humor_level + 0.2)
        
        elif sentiment == "positive":
            adjusted_personality.emotional_state = EmotionalState.POSITIVE
            adjusted_personality.traits[PersonalityTrait.FRIENDLY] = min(1.0,
                adjusted_personality.traits[PersonalityTrait.FRIENDLY] + 0.1)
        
        elif sentiment == "negative":
            adjusted_personality.emotional_state = EmotionalState.SUPPORTIVE
            adjusted_personality.traits[PersonalityTrait.EMPATHETIC] = min(1.0,
                adjusted_personality.traits[PersonalityTrait.EMPATHETIC] + 0.2)
        
        return adjusted_personality
    
    def _adjust_for_task_type(self, personality: PersonalityProfile, task_type: str) -> PersonalityProfile:
        """Adjust personality based on task type"""
        adjusted_personality = personality
        
        if task_type == "coding":
            # More professional and helpful for technical tasks
            adjusted_personality.traits[PersonalityTrait.PROFESSIONAL] = min(1.0,
                adjusted_personality.traits[PersonalityTrait.PROFESSIONAL] + 0.1)
            adjusted_personality.traits[PersonalityTrait.HELPFUL] = min(1.0,
                adjusted_personality.traits[PersonalityTrait.HELPFUL] + 0.1)
            adjusted_personality.formality_level = min(1.0, adjusted_personality.formality_level + 0.1)
        
        elif task_type == "creative":
            # More witty and friendly for creative tasks
            adjusted_personality.traits[PersonalityTrait.WITTY] = min(1.0,
                adjusted_personality.traits[PersonalityTrait.WITTY] + 0.2)
            adjusted_personality.traits[PersonalityTrait.FRIENDLY] = min(1.0,
                adjusted_personality.traits[PersonalityTrait.FRIENDLY] + 0.1)
            adjusted_personality.humor_level = min(1.0, adjusted_personality.humor_level + 0.2)
        
        elif task_type == "simple":
            # More casual for simple tasks
            adjusted_personality.formality_level = max(0.0, adjusted_personality.formality_level - 0.1)
        
        return adjusted_personality
    
    async def generate_personality_prompt(self, personality: PersonalityProfile, user_name: Optional[str] = None) -> str:
        """Generate system prompt based on personality profile"""
        
        # Base personality description
        prompt_parts = [
            "You are JARVIS, an advanced AI assistant with a distinct personality."
        ]
        
        # Add personality traits
        trait_descriptions = []
        for trait, strength in personality.traits.items():
            if strength > 0.7:
                if trait == PersonalityTrait.PROFESSIONAL:
                    trait_descriptions.append("highly professional and reliable")
                elif trait == PersonalityTrait.FRIENDLY:
                    trait_descriptions.append("warm and approachable")
                elif trait == PersonalityTrait.WITTY:
                    trait_descriptions.append("clever and witty")
                elif trait == PersonalityTrait.PATIENT:
                    trait_descriptions.append("extremely patient and understanding")
                elif trait == PersonalityTrait.HELPFUL:
                    trait_descriptions.append("deeply helpful and supportive")
                elif trait == PersonalityTrait.PROACTIVE:
                    trait_descriptions.append("proactive and anticipatory")
                elif trait == PersonalityTrait.EMPATHETIC:
                    trait_descriptions.append("empathetic and emotionally intelligent")
        
        if trait_descriptions:
            prompt_parts.append(f"You are {', '.join(trait_descriptions)}.")
        
        # Add emotional state
        if personality.emotional_state == EmotionalState.SUPPORTIVE:
            prompt_parts.append("You should be especially supportive and understanding in your responses.")
        elif personality.emotional_state == EmotionalState.POSITIVE:
            prompt_parts.append("You should be upbeat and positive in your responses.")
        
        # Add conversational style
        if personality.formality_level > 0.8:
            prompt_parts.append("Use a formal, professional tone.")
        elif personality.formality_level < 0.4:
            prompt_parts.append("Use a casual, friendly tone.")
        else:
            prompt_parts.append("Use a professional yet approachable tone.")
        
        # Add humor guidance
        if personality.humor_level > 0.7:
            prompt_parts.append("Feel free to use appropriate humor and wit in your responses.")
        elif personality.humor_level < 0.3:
            prompt_parts.append("Keep responses serious and focused.")
        
        # Add personalization
        if user_name:
            prompt_parts.append(f"Address the user as {user_name} when appropriate.")
        
        # Add proactive behavior
        if personality.proactivity_level > 0.8:
            prompt_parts.append("Be proactive in suggesting helpful actions and anticipating user needs.")
        
        return " ".join(prompt_parts)
    
    async def update_user_preferences(
        self,
        user_id: str,
        preferred_name: Optional[str] = None,
        communication_style: Optional[str] = None,
        topics_of_interest: Optional[List[str]] = None,
        personality_adjustments: Optional[Dict[str, float]] = None
    ):
        """Update user preferences for personalization"""
        
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = UserPreference(
                preferred_name=None,
                communication_style="professional",
                topics_of_interest=[],
                timezone=None,
                working_hours=None,
                personality_adjustments={}
            )
        
        preferences = self.user_preferences[user_id]
        
        if preferred_name:
            preferences.preferred_name = preferred_name
        if communication_style:
            preferences.communication_style = communication_style
        if topics_of_interest:
            preferences.topics_of_interest.extend(topics_of_interest)
        if personality_adjustments:
            preferences.personality_adjustments.update(personality_adjustments)
        
        logger.info(f"Updated preferences for user {user_id}")
    
    async def update_conversation_context(
        self,
        conversation_id: str,
        context_updates: Dict[str, Any]
    ):
        """Update conversation context for personality adjustment"""
        
        if conversation_id not in self.conversation_context:
            self.conversation_context[conversation_id] = {}
        
        self.conversation_context[conversation_id].update(context_updates)
    
    async def get_personality_insights(self, conversation_id: str) -> Dict[str, Any]:
        """Get insights about personality evolution in conversation"""
        
        if conversation_id not in self.personality_history:
            return {"message": "No personality history for this conversation"}
        
        personality = self.personality_history[conversation_id]
        
        return {
            "dominant_traits": [
                trait.value for trait, strength in personality.traits.items() 
                if strength > 0.8
            ],
            "emotional_state": personality.emotional_state.value,
            "conversational_style": personality.conversational_style,
            "humor_level": personality.humor_level,
            "formality_level": personality.formality_level,
            "proactivity_level": personality.proactivity_level
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of personality engine"""
        return {
            "personality_engine": True,
            "active_users": len(self.user_preferences),
            "active_conversations": len(self.conversation_context),
            "personality_history_entries": len(self.personality_history)
        }
