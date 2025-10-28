"""
Assistant Core for Atulya Tantra
Conversational AI and user interaction
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

class AssistantCore:
    """Core assistant functionality for user interaction"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.conversation_history = []
        self.user_preferences = {}
        self.context = {}
        
    async def process_message(self, message: str, user_id: str = "default") -> str:
        """Process user message and generate response"""
        try:
            # Add to conversation history
            self.conversation_history.append({
                'user_id': user_id,
                'message': message,
                'timestamp': datetime.now().isoformat()
            })
            
            # Analyze message
            analysis = await self.analyze_message(message)
            
            # Generate response
            response = await self.generate_response(analysis, user_id)
            
            # Add response to history
            self.conversation_history.append({
                'user_id': 'assistant',
                'message': response,
                'timestamp': datetime.now().isoformat()
            })
            
            return response
            
        except Exception as e:
            return f"I apologize, but I encountered an error: {str(e)}"
    
    async def analyze_message(self, message: str) -> Dict[str, Any]:
        """Analyze user message for intent and context"""
        message_lower = message.lower()
        
        # Simple intent detection
        if any(word in message_lower for word in ['hello', 'hi', 'hey']):
            intent = 'greeting'
        elif any(word in message_lower for word in ['help', 'assist', 'support']):
            intent = 'help_request'
        elif any(word in message_lower for word in ['thank', 'thanks']):
            intent = 'gratitude'
        else:
            intent = 'general_query'
        
        return {
            'intent': intent,
            'sentiment': 'neutral',
            'complexity': 'medium',
            'requires_action': False
        }
    
    async def generate_response(self, analysis: Dict[str, Any], user_id: str) -> str:
        """Generate appropriate response based on analysis"""
        intent = analysis.get('intent', 'general_query')
        
        if intent == 'greeting':
            return "Hello! I'm Tantra, your AI assistant. How can I help you today?"
        elif intent == 'help_request':
            return "I'm here to help! I can assist with various tasks, answer questions, and provide information. What do you need help with?"
        elif intent == 'gratitude':
            return "You're welcome! I'm happy to help. Is there anything else you'd like to know?"
        else:
            return "I understand your message. Let me help you with that. Could you provide more details about what you need?"
    
    def get_conversation_history(self, user_id: str = "default", limit: int = 10) -> List[Dict[str, Any]]:
        """Get conversation history for a user"""
        user_messages = [
            msg for msg in self.conversation_history 
            if msg.get('user_id') == user_id
        ]
        return user_messages[-limit:]
    
    def set_user_preference(self, user_id: str, key: str, value: Any):
        """Set user preference"""
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = {}
        self.user_preferences[user_id][key] = value
    
    def get_user_preference(self, user_id: str, key: str, default: Any = None) -> Any:
        """Get user preference"""
        return self.user_preferences.get(user_id, {}).get(key, default)