"""
Natural Conversation System
Human-like conversations without hardcoded responses using dynamic AI
"""

import asyncio
import json
import random
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import re

from ..config.logging import get_logger
from ..brain.llm_provider import get_llm_provider
from ..memory.conversation_memory import get_conversation_memory

logger = get_logger(__name__)


class ConversationStyle(str, Enum):
    """Conversation styles"""
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    FRIENDLY = "friendly"
    TECHNICAL = "technical"
    CREATIVE = "creative"
    ADAPTIVE = "adaptive"


class ConversationContext(str, Enum):
    """Conversation contexts"""
    GREETING = "greeting"
    QUESTION = "question"
    REQUEST = "request"
    COMPLAINT = "complaint"
    COMPLIMENT = "compliment"
    SMALL_TALK = "small_talk"
    DEEP_DISCUSSION = "deep_discussion"
    PROBLEM_SOLVING = "problem_solving"
    CREATIVE_WORK = "creative_work"
    TECHNICAL_SUPPORT = "technical_support"


@dataclass
class ConversationState:
    """Current conversation state"""
    user_id: str
    session_id: str
    style: ConversationStyle
    context: ConversationContext
    mood: str  # happy, neutral, frustrated, excited, etc.
    topics: List[str]
    last_interaction: datetime
    conversation_depth: int
    user_preferences: Dict[str, Any]
    emotional_context: Dict[str, float]  # emotional scores


@dataclass
class ConversationMemory:
    """Conversation memory entry"""
    timestamp: datetime
    user_message: str
    ai_response: str
    context: ConversationContext
    emotional_tone: str
    topics: List[str]
    user_satisfaction: Optional[float] = None
    follow_up_needed: bool = False


class NaturalConversationEngine:
    """Advanced natural conversation engine with human-like responses"""
    
    def __init__(self):
        self.llm_provider = get_llm_provider()
        self.memory = get_conversation_memory()
        self.conversation_states: Dict[str, ConversationState] = {}
        self.conversation_memories: Dict[str, List[ConversationMemory]] = {}
        
        # Conversation patterns and templates (minimal, mostly for fallback)
        self.fallback_responses = {
            "greeting": [
                "Hello! How can I help you today?",
                "Hi there! What's on your mind?",
                "Hey! Great to see you. What can I do for you?"
            ],
            "confusion": [
                "I'm not sure I understand. Could you rephrase that?",
                "Let me make sure I got that right. Are you asking about...?",
                "I want to help, but I need a bit more context. Could you clarify?"
            ],
            "encouragement": [
                "That's a great question!",
                "I love that you're thinking about this.",
                "You're absolutely right to ask about that."
            ]
        }
        
        # Emotional intelligence patterns
        self.emotional_patterns = {
            "frustrated": {
                "indicators": ["frustrated", "annoyed", "angry", "upset", "mad"],
                "response_style": "patient, understanding, solution-focused",
                "tone": "calm and supportive"
            },
            "excited": {
                "indicators": ["excited", "thrilled", "amazing", "awesome", "fantastic"],
                "response_style": "enthusiastic, engaging, matching energy",
                "tone": "upbeat and positive"
            },
            "confused": {
                "indicators": ["confused", "don't understand", "unclear", "lost"],
                "response_style": "clear, step-by-step, patient",
                "tone": "helpful and educational"
            },
            "sad": {
                "indicators": ["sad", "depressed", "down", "upset", "disappointed"],
                "response_style": "empathetic, supportive, gentle",
                "tone": "caring and understanding"
            }
        }
    
    async def process_message(self, user_id: str, message: str, session_id: str = None) -> str:
        """Process user message and generate natural response"""
        try:
            # Get or create conversation state
            state = await self._get_conversation_state(user_id, session_id)
            
            # Analyze the message
            analysis = await self._analyze_message(message, state)
            
            # Update conversation state
            await self._update_conversation_state(state, analysis)
            
            # Generate natural response
            response = await self._generate_natural_response(message, analysis, state)
            
            # Store conversation memory
            await self._store_conversation_memory(user_id, message, response, analysis, state)
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return await self._generate_fallback_response(message)
    
    async def _get_conversation_state(self, user_id: str, session_id: str = None) -> ConversationState:
        """Get or create conversation state for user"""
        if session_id is None:
            session_id = f"session_{int(datetime.utcnow().timestamp())}"
        
        state_key = f"{user_id}_{session_id}"
        
        if state_key not in self.conversation_states:
            # Create new conversation state
            self.conversation_states[state_key] = ConversationState(
                user_id=user_id,
                session_id=session_id,
                style=ConversationStyle.ADAPTIVE,
                context=ConversationContext.GREETING,
                mood="neutral",
                topics=[],
                last_interaction=datetime.utcnow(),
                conversation_depth=0,
                user_preferences={},
                emotional_context={}
            )
        
        return self.conversation_states[state_key]
    
    async def _analyze_message(self, message: str, state: ConversationState) -> Dict[str, Any]:
        """Analyze user message for context, emotion, and intent"""
        
        # Use AI to analyze the message
        analysis_prompt = f"""
        Analyze this user message and provide a detailed analysis in JSON format:
        
        User Message: "{message}"
        Current Context: {state.context.value}
        Current Mood: {state.mood}
        Previous Topics: {state.topics}
        
        Please analyze and return JSON with:
        {{
            "context": "greeting|question|request|complaint|compliment|small_talk|deep_discussion|problem_solving|creative_work|technical_support",
            "emotional_tone": "happy|neutral|frustrated|excited|confused|sad|angry|curious|surprised",
            "topics": ["list", "of", "main", "topics"],
            "intent": "what the user wants to accomplish",
            "requires_action": true/false,
            "action_type": "if action required, what type",
            "confidence": 0.0-1.0,
            "follow_up_needed": true/false,
            "conversation_depth": 1-10,
            "suggested_style": "professional|casual|friendly|technical|creative|adaptive"
        }}
        """
        
        try:
            response = await self.llm_provider.generate_response(
                prompt=analysis_prompt,
                max_tokens=500,
                temperature=0.3
            )
            
            # Parse AI response
            analysis = json.loads(response.strip())
            
        except Exception as e:
            logger.warning(f"AI analysis failed, using fallback: {e}")
            # Fallback analysis
            analysis = self._fallback_analysis(message, state)
        
        return analysis
    
    def _fallback_analysis(self, message: str, state: ConversationState) -> Dict[str, Any]:
        """Fallback analysis when AI fails"""
        message_lower = message.lower()
        
        # Simple pattern matching
        if any(word in message_lower for word in ["hello", "hi", "hey", "good morning", "good afternoon"]):
            context = "greeting"
        elif "?" in message:
            context = "question"
        elif any(word in message_lower for word in ["please", "can you", "could you", "help me"]):
            context = "request"
        else:
            context = "small_talk"
        
        return {
            "context": context,
            "emotional_tone": "neutral",
            "topics": [],
            "intent": "general conversation",
            "requires_action": False,
            "confidence": 0.5,
            "follow_up_needed": False,
            "conversation_depth": 1,
            "suggested_style": "friendly"
        }
    
    async def _update_conversation_state(self, state: ConversationState, analysis: Dict[str, Any]):
        """Update conversation state based on analysis"""
        state.context = ConversationContext(analysis.get("context", "small_talk"))
        state.mood = analysis.get("emotional_tone", "neutral")
        state.last_interaction = datetime.utcnow()
        state.conversation_depth = analysis.get("conversation_depth", 1)
        
        # Update topics
        new_topics = analysis.get("topics", [])
        for topic in new_topics:
            if topic not in state.topics:
                state.topics.append(topic)
        
        # Keep only recent topics (last 10)
        if len(state.topics) > 10:
            state.topics = state.topics[-10:]
        
        # Update style based on suggestion
        suggested_style = analysis.get("suggested_style", "adaptive")
        if suggested_style != "adaptive":
            state.style = ConversationStyle(suggested_style)
    
    async def _generate_natural_response(self, message: str, analysis: Dict[str, Any], state: ConversationState) -> str:
        """Generate natural, human-like response"""
        
        # Build context for AI response generation
        context_info = {
            "user_message": message,
            "conversation_context": state.context.value,
            "emotional_tone": state.mood,
            "conversation_style": state.style.value,
            "topics": state.topics,
            "conversation_depth": state.conversation_depth,
            "user_preferences": state.user_preferences,
            "requires_action": analysis.get("requires_action", False),
            "action_type": analysis.get("action_type", ""),
            "follow_up_needed": analysis.get("follow_up_needed", False)
        }
        
        # Generate response using AI
        response_prompt = self._build_response_prompt(context_info)
        
        try:
            response = await self.llm_provider.generate_response(
                prompt=response_prompt,
                max_tokens=300,
                temperature=0.7  # Higher temperature for more natural responses
            )
            
            # Post-process response
            response = self._post_process_response(response, analysis, state)
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return await self._generate_fallback_response(message)
    
    def _build_response_prompt(self, context: Dict[str, Any]) -> str:
        """Build prompt for AI response generation"""
        
        prompt = f"""
        You are an advanced AI assistant having a natural, human-like conversation. 
        
        Context:
        - User Message: "{context['user_message']}"
        - Conversation Context: {context['conversation_context']}
        - Emotional Tone: {context['emotional_tone']}
        - Style: {context['conversation_style']}
        - Topics: {context['topics']}
        - Conversation Depth: {context['conversation_depth']}
        - Requires Action: {context['requires_action']}
        - Action Type: {context['action_type']}
        - Follow-up Needed: {context['follow_up_needed']}
        
        Guidelines:
        1. Respond naturally and conversationally, like a human would
        2. Match the emotional tone appropriately
        3. Be helpful and engaging
        4. If action is required, explain what you'll do
        5. If follow-up is needed, ask relevant questions
        6. Keep responses concise but complete
        7. Show personality and warmth
        8. Avoid robotic or template-like responses
        
        Generate a natural, human-like response:
        """
        
        return prompt
    
    def _post_process_response(self, response: str, analysis: Dict[str, Any], state: ConversationState) -> str:
        """Post-process AI response to make it more natural"""
        
        # Clean up response
        response = response.strip()
        
        # Remove any AI artifacts
        response = re.sub(r'^(AI|Assistant|Bot):\s*', '', response, flags=re.IGNORECASE)
        
        # Add emotional context if needed
        if state.mood in ["frustrated", "sad"] and "I understand" not in response:
            response = f"I understand. {response}"
        
        # Add follow-up questions if needed
        if analysis.get("follow_up_needed", False):
            follow_up = self._generate_follow_up_question(analysis, state)
            if follow_up:
                response += f" {follow_up}"
        
        return response
    
    def _generate_follow_up_question(self, analysis: Dict[str, Any], state: ConversationState) -> str:
        """Generate natural follow-up questions"""
        
        context = analysis.get("context", "small_talk")
        intent = analysis.get("intent", "")
        
        follow_ups = {
            "question": "Is there anything specific you'd like to know more about?",
            "request": "Would you like me to help you with that?",
            "problem_solving": "What approach would you prefer to take?",
            "creative_work": "What style or direction are you thinking?",
            "technical_support": "Can you tell me more about the issue you're experiencing?"
        }
        
        return follow_ups.get(context, "")
    
    async def _generate_fallback_response(self, message: str) -> str:
        """Generate fallback response when AI fails"""
        
        message_lower = message.lower()
        
        # Check for greetings
        if any(word in message_lower for word in ["hello", "hi", "hey"]):
            return random.choice(self.fallback_responses["greeting"])
        
        # Check for confusion indicators
        if any(word in message_lower for word in ["what", "how", "why", "when", "where"]):
            return random.choice(self.fallback_responses["encouragement"])
        
        # Default response
        return "I'm here to help! Could you tell me more about what you need?"
    
    async def _store_conversation_memory(self, user_id: str, message: str, response: str, 
                                       analysis: Dict[str, Any], state: ConversationState):
        """Store conversation in memory"""
        
        memory_entry = ConversationMemory(
            timestamp=datetime.utcnow(),
            user_message=message,
            ai_response=response,
            context=ConversationContext(analysis.get("context", "small_talk")),
            emotional_tone=analysis.get("emotional_tone", "neutral"),
            topics=analysis.get("topics", []),
            follow_up_needed=analysis.get("follow_up_needed", False)
        )
        
        if user_id not in self.conversation_memories:
            self.conversation_memories[user_id] = []
        
        self.conversation_memories[user_id].append(memory_entry)
        
        # Keep only recent conversations (last 100)
        if len(self.conversation_memories[user_id]) > 100:
            self.conversation_memories[user_id] = self.conversation_memories[user_id][-100:]
    
    async def get_conversation_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get conversation history for user"""
        if user_id not in self.conversation_memories:
            return []
        
        recent_memories = self.conversation_memories[user_id][-limit:]
        
        return [
            {
                "timestamp": memory.timestamp.isoformat(),
                "user_message": memory.user_message,
                "ai_response": memory.ai_response,
                "context": memory.context.value,
                "emotional_tone": memory.emotional_tone,
                "topics": memory.topics
            }
            for memory in recent_memories
        ]
    
    async def get_conversation_insights(self, user_id: str) -> Dict[str, Any]:
        """Get insights about user's conversation patterns"""
        if user_id not in self.conversation_memories:
            return {"message": "No conversation history available"}
        
        memories = self.conversation_memories[user_id]
        
        # Analyze patterns
        contexts = [memory.context.value for memory in memories]
        emotional_tones = [memory.emotional_tone for memory in memories]
        topics = []
        for memory in memories:
            topics.extend(memory.topics)
        
        # Count frequencies
        context_counts = {}
        for context in contexts:
            context_counts[context] = context_counts.get(context, 0) + 1
        
        emotional_counts = {}
        for tone in emotional_tones:
            emotional_counts[tone] = emotional_counts.get(tone, 0) + 1
        
        topic_counts = {}
        for topic in topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        return {
            "total_conversations": len(memories),
            "most_common_context": max(context_counts.items(), key=lambda x: x[1])[0] if context_counts else "unknown",
            "most_common_emotional_tone": max(emotional_counts.items(), key=lambda x: x[1])[0] if emotional_counts else "neutral",
            "top_topics": sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:5],
            "conversation_frequency": len(memories) / max(1, (datetime.utcnow() - memories[0].timestamp).days) if memories else 0
        }
    
    def get_conversation_statistics(self) -> Dict[str, Any]:
        """Get overall conversation statistics"""
        total_users = len(self.conversation_memories)
        total_conversations = sum(len(memories) for memories in self.conversation_memories.values())
        active_sessions = len(self.conversation_states)
        
        return {
            "total_users": total_users,
            "total_conversations": total_conversations,
            "active_sessions": active_sessions,
            "average_conversations_per_user": total_conversations / max(1, total_users)
        }


# Global conversation engine instance
_conversation_engine: Optional[NaturalConversationEngine] = None


def get_natural_conversation_engine() -> NaturalConversationEngine:
    """Get global natural conversation engine instance"""
    global _conversation_engine
    if _conversation_engine is None:
        _conversation_engine = NaturalConversationEngine()
    return _conversation_engine


async def chat_with_ai(user_message: str, user_id: str = "default", session_id: str = None) -> str:
    """Simple function to chat with the AI"""
    engine = get_natural_conversation_engine()
    return await engine.process_message(user_id, user_message, session_id)