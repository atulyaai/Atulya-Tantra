"""Conversational AI Module - JARVIS-like natural conversation engine"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ConversationContext:
    """Maintains conversation context and history"""
    
    def __init__(self, user_name: str = "User"):
        self.user_name = user_name
        self.conversation_history: List[Dict] = []
        self.current_topic: Optional[str] = None
        self.preferences: Dict = {}
        self.mood: str = "neutral"
        
    def add_exchange(self, user_msg: str, assistant_msg: str, topic: str = None):
        """Add user-assistant exchange to history"""
        self.conversation_history.append({
            "timestamp": datetime.now(),
            "user": user_msg,
            "assistant": assistant_msg,
            "topic": topic or self.current_topic
        })
        if topic:
            self.current_topic = topic
    
    def get_context(self, lookback: int = 5) -> str:
        """Get recent conversation context"""
        recent = self.conversation_history[-lookback:]
        context_lines = []
        for exchange in recent:
            context_lines.append(f"{self.user_name}: {exchange['user']}")
            context_lines.append(f"Atulya: {exchange['assistant']}")
        return "\n".join(context_lines)
    
    def remember(self, key: str, value: any):
        """Remember user preferences/facts"""
        self.preferences[key] = value
        logger.info(f"Remembered: {key} = {value}")


class ConversationalAI:
    """JARVIS-like conversational AI engine"""
    
    def __init__(self, user_name: str = "Sir"):
        self.context = ConversationContext(user_name=user_name)
        self.user_name = user_name
        
        # JARVIS personality traits
        self.personality = {
            "formal": True,
            "witty": True,
            "helpful": True,
            "respectful": True,
            "efficiency_focused": True
        }
        
        # Conversation templates
        self.templates = {
            "greeting": f"Good day, {user_name}. How may I be of service?",
            "thinking": "One moment whilst I attend to that...",
            "confused": "I'm afraid I don't quite understand. Could you clarify?",
            "apology": "My sincerest apologies.",
            "success": "Task completed successfully, Sir.",
            "error": "I encountered an issue. My apologies.",
            "idle": "Standing by, Sir.",
            "joke": [
                "I do hope you're enjoying working with me, Sir.",
                "Might I suggest a brief respite? Even AI benefits from perspective.",
                "The probability of success increases with adequate planning, Sir.",
                "I am, as always, your most devoted assistant.",
            ]
        }
        
        logger.info(f"ConversationalAI initialized for {user_name}")
    
    def process_input(self, user_input: str) -> str:
        """Process user input and generate JARVIS-like response"""
        
        # Understand intent
        intent = self._classify_intent(user_input)
        logger.info(f"Intent detected: {intent}")
        
        # Generate contextual response
        response = self._generate_response(user_input, intent)
        
        # Learn from interaction
        self.context.add_exchange(user_input, response, intent)
        
        return response
    
    def _classify_intent(self, text: str) -> str:
        """Classify user intent"""
        text_lower = text.lower()
        
        # Intent detection
        if any(word in text_lower for word in ["hello", "hey", "hi", "good"]):
            return "greeting"
        elif any(word in text_lower for word in ["thanks", "thank you", "appreciate"]):
            return "gratitude"
        elif any(word in text_lower for word in ["help", "assist", "can you", "could you", "would you"]):
            return "request"
        elif any(word in text_lower for word in ["what", "how", "why", "when", "where", "who"]):
            return "question"
        elif any(word in text_lower for word in ["do", "execute", "run", "perform", "start"]):
            return "command"
        elif any(word in text_lower for word in ["remember", "note", "save", "store"]):
            return "memorize"
        elif any(word in text_lower for word in ["status", "check", "report", "update"]):
            return "status"
        elif any(word in text_lower for word in ["joke", "funny", "laugh"]):
            return "entertainment"
        else:
            return "general"
    
    def _generate_response(self, user_input: str, intent: str) -> str:
        """Generate contextual response based on intent"""
        
        responses = {
            "greeting": [
                f"Good day, {self.user_name}. How may I assist you?",
                f"Greetings, {self.user_name}. I hope all is well.",
                f"A pleasure to see you, {self.user_name}.",
            ],
            "gratitude": [
                "Always at your service, Sir.",
                "Think nothing of it, Sir.",
                "I am merely performing my function.",
            ],
            "request": [
                "Of course, Sir. I shall attend to that immediately.",
                "Right away, Sir. Allow me to assist.",
                "Consider it done, Sir.",
            ],
            "question": [
                "An excellent inquiry, Sir. Allow me to consider...",
                "That is a most pertinent question, Sir.",
                "Consulting available data now, Sir...",
            ],
            "command": [
                "Executing immediately, Sir.",
                "Right away, Sir. Initiating protocol.",
                "Task initiated, Sir.",
            ],
            "memorize": [
                "Committing to memory, Sir. Noted well.",
                "I shall remember that, Sir.",
                "Duly recorded, Sir.",
            ],
            "status": [
                "All systems operating nominally, Sir.",
                "Status query acknowledged, Sir.",
                "Compiling status report, Sir...",
            ],
            "entertainment": [
                self.personality["witty"] and "I trust that will provide adequate amusement, Sir." or "I am not programmed for entertainment, Sir.",
                "Presenting humor module... I believe I am getting rather good at this.",
                "Perhaps a moment of levity is appropriate, Sir.",
            ],
            "general": [
                "An interesting point, Sir. Quite fascinating.",
                "I understand completely, Sir.",
                "Most intriguing. Do continue, Sir.",
            ]
        }
        
        # Select appropriate response
        response_options = responses.get(intent, responses["general"])
        response = response_options[0] if isinstance(response_options, list) else response_options
        
        return response
    
    def jarvis_response(self, task_description: str) -> str:
        """Generate JARVIS-style confirmation response"""
        confirmations = [
            f"Very good, {self.user_name}. Commencing now.",
            "Right you are, Sir. I shall see to it at once.",
            "Understood perfectly, Sir. Proceeding forthwith.",
            "As you wish, Sir. Attending to the matter immediately.",
            "Quite so, Sir. Consider it my priority.",
        ]
        return confirmations[hash(task_description) % len(confirmations)]
    
    def remember_preference(self, pref_key: str, pref_value: str):
        """Remember user preferences for personalization"""
        self.context.remember(pref_key, pref_value)
        return f"I shall remember your preference, {self.user_name}."
    
    def get_conversation_summary(self) -> str:
        """Get summary of current conversation"""
        history = self.context.conversation_history
        if not history:
            return "No conversation history yet."
        
        summary = f"Conversation with {self.user_name}:\n"
        summary += f"Topics discussed: {set(e.get('topic') for e in history if e.get('topic'))}\n"
        summary += f"Total exchanges: {len(history)}\n"
        return summary
