"""
Natural Conversation Engine for Atulya Tantra AGI
Handles natural language understanding and response generation
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from ..config.logging import get_logger
from ..config.exceptions import ConversationError, ValidationError
from ..brain.llm_provider import LLMProvider
from ..memory.conversation_memory import ConversationMemory
from ..jarvis.sentiment_analyzer import SentimentAnalyzer
from ..jarvis.personality_engine import PersonalityEngine

logger = get_logger(__name__)


@dataclass
class ConversationContext:
    """Conversation context"""
    user_id: str
    session_id: str
    message: str
    timestamp: str
    sentiment: str
    intent: str
    entities: List[Dict[str, Any]]
    response_type: str
    confidence: float


@dataclass
class ConversationResponse:
    """Conversation response"""
    message: str
    response_type: str
    confidence: float
    timestamp: str
    metadata: Dict[str, Any]


class NaturalConversationEngine:
    """Natural conversation engine"""
    
    def __init__(
        self,
        llm_provider: LLMProvider = None,
        memory: ConversationMemory = None,
        sentiment_analyzer: SentimentAnalyzer = None,
        personality_engine: PersonalityEngine = None
    ):
        self.llm_provider = llm_provider
        self.memory = memory
        self.sentiment_analyzer = sentiment_analyzer
        self.personality_engine = personality_engine
        
        # Conversation patterns
        self.greeting_patterns = [
            r'\b(hi|hello|hey|greetings|good morning|good afternoon|good evening)\b',
            r'\b(how are you|how do you do|what\'s up|what\'s new)\b',
            r'\b(nice to meet you|pleased to meet you)\b'
        ]
        
        self.question_patterns = [
            r'\b(what|when|where|why|how|who|which|can you|could you|would you)\b',
            r'\b(explain|describe|tell me|show me|help me)\b',
            r'\b(do you know|can you help|are you able)\b'
        ]
        
        self.command_patterns = [
            r'\b(create|make|build|generate|write|code|develop)\b',
            r'\b(analyze|examine|review|check|inspect)\b',
            r'\b(delete|remove|clear|reset|stop|cancel)\b',
            r'\b(start|begin|launch|run|execute|perform)\b'
        ]
        
        self.thank_you_patterns = [
            r'\b(thank you|thanks|appreciate|grateful|much obliged)\b',
            r'\b(that\'s helpful|that\'s great|perfect|excellent)\b'
        ]
        
        self.goodbye_patterns = [
            r'\b(goodbye|bye|see you|farewell|take care|until next time)\b',
            r'\b(exit|quit|stop|end|finish)\b'
        ]
        
        # Response templates
        self.response_templates = {
            "greeting": [
                "Hello! I'm here to help you with your tasks.",
                "Hi there! How can I assist you today?",
                "Greetings! What would you like to work on?",
                "Hello! I'm ready to help you achieve your goals."
            ],
            "question": [
                "I'd be happy to help you with that question.",
                "Let me think about that and provide you with a helpful answer.",
                "That's a great question! Let me explain that for you.",
                "I can help you understand that better."
            ],
            "command": [
                "I'll help you with that task right away.",
                "Let me work on that for you.",
                "I'm on it! Let me handle that request.",
                "I'll get started on that immediately."
            ],
            "thank_you": [
                "You're very welcome! I'm glad I could help.",
                "My pleasure! I'm here whenever you need assistance.",
                "Happy to help! Feel free to ask if you need anything else.",
                "You're welcome! I enjoy helping you succeed."
            ],
            "goodbye": [
                "Goodbye! It was great working with you today.",
                "See you later! Feel free to come back anytime.",
                "Take care! I'll be here when you need me.",
                "Farewell! Have a wonderful day."
            ],
            "default": [
                "I understand. Let me help you with that.",
                "I'm here to assist you. What would you like to do?",
                "I can help you with that. Let me know what you need.",
                "I'm ready to help. What's your next step?"
            ]
        }
        
        logger.info("Initialized Natural Conversation Engine")
    
    async def process_message(
        self,
        user_id: str,
        session_id: str,
        message: str,
        context: Dict[str, Any] = None
    ) -> ConversationResponse:
        """Process a natural language message"""
        try:
            # Create conversation context
            conversation_context = await self._create_context(
                user_id, session_id, message, context
            )
            
            # Analyze sentiment
            if self.sentiment_analyzer:
                conversation_context.sentiment = await self._analyze_sentiment(message)
            
            # Classify intent
            conversation_context.intent = await self._classify_intent(message)
            
            # Extract entities
            conversation_context.entities = await self._extract_entities(message)
            
            # Determine response type
            conversation_context.response_type = await self._determine_response_type(
                conversation_context
            )
            
            # Generate response
            response = await self._generate_response(conversation_context)
            
            # Store in memory
            if self.memory:
                await self._store_conversation(conversation_context, response)
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            raise ConversationError(f"Failed to process message: {e}")
    
    async def _create_context(
        self,
        user_id: str,
        session_id: str,
        message: str,
        context: Dict[str, Any] = None
    ) -> ConversationContext:
        """Create conversation context"""
        return ConversationContext(
            user_id=user_id,
            session_id=session_id,
            message=message,
            timestamp=datetime.now().isoformat(),
            sentiment="neutral",
            intent="unknown",
            entities=[],
            response_type="default",
            confidence=0.0
        )
    
    async def _analyze_sentiment(self, message: str) -> str:
        """Analyze message sentiment"""
        try:
            if not self.sentiment_analyzer:
                return "neutral"
            
            sentiment_result = await self.sentiment_analyzer.analyze_sentiment(message)
            return sentiment_result.get("sentiment", "neutral")
            
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")
            return "neutral"
    
    async def _classify_intent(self, message: str) -> str:
        """Classify message intent"""
        try:
            message_lower = message.lower()
            
            # Check greeting patterns
            for pattern in self.greeting_patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    return "greeting"
            
            # Check question patterns
            for pattern in self.question_patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    return "question"
            
            # Check command patterns
            for pattern in self.command_patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    return "command"
            
            # Check thank you patterns
            for pattern in self.thank_you_patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    return "thank_you"
            
            # Check goodbye patterns
            for pattern in self.goodbye_patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    return "goodbye"
            
            return "unknown"
            
        except Exception as e:
            logger.error(f"Error classifying intent: {e}")
            return "unknown"
    
    async def _extract_entities(self, message: str) -> List[Dict[str, Any]]:
        """Extract entities from message"""
        try:
            entities = []
            
            # Simple entity extraction patterns
            patterns = {
                "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                "url": r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
                "phone": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
                "date": r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
                "time": r'\b\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\b',
                "number": r'\b\d+\b',
                "currency": r'\$\d+(?:\.\d{2})?\b'
            }
            
            for entity_type, pattern in patterns.items():
                matches = re.finditer(pattern, message, re.IGNORECASE)
                for match in matches:
                    entities.append({
                        "type": entity_type,
                        "value": match.group(),
                        "start": match.start(),
                        "end": match.end()
                    })
            
            return entities
            
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return []
    
    async def _determine_response_type(self, context: ConversationContext) -> str:
        """Determine response type based on context"""
        try:
            # Use intent to determine response type
            intent_response_map = {
                "greeting": "greeting",
                "question": "question",
                "command": "command",
                "thank_you": "thank_you",
                "goodbye": "goodbye"
            }
            
            response_type = intent_response_map.get(context.intent, "default")
            
            # Adjust based on sentiment
            if context.sentiment == "negative":
                response_type = "empathetic"
            elif context.sentiment == "positive":
                response_type = "enthusiastic"
            
            return response_type
            
        except Exception as e:
            logger.error(f"Error determining response type: {e}")
            return "default"
    
    async def _generate_response(self, context: ConversationContext) -> ConversationResponse:
        """Generate response based on context"""
        try:
            # Get response template
            templates = self.response_templates.get(context.response_type, self.response_templates["default"])
            
            # Select template (simple round-robin for now)
            template_index = hash(context.message) % len(templates)
            base_response = templates[template_index]
            
            # Enhance with personality
            if self.personality_engine:
                enhanced_response = await self._enhance_with_personality(
                    base_response, context
                )
            else:
                enhanced_response = base_response
            
            # Use LLM for complex responses if available
            if self.llm_provider and context.intent in ["question", "command"]:
                llm_response = await self._generate_llm_response(context)
                if llm_response:
                    enhanced_response = llm_response
            
            # Calculate confidence
            confidence = await self._calculate_confidence(context)
            
            return ConversationResponse(
                message=enhanced_response,
                response_type=context.response_type,
                confidence=confidence,
                timestamp=datetime.now().isoformat(),
                metadata={
                    "intent": context.intent,
                    "sentiment": context.sentiment,
                    "entities": context.entities,
                    "template_used": template_index
                }
            )
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return ConversationResponse(
                message="I apologize, but I'm having trouble processing your request right now.",
                response_type="error",
                confidence=0.0,
                timestamp=datetime.now().isoformat(),
                metadata={"error": str(e)}
            )
    
    async def _enhance_with_personality(
        self,
        response: str,
        context: ConversationContext
    ) -> str:
        """Enhance response with personality"""
        try:
            if not self.personality_engine:
                return response
            
            # Get personality traits
            traits = await self.personality_engine.get_personality_traits()
            
            # Apply personality modifications
            if traits.get("enthusiasm", 0.5) > 0.7:
                response = f"{response} I'm excited to help you with this!"
            
            if traits.get("empathy", 0.5) > 0.7 and context.sentiment == "negative":
                response = f"I understand this might be challenging. {response}"
            
            if traits.get("humor", 0.5) > 0.7:
                response = f"{response} (And I promise to keep things interesting!)"
            
            return response
            
        except Exception as e:
            logger.error(f"Error enhancing with personality: {e}")
            return response
    
    async def _generate_llm_response(self, context: ConversationContext) -> Optional[str]:
        """Generate response using LLM"""
        try:
            if not self.llm_provider:
                return None
            
            # Create prompt for LLM
            prompt = self._create_llm_prompt(context)
            
            # Generate response
            response = await self.llm_provider.generate_response(
                prompt=prompt,
                max_tokens=200,
                temperature=0.7
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            return None
    
    def _create_llm_prompt(self, context: ConversationContext) -> str:
        """Create prompt for LLM"""
        prompt = f"""
        You are JARVIS, an advanced AI assistant. Respond to the user's message naturally and helpfully.
        
        User message: {context.message}
        Intent: {context.intent}
        Sentiment: {context.sentiment}
        
        Respond in a conversational, helpful manner. Keep your response concise but informative.
        """
        
        return prompt.strip()
    
    async def _calculate_confidence(self, context: ConversationContext) -> float:
        """Calculate response confidence"""
        try:
            confidence = 0.5  # Base confidence
            
            # Increase confidence based on intent clarity
            if context.intent != "unknown":
                confidence += 0.2
            
            # Increase confidence based on sentiment analysis
            if context.sentiment != "neutral":
                confidence += 0.1
            
            # Increase confidence based on entity extraction
            if context.entities:
                confidence += 0.1
            
            # Cap at 1.0
            return min(confidence, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating confidence: {e}")
            return 0.5
    
    async def _store_conversation(
        self,
        context: ConversationContext,
        response: ConversationResponse
    ) -> None:
        """Store conversation in memory"""
        try:
            if not self.memory:
                return
            
            # Store user message
            await self.memory.add_message(
                user_id=context.user_id,
                session_id=context.session_id,
                message=context.message,
                message_type="user",
                metadata={
                    "intent": context.intent,
                    "sentiment": context.sentiment,
                    "entities": context.entities
                }
            )
            
            # Store assistant response
            await self.memory.add_message(
                user_id=context.user_id,
                session_id=context.session_id,
                message=response.message,
                message_type="assistant",
                metadata={
                    "response_type": response.response_type,
                    "confidence": response.confidence,
                    "template_used": response.metadata.get("template_used")
                }
            )
            
        except Exception as e:
            logger.error(f"Error storing conversation: {e}")
    
    async def get_conversation_history(
        self,
        user_id: str,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get conversation history"""
        try:
            if not self.memory:
                return []
            
            return await self.memory.get_conversation_history(
                user_id=user_id,
                session_id=session_id,
                limit=limit
            )
            
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []
    
    async def clear_conversation(
        self,
        user_id: str,
        session_id: str
    ) -> bool:
        """Clear conversation history"""
        try:
            if not self.memory:
                return False
            
            return await self.memory.clear_conversation(
                user_id=user_id,
                session_id=session_id
            )
            
        except Exception as e:
            logger.error(f"Error clearing conversation: {e}")
            return False


# Global conversation engine instance
_conversation_engine = None


def get_conversation_engine() -> NaturalConversationEngine:
    """Get global conversation engine instance"""
    global _conversation_engine
    if _conversation_engine is None:
        _conversation_engine = NaturalConversationEngine()
    return _conversation_engine


# Export public API
__all__ = [
    "ConversationContext",
    "ConversationResponse",
    "NaturalConversationEngine",
    "get_conversation_engine"
]