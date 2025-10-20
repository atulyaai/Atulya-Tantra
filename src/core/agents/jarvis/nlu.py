"""
Atulya Tantra - JARVIS Natural Language Understanding
Version: 2.5.0
NLU system for intent recognition, context management, and ambiguity handling
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import re
import json
from datetime import datetime
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """Types of user intents"""
    QUESTION = "question"
    COMMAND = "command"
    CHAT = "chat"
    REQUEST = "request"
    COMPLAINT = "complaint"
    COMPLIMENT = "compliment"
    GREETING = "greeting"
    FAREWELL = "farewell"
    CLARIFICATION = "clarification"
    FOLLOW_UP = "follow_up"


class ContextType(Enum):
    """Types of conversational context"""
    TECHNICAL = "technical"
    PERSONAL = "personal"
    WORK = "work"
    CREATIVE = "creative"
    EDUCATIONAL = "educational"
    CASUAL = "casual"


@dataclass
class IntentResult:
    """Result of intent recognition"""
    intent: IntentType
    confidence: float
    parameters: Dict[str, Any]
    entities: List[Dict[str, Any]]
    context_clues: List[str]


@dataclass
class ContextResult:
    """Result of context analysis"""
    context_type: ContextType
    confidence: float
    topics: List[str]
    entities: List[str]
    sentiment: str
    urgency: float  # 0.0 to 1.0


@dataclass
class AmbiguityResult:
    """Result of ambiguity analysis"""
    is_ambiguous: bool
    ambiguity_types: List[str]
    interpretations: List[Dict[str, Any]]
    clarifying_questions: List[str]
    confidence_scores: List[float]


class NaturalLanguageUnderstanding:
    """NLU system for JARVIS conversational intelligence"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.conversation_history = defaultdict(deque)  # conversation_id -> deque of messages
        self.context_memory = defaultdict(dict)  # conversation_id -> context_data
        self.entity_memory = defaultdict(set)  # conversation_id -> entities
        self.topic_tracking = defaultdict(list)  # conversation_id -> topics
        
        # Intent patterns
        self.intent_patterns = self._initialize_intent_patterns()
        
        # Context patterns
        self.context_patterns = self._initialize_context_patterns()
        
        logger.info("NaturalLanguageUnderstanding initialized")
    
    def _initialize_intent_patterns(self) -> Dict[IntentType, List[str]]:
        """Initialize intent recognition patterns"""
        return {
            IntentType.QUESTION: [
                r"\?$", r"what is", r"how do", r"why", r"when", r"where", r"can you", r"could you",
                r"would you", r"tell me", r"explain", r"describe"
            ],
            IntentType.COMMAND: [
                r"^do ", r"^create ", r"^make ", r"^generate ", r"^build ", r"^write ",
                r"^calculate ", r"^analyze ", r"^find ", r"^search ", r"^show me"
            ],
            IntentType.REQUEST: [
                r"please ", r"could you please", r"would you mind", r"i need", r"i want",
                r"help me", r"assist me", r"support me"
            ],
            IntentType.COMPLAINT: [
                r"problem", r"issue", r"error", r"bug", r"broken", r"not working",
                r"frustrated", r"annoying", r"wrong", r"mistake"
            ],
            IntentType.COMPLIMENT: [
                r"thank you", r"thanks", r"great", r"awesome", r"excellent", r"perfect",
                r"amazing", r"wonderful", r"helpful", r"appreciate"
            ],
            IntentType.GREETING: [
                r"^hello", r"^hi", r"^hey", r"^good morning", r"^good afternoon",
                r"^good evening", r"^greetings"
            ],
            IntentType.FAREWELL: [
                r"bye", r"goodbye", r"see you", r"talk to you later", r"have a good",
                r"take care", r"farewell"
            ],
            IntentType.CLARIFICATION: [
                r"what do you mean", r"i don't understand", r"could you clarify",
                r"explain more", r"be more specific", r"elaborate"
            ],
            IntentType.FOLLOW_UP: [
                r"also", r"and", r"additionally", r"furthermore", r"moreover",
                r"what about", r"how about", r"related to"
            ]
        }
    
    def _initialize_context_patterns(self) -> Dict[ContextType, List[str]]:
        """Initialize context recognition patterns"""
        return {
            ContextType.TECHNICAL: [
                "code", "programming", "algorithm", "debug", "function", "class", "variable",
                "database", "API", "server", "client", "framework", "library", "syntax"
            ],
            ContextType.PERSONAL: [
                "family", "friend", "relationship", "feel", "emotion", "personal", "private",
                "life", "home", "health", "mood", "anxiety", "stress", "happy", "sad"
            ],
            ContextType.WORK: [
                "work", "job", "career", "meeting", "project", "deadline", "boss", "colleague",
                "office", "business", "company", "professional", "resume", "interview"
            ],
            ContextType.CREATIVE: [
                "creative", "art", "design", "story", "poetry", "music", "drawing", "writing",
                "brainstorm", "idea", "inspiration", "imagination", "artistic"
            ],
            ContextType.EDUCATIONAL: [
                "learn", "study", "education", "school", "university", "course", "lesson",
                "teacher", "student", "homework", "exam", "knowledge", "research"
            ],
            ContextType.CASUAL: [
                "weather", "food", "movie", "book", "game", "sport", "travel", "vacation",
                "weekend", "fun", "entertainment", "hobby", "relax"
            ]
        }
    
    async def recognize_intent(self, message: str, conversation_id: str) -> IntentResult:
        """Recognize user intent from message"""
        
        message_lower = message.lower().strip()
        intent_scores = defaultdict(float)
        entities = []
        parameters = {}
        context_clues = []
        
        # Score each intent type
        for intent_type, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    intent_scores[intent_type] += 1.0
                    context_clues.append(f"Pattern match: {pattern}")
        
        # Normalize scores
        total_score = sum(intent_scores.values())
        if total_score > 0:
            for intent in intent_scores:
                intent_scores[intent] /= total_score
        
        # Get highest scoring intent
        if intent_scores:
            best_intent = max(intent_scores.items(), key=lambda x: x[1])
            intent_type, confidence = best_intent
        else:
            # Default to chat if no clear intent
            intent_type = IntentType.CHAT
            confidence = 0.5
        
        # Extract entities and parameters
        entities = await self._extract_entities(message)
        parameters = await self._extract_parameters(message, intent_type)
        
        # Add to conversation history
        self.conversation_history[conversation_id].append({
            "message": message,
            "intent": intent_type,
            "timestamp": datetime.now()
        })
        
        # Keep only recent history (last 20 messages)
        if len(self.conversation_history[conversation_id]) > 20:
            self.conversation_history[conversation_id] = deque(
                list(self.conversation_history[conversation_id])[-20:],
                maxlen=20
            )
        
        return IntentResult(
            intent=intent_type,
            confidence=confidence,
            parameters=parameters,
            entities=entities,
            context_clues=context_clues
        )
    
    async def analyze_context(
        self,
        message: str,
        conversation_id: str,
        intent_result: IntentResult
    ) -> ContextResult:
        """Analyze conversational context"""
        
        message_lower = message.lower()
        context_scores = defaultdict(float)
        topics = []
        entities = []
        sentiment = "neutral"
        urgency = 0.0
        
        # Score context types
        for context_type, keywords in self.context_patterns.items():
            for keyword in keywords:
                if keyword in message_lower:
                    context_scores[context_type] += 1.0
                    topics.append(keyword)
        
        # Determine context type
        if context_scores:
            best_context = max(context_scores.items(), key=lambda x: x[1])
            context_type, confidence = best_context
        else:
            context_type = ContextType.CASUAL
            confidence = 0.5
        
        # Extract entities
        entities = await self._extract_entities(message)
        
        # Analyze sentiment (simple keyword-based)
        positive_words = ["good", "great", "awesome", "excellent", "happy", "love", "like"]
        negative_words = ["bad", "terrible", "awful", "hate", "dislike", "angry", "frustrated"]
        
        positive_count = sum(1 for word in positive_words if word in message_lower)
        negative_count = sum(1 for word in negative_words if word in message_lower)
        
        if positive_count > negative_count:
            sentiment = "positive"
        elif negative_count > positive_count:
            sentiment = "negative"
        
        # Analyze urgency
        urgent_keywords = ["urgent", "asap", "immediately", "emergency", "critical", "important"]
        urgency = sum(0.2 for keyword in urgent_keywords if keyword in message_lower)
        urgency = min(1.0, urgency)
        
        # Update context memory
        self.context_memory[conversation_id].update({
            "last_context": context_type.value,
            "last_topics": topics,
            "last_sentiment": sentiment,
            "last_urgency": urgency,
            "timestamp": datetime.now()
        })
        
        # Update topic tracking
        self.topic_tracking[conversation_id].extend(topics)
        if len(self.topic_tracking[conversation_id]) > 10:
            self.topic_tracking[conversation_id] = self.topic_tracking[conversation_id][-10:]
        
        return ContextResult(
            context_type=context_type,
            confidence=confidence,
            topics=topics,
            entities=entities,
            sentiment=sentiment,
            urgency=urgency
        )
    
    async def detect_ambiguity(
        self,
        message: str,
        conversation_id: str,
        intent_result: IntentResult,
        context_result: ContextResult
    ) -> AmbiguityResult:
        """Detect ambiguity in user message"""
        
        ambiguity_types = []
        interpretations = []
        clarifying_questions = []
        confidence_scores = []
        
        # Check for pronoun ambiguity
        pronouns = ["it", "this", "that", "they", "them", "he", "she"]
        if any(pronoun in message.lower() for pronoun in pronouns):
            ambiguity_types.append("pronoun_reference")
            clarifying_questions.append("What specifically are you referring to?")
        
        # Check for multiple possible interpretations
        if intent_result.confidence < 0.7:
            ambiguity_types.append("intent_ambiguity")
            clarifying_questions.append("Could you clarify what you'd like me to help you with?")
        
        # Check for context ambiguity
        if context_result.confidence < 0.6:
            ambiguity_types.append("context_ambiguity")
            clarifying_questions.append("Could you provide more context about this topic?")
        
        # Check for missing information
        wh_words = ["what", "where", "when", "why", "how", "who"]
        if any(wh_word in message.lower() for wh_word in wh_words) and len(message.split()) < 5:
            ambiguity_types.append("incomplete_question")
            clarifying_questions.append("Could you provide more details about your question?")
        
        # Generate interpretations
        if intent_result.intent == IntentType.QUESTION:
            interpretations.append({
                "type": "information_request",
                "description": "User is asking for information",
                "confidence": intent_result.confidence
            })
        elif intent_result.intent == IntentType.COMMAND:
            interpretations.append({
                "type": "action_request",
                "description": "User wants me to perform an action",
                "confidence": intent_result.confidence
            })
        elif intent_result.intent == IntentType.CHAT:
            interpretations.append({
                "type": "casual_conversation",
                "description": "User is having a casual conversation",
                "confidence": intent_result.confidence
            })
        
        confidence_scores = [interp["confidence"] for interp in interpretations]
        
        is_ambiguous = len(ambiguity_types) > 0 or max(confidence_scores, default=0) < 0.8
        
        return AmbiguityResult(
            is_ambiguous=is_ambiguous,
            ambiguity_types=ambiguity_types,
            interpretations=interpretations,
            clarifying_questions=clarifying_questions,
            confidence_scores=confidence_scores
        )
    
    async def _extract_entities(self, message: str) -> List[Dict[str, Any]]:
        """Extract entities from message (simple implementation)"""
        
        entities = []
        message_lower = message.lower()
        
        # Extract potential names (capitalized words)
        name_pattern = r'\b[A-Z][a-z]+\b'
        names = re.findall(name_pattern, message)
        for name in names:
            entities.append({
                "type": "person",
                "value": name,
                "confidence": 0.6
            })
        
        # Extract numbers
        number_pattern = r'\b\d+\b'
        numbers = re.findall(number_pattern, message)
        for number in numbers:
            entities.append({
                "type": "number",
                "value": number,
                "confidence": 0.9
            })
        
        # Extract URLs
        url_pattern = r'https?://\S+'
        urls = re.findall(url_pattern, message)
        for url in urls:
            entities.append({
                "type": "url",
                "value": url,
                "confidence": 0.95
            })
        
        # Extract email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, message)
        for email in emails:
            entities.append({
                "type": "email",
                "value": email,
                "confidence": 0.95
            })
        
        return entities
    
    async def _extract_parameters(self, message: str, intent_type: IntentType) -> Dict[str, Any]:
        """Extract parameters based on intent type"""
        
        parameters = {}
        message_lower = message.lower()
        
        if intent_type == IntentType.COMMAND:
            # Extract action and target
            action_patterns = [
                r"(create|make|generate|build|write)\s+(.+?)(?:\s|$)",
                r"(calculate|analyze|find|search)\s+(.+?)(?:\s|$)"
            ]
            
            for pattern in action_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    parameters["action"] = match.group(1)
                    parameters["target"] = match.group(2)
                    break
        
        elif intent_type == IntentType.QUESTION:
            # Extract question type and subject
            question_patterns = [
                r"(what|how|why|when|where|who)\s+(.+?)(?:\?|$)",
                r"(explain|describe|tell me about)\s+(.+?)(?:\s|$)"
            ]
            
            for pattern in question_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    parameters["question_type"] = match.group(1)
                    parameters["subject"] = match.group(2)
                    break
        
        return parameters
    
    async def get_conversation_context(self, conversation_id: str) -> Dict[str, Any]:
        """Get comprehensive conversation context"""
        
        context = {
            "conversation_id": conversation_id,
            "message_count": len(self.conversation_history[conversation_id]),
            "recent_intents": [],
            "common_topics": [],
            "context_memory": {},
            "entities": list(self.entity_memory[conversation_id])
        }
        
        # Get recent intents
        recent_messages = list(self.conversation_history[conversation_id])[-5:]
        context["recent_intents"] = [
            {
                "intent": msg["intent"].value,
                "timestamp": msg["timestamp"].isoformat()
            }
            for msg in recent_messages
        ]
        
        # Get common topics
        if conversation_id in self.topic_tracking:
            topic_counts = defaultdict(int)
            for topic in self.topic_tracking[conversation_id]:
                topic_counts[topic] += 1
            
            context["common_topics"] = [
                {"topic": topic, "count": count}
                for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            ]
        
        # Get context memory
        if conversation_id in self.context_memory:
            context["context_memory"] = self.context_memory[conversation_id]
        
        return context
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of NLU system"""
        return {
            "nlu_system": True,
            "active_conversations": len(self.conversation_history),
            "total_patterns": sum(len(patterns) for patterns in self.intent_patterns.values()),
            "context_patterns": sum(len(patterns) for patterns in self.context_patterns.values())
        }
