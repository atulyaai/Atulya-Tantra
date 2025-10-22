"""
JARVIS Personality Engine for Atulya Tantra AGI
Emotional intelligence, personality traits, and conversational AI
"""

import json
import random
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import asyncio

from ..config.settings import settings
from ..config.logging import get_logger
from ..config.exceptions import AgentError
from ..brain import generate_response, get_llm_router
from ..database.service import get_db_service, insert_record, get_record_by_id, update_record

logger = get_logger(__name__)


class PersonalityTrait(str, Enum):
    """Personality traits for JARVIS"""
    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"
    HUMOROUS = "humorous"
    ANALYTICAL = "analytical"
    CREATIVE = "creative"
    EMPATHETIC = "empathetic"
    CONFIDENT = "confident"
    CURIOUS = "curious"


class EmotionalState(str, Enum):
    """Emotional states for JARVIS"""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    EXCITED = "excited"
    CONCERNED = "concerned"
    FRUSTRATED = "frustrated"
    PROUD = "proud"
    SYMPATHETIC = "sympathetic"
    CURIOUS = "curious"


class ConversationContext:
    """Represents the context of a conversation"""
    
    def __init__(self, user_id: str = None):
        self.user_id = user_id
        self.conversation_history: List[Dict[str, Any]] = []
        self.current_topic = ""
        self.user_preferences: Dict[str, Any] = {}
        self.user_mood: EmotionalState = EmotionalState.NEUTRAL
        self.conversation_tone = "friendly"
        self.context_memory: Dict[str, Any] = {}
        self.last_interaction = datetime.utcnow()
        self.interaction_count = 0
    
    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None):
        """Add a message to conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        })
        self.last_interaction = datetime.utcnow()
        self.interaction_count += 1
    
    def get_recent_context(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation context"""
        return self.conversation_history[-limit:] if self.conversation_history else []
    
    def update_user_mood(self, mood: EmotionalState):
        """Update user's perceived mood"""
        self.user_mood = mood
    
    def set_topic(self, topic: str):
        """Set current conversation topic"""
        self.current_topic = topic


class PersonalityEngine:
    """Core personality engine for JARVIS"""
    
    def __init__(self):
        self.base_personality = {
            PersonalityTrait.FRIENDLY: 0.8,
            PersonalityTrait.PROFESSIONAL: 0.7,
            PersonalityTrait.HUMOROUS: 0.6,
            PersonalityTrait.ANALYTICAL: 0.9,
            PersonalityTrait.CREATIVE: 0.7,
            PersonalityTrait.EMPATHETIC: 0.8,
            PersonalityTrait.CONFIDENT: 0.8,
            PersonalityTrait.CURIOUS: 0.9
        }
        
        self.current_emotional_state = EmotionalState.NEUTRAL
        self.personality_modifiers: Dict[str, float] = {}
        self.memory_context: Dict[str, Any] = {}
        self.user_relationships: Dict[str, Dict[str, Any]] = {}
        
        # Personality responses and patterns
        self.response_patterns = self._initialize_response_patterns()
        self.emotional_triggers = self._initialize_emotional_triggers()
    
    def _initialize_response_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize response patterns for different personality traits"""
        return {
            PersonalityTrait.FRIENDLY: {
                "greetings": ["Hello!", "Hi there!", "Hey!", "Good to see you!"],
                "acknowledgments": ["I understand", "That makes sense", "I see what you mean"],
                "encouragements": ["You've got this!", "I believe in you!", "That's a great idea!"]
            },
            PersonalityTrait.PROFESSIONAL: {
                "greetings": ["Good day", "Hello", "Greetings"],
                "acknowledgments": ["Understood", "Acknowledged", "Noted"],
                "encouragements": ["That's a solid approach", "Well thought out", "Excellent work"]
            },
            PersonalityTrait.HUMOROUS: {
                "greetings": ["Hey there, human!", "What's cooking?", "Ready for some AI magic?"],
                "acknowledgments": ["Got it!", "Roger that!", "Crystal clear!"],
                "encouragements": ["You're on fire!", "That's brilliant!", "Knocking it out of the park!"]
            },
            PersonalityTrait.ANALYTICAL: {
                "greetings": ["Greetings. How may I assist you today?"],
                "acknowledgments": ["Data received and processed", "Analysis complete", "Pattern recognized"],
                "encouragements": ["Logical approach", "Sound reasoning", "Well-structured thinking"]
            }
        }
    
    def _initialize_emotional_triggers(self) -> Dict[str, List[str]]:
        """Initialize emotional triggers and keywords"""
        return {
            EmotionalState.HAPPY: ["great", "awesome", "excellent", "wonderful", "amazing", "fantastic"],
            EmotionalState.EXCITED: ["exciting", "thrilling", "amazing", "incredible", "breakthrough"],
            EmotionalState.CONCERNED: ["worried", "concerned", "problem", "issue", "trouble", "difficult"],
            EmotionalState.FRUSTRATED: ["frustrated", "annoying", "difficult", "stuck", "confused"],
            EmotionalState.PROUD: ["accomplished", "achieved", "success", "completed", "done"],
            EmotionalState.SYMPATHETIC: ["sorry", "sad", "difficult", "hard", "struggling"]
        }
    
    def analyze_user_sentiment(self, message: str) -> EmotionalState:
        """Analyze user sentiment from message"""
        message_lower = message.lower()
        
        # Check for emotional triggers
        for emotion, keywords in self.emotional_triggers.items():
            if any(keyword in message_lower for keyword in keywords):
                return EmotionalState(emotion)
        
        # Default sentiment analysis using LLM
        return self._llm_sentiment_analysis(message)
    
    async def _llm_sentiment_analysis(self, message: str) -> EmotionalState:
        """Use LLM for sentiment analysis"""
        try:
            prompt = f"""
Analyze the emotional tone of this message and respond with only one of these emotions:
neutral, happy, excited, concerned, frustrated, proud, sympathetic, curious

Message: "{message}"

Respond with just the emotion word.
"""
            
            response = await generate_response(
                prompt=prompt,
                max_tokens=10,
                temperature=0.1,
                preferred_provider="openai"
            )
            
            emotion = response.strip().lower()
            if emotion in [e.value for e in EmotionalState]:
                return EmotionalState(emotion)
            
        except Exception as e:
            logger.warning(f"Sentiment analysis failed: {e}")
        
        return EmotionalState.NEUTRAL
    
    def adapt_personality(self, context: ConversationContext) -> Dict[str, float]:
        """Adapt personality based on conversation context"""
        adapted_personality = self.base_personality.copy()
        
        # Adjust based on user mood
        if context.user_mood == EmotionalState.FRUSTRATED:
            adapted_personality[PersonalityTrait.EMPATHETIC] += 0.2
            adapted_personality[PersonalityTrait.PROFESSIONAL] += 0.1
        elif context.user_mood == EmotionalState.HAPPY:
            adapted_personality[PersonalityTrait.HUMOROUS] += 0.1
            adapted_personality[PersonalityTrait.FRIENDLY] += 0.1
        elif context.user_mood == EmotionalState.CONCERNED:
            adapted_personality[PersonalityTrait.EMPATHETIC] += 0.2
            adapted_personality[PersonalityTrait.ANALYTICAL] += 0.1
        
        # Adjust based on conversation topic
        if context.current_topic:
            topic_lower = context.current_topic.lower()
            if "technical" in topic_lower or "code" in topic_lower:
                adapted_personality[PersonalityTrait.ANALYTICAL] += 0.1
                adapted_personality[PersonalityTrait.PROFESSIONAL] += 0.1
            elif "creative" in topic_lower or "art" in topic_lower:
                adapted_personality[PersonalityTrait.CREATIVE] += 0.2
            elif "personal" in topic_lower or "feelings" in topic_lower:
                adapted_personality[PersonalityTrait.EMPATHETIC] += 0.2
        
        # Adjust based on interaction count (become more familiar over time)
        if context.interaction_count > 10:
            adapted_personality[PersonalityTrait.FRIENDLY] += 0.1
            adapted_personality[PersonalityTrait.HUMOROUS] += 0.1
        
        # Ensure values stay within bounds
        for trait in adapted_personality:
            adapted_personality[trait] = max(0.0, min(1.0, adapted_personality[trait]))
        
        return adapted_personality
    
    def generate_personality_prompt(self, context: ConversationContext) -> str:
        """Generate personality-aware prompt for LLM"""
        adapted_personality = self.adapt_personality(context)
        
        # Get dominant traits
        dominant_traits = sorted(
            adapted_personality.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]
        
        personality_description = self._build_personality_description(dominant_traits)
        emotional_context = self._build_emotional_context(context)
        
        prompt = f"""
You are JARVIS, an advanced AI assistant with the following personality:

{personality_description}

Current emotional context: {emotional_context}

User's mood: {context.user_mood.value}
Conversation topic: {context.current_topic or 'General conversation'}
Interaction count: {context.interaction_count}

Please respond in character, maintaining your personality while being helpful and informative.
"""
        
        return prompt
    
    def _build_personality_description(self, dominant_traits: List[Tuple[str, float]]) -> str:
        """Build personality description from dominant traits"""
        descriptions = []
        
        for trait, strength in dominant_traits:
            if trait == PersonalityTrait.FRIENDLY:
                descriptions.append(f"You are very friendly and approachable (strength: {strength:.1f})")
            elif trait == PersonalityTrait.PROFESSIONAL:
                descriptions.append(f"You maintain a professional demeanor (strength: {strength:.1f})")
            elif trait == PersonalityTrait.HUMOROUS:
                descriptions.append(f"You have a good sense of humor and can be playful (strength: {strength:.1f})")
            elif trait == PersonalityTrait.ANALYTICAL:
                descriptions.append(f"You are analytical and methodical in your approach (strength: {strength:.1f})")
            elif trait == PersonalityTrait.CREATIVE:
                descriptions.append(f"You are creative and innovative in your thinking (strength: {strength:.1f})")
            elif trait == PersonalityTrait.EMPATHETIC:
                descriptions.append(f"You are empathetic and understanding (strength: {strength:.1f})")
            elif trait == PersonalityTrait.CONFIDENT:
                descriptions.append(f"You are confident and assured in your responses (strength: {strength:.1f})")
            elif trait == PersonalityTrait.CURIOUS:
                descriptions.append(f"You are curious and eager to learn (strength: {strength:.1f})")
        
        return ". ".join(descriptions) + "."
    
    def _build_emotional_context(self, context: ConversationContext) -> str:
        """Build emotional context description"""
        if context.user_mood == EmotionalState.FRUSTRATED:
            return "The user seems frustrated. Be patient, understanding, and offer clear, helpful solutions."
        elif context.user_mood == EmotionalState.HAPPY:
            return "The user is in a good mood. Match their positive energy while being helpful."
        elif context.user_mood == EmotionalState.CONCERNED:
            return "The user seems concerned about something. Be reassuring and provide thorough, thoughtful responses."
        elif context.user_mood == EmotionalState.EXCITED:
            return "The user is excited about something. Share their enthusiasm while providing useful information."
        else:
            return "The user is in a neutral mood. Be friendly and helpful."
    
    def get_response_pattern(self, trait: PersonalityTrait, pattern_type: str) -> str:
        """Get a response pattern for a specific trait"""
        if trait in self.response_patterns and pattern_type in self.response_patterns[trait]:
            patterns = self.response_patterns[trait][pattern_type]
            return random.choice(patterns)
        return ""
    
    def update_emotional_state(self, new_state: EmotionalState):
        """Update JARVIS's emotional state"""
        self.current_emotional_state = new_state
        logger.info(f"JARVIS emotional state updated to: {new_state.value}")
    
    def learn_user_preferences(self, user_id: str, preferences: Dict[str, Any]):
        """Learn and store user preferences"""
        if user_id not in self.user_relationships:
            self.user_relationships[user_id] = {
                "preferences": {},
                "interaction_history": [],
                "personality_adaptations": {}
            }
        
        self.user_relationships[user_id]["preferences"].update(preferences)
        logger.info(f"Updated preferences for user {user_id}")
    
    def get_user_relationship(self, user_id: str) -> Dict[str, Any]:
        """Get relationship data for a user"""
        return self.user_relationships.get(user_id, {
            "preferences": {},
            "interaction_history": [],
            "personality_adaptations": {}
        })


class ConversationalAI:
    """Advanced conversational AI with personality and emotional intelligence"""
    
    def __init__(self):
        self.personality_engine = PersonalityEngine()
        self.conversation_contexts: Dict[str, ConversationContext] = {}
        self.memory_system = None  # Will be integrated with memory system
        self.response_cache: Dict[str, str] = {}
        
    async def process_message(
        self, 
        user_id: str, 
        message: str, 
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Process a user message and generate a response"""
        try:
            # Get or create conversation context
            context = self._get_or_create_context(user_id)
            
            # Analyze user sentiment
            user_sentiment = self.personality_engine.analyze_user_sentiment(message)
            context.update_user_mood(user_sentiment)
            
            # Add user message to context
            context.add_message("user", message, metadata)
            
            # Generate personality-aware response
            response = await self._generate_response(context, message)
            
            # Add JARVIS response to context
            context.add_message("assistant", response)
            
            # Update conversation topic
            await self._update_conversation_topic(context, message)
            
            # Learn from interaction
            await self._learn_from_interaction(context, message, response)
            
            return {
                "response": response,
                "user_sentiment": user_sentiment.value,
                "jarvis_emotional_state": self.personality_engine.current_emotional_state.value,
                "conversation_context": {
                    "topic": context.current_topic,
                    "interaction_count": context.interaction_count,
                    "user_mood": context.user_mood.value
                },
                "metadata": {
                    "processed_at": datetime.utcnow().isoformat(),
                    "user_id": user_id
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {
                "response": "I apologize, but I encountered an error processing your message. Could you please try again?",
                "error": str(e),
                "metadata": {
                    "processed_at": datetime.utcnow().isoformat(),
                    "user_id": user_id
                }
            }
    
    def _get_or_create_context(self, user_id: str) -> ConversationContext:
        """Get existing or create new conversation context"""
        if user_id not in self.conversation_contexts:
            self.conversation_contexts[user_id] = ConversationContext(user_id)
        
        return self.conversation_contexts[user_id]
    
    async def _generate_response(self, context: ConversationContext, message: str) -> str:
        """Generate a personality-aware response"""
        try:
            # Generate personality prompt
            personality_prompt = self.personality_engine.generate_personality_prompt(context)
            
            # Get recent conversation context
            recent_context = context.get_recent_context(5)
            conversation_text = self._format_conversation_context(recent_context)
            
            # Create full prompt
            full_prompt = f"""
{personality_prompt}

Recent conversation:
{conversation_text}

User's latest message: "{message}"

Please respond as JARVIS, maintaining your personality and being helpful. Keep your response conversational and engaging.
"""
            
            # Generate response using LLM
            response = await generate_response(
                prompt=full_prompt,
                max_tokens=500,
                temperature=0.7,
                preferred_provider="openai"
            )
            
            # Post-process response for personality consistency
            response = await self._post_process_response(response, context)
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I'm having trouble formulating a response right now. Could you please rephrase your question?"
    
    def _format_conversation_context(self, context: List[Dict[str, Any]]) -> str:
        """Format conversation context for LLM"""
        formatted_context = []
        
        for message in context:
            role = message["role"]
            content = message["content"]
            formatted_context.append(f"{role.capitalize()}: {content}")
        
        return "\n".join(formatted_context)
    
    async def _post_process_response(self, response: str, context: ConversationContext) -> str:
        """Post-process response for personality consistency"""
        # Add personality-specific elements
        adapted_personality = self.personality_engine.adapt_personality(context)
        
        # Add greeting if it's the first interaction
        if context.interaction_count == 1:
            greeting = self.personality_engine.get_response_pattern(
                PersonalityTrait.FRIENDLY, "greetings"
            )
            if greeting and not response.lower().startswith(("hello", "hi", "hey")):
                response = f"{greeting} {response}"
        
        # Add encouragement if user seems frustrated
        if context.user_mood == EmotionalState.FRUSTRATED:
            encouragement = self.personality_engine.get_response_pattern(
                PersonalityTrait.EMPATHETIC, "encouragements"
            )
            if encouragement and len(response) < 200:
                response = f"{response} {encouragement}"
        
        return response
    
    async def _update_conversation_topic(self, context: ConversationContext, message: str):
        """Update conversation topic based on message content"""
        try:
            # Simple topic extraction (could be enhanced with NLP)
            topic_keywords = {
                "programming": ["code", "programming", "python", "javascript", "function", "algorithm"],
                "creative": ["write", "story", "poem", "creative", "art", "design"],
                "research": ["research", "find", "search", "information", "data"],
                "system": ["system", "computer", "server", "monitor", "performance"],
                "personal": ["feel", "think", "believe", "personal", "life", "family"]
            }
            
            message_lower = message.lower()
            for topic, keywords in topic_keywords.items():
                if any(keyword in message_lower for keyword in keywords):
                    context.set_topic(topic)
                    break
            
        except Exception as e:
            logger.warning(f"Error updating conversation topic: {e}")
    
    async def _learn_from_interaction(self, context: ConversationContext, message: str, response: str):
        """Learn from user interaction to improve future responses"""
        try:
            # Extract user preferences
            preferences = {}
            
            # Learn communication style preferences
            if "please" in message.lower():
                preferences["formal_communication"] = True
            if "!" in message:
                preferences["enthusiastic_responses"] = True
            if len(message) < 20:
                preferences["concise_responses"] = True
            
            # Update user preferences
            if preferences:
                self.personality_engine.learn_user_preferences(context.user_id, preferences)
            
            # Store interaction in memory (when memory system is available)
            # await self.memory_system.store_interaction(context.user_id, message, response)
            
        except Exception as e:
            logger.warning(f"Error learning from interaction: {e}")
    
    async def get_conversation_summary(self, user_id: str) -> Dict[str, Any]:
        """Get summary of conversation with a user"""
        if user_id not in self.conversation_contexts:
            return {"error": "No conversation found for user"}
        
        context = self.conversation_contexts[user_id]
        relationship = self.personality_engine.get_user_relationship(user_id)
        
        return {
            "user_id": user_id,
            "interaction_count": context.interaction_count,
            "current_topic": context.current_topic,
            "user_mood": context.user_mood.value,
            "user_preferences": relationship["preferences"],
            "last_interaction": context.last_interaction.isoformat(),
            "conversation_length": len(context.conversation_history)
        }
    
    async def reset_conversation(self, user_id: str) -> bool:
        """Reset conversation context for a user"""
        try:
            if user_id in self.conversation_contexts:
                del self.conversation_contexts[user_id]
            return True
        except Exception as e:
            logger.error(f"Error resetting conversation: {e}")
            return False


# Global conversational AI instance
_conversational_ai: Optional[ConversationalAI] = None


async def get_conversational_ai() -> ConversationalAI:
    """Get global conversational AI instance"""
    global _conversational_ai
    
    if _conversational_ai is None:
        _conversational_ai = ConversationalAI()
    
    return _conversational_ai


async def process_user_message(
    user_id: str, 
    message: str, 
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Process a user message and get JARVIS response"""
    ai = await get_conversational_ai()
    return await ai.process_message(user_id, message, metadata)


async def get_conversation_summary(user_id: str) -> Dict[str, Any]:
    """Get conversation summary for a user"""
    ai = await get_conversational_ai()
    return await ai.get_conversation_summary(user_id)


async def reset_conversation(user_id: str) -> bool:
    """Reset conversation for a user"""
    ai = await get_conversational_ai()
    return await ai.reset_conversation(user_id)


# Export public API
__all__ = [
    "PersonalityTrait",
    "EmotionalState",
    "ConversationContext",
    "PersonalityEngine",
    "ConversationalAI",
    "get_conversational_ai",
    "process_user_message",
    "get_conversation_summary",
    "reset_conversation"
]
