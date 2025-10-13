"""
JARVIS Protocol - Conversation Manager
Handles natural conversation flow and context management
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from core.logger import get_logger

logger = get_logger('protocols.jarvis.conversation')


class ConversationManager:
    """
    Manages conversation context and history for JARVIS Protocol
    
    Features:
    - Context preservation
    - Conversation history management
    - Topic tracking
    - Emotional state monitoring
    """
    
    def __init__(self, max_history: int = 50):
        """
        Initialize conversation manager
        
        Args:
            max_history: Maximum conversation history to maintain
        """
        self.history: List[Dict[str, Any]] = []
        self.max_history = max_history
        self.current_topic = None
        self.user_profile = {}
        
        logger.info("JARVIS Conversation Manager initialized")
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """
        Add message to conversation history
        
        Args:
            role: Message role ('user' or 'assistant')
            content: Message content
            metadata: Optional metadata dictionary
        """
        message = {
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        self.history.append(message)
        
        # Maintain max history
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        
        logger.debug(f"Added {role} message to history")
    
    def get_context(self, last_n: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent conversation context
        
        Args:
            last_n: Number of recent messages to retrieve
            
        Returns:
            List of recent messages
        """
        return self.history[-last_n:] if self.history else []
    
    def clear_history(self):
        """Clear conversation history"""
        self.history = []
        logger.info("Conversation history cleared")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get conversation summary"""
        return {
            'total_messages': len(self.history),
            'current_topic': self.current_topic,
            'last_interaction': self.history[-1]['timestamp'] if self.history else None,
            'user_profile': self.user_profile
        }


# Placeholder for future expansion
__all__ = ['ConversationManager']

