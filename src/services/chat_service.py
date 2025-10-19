"""
Atulya Tantra - Chat Service
Version: 2.5.0
Orchestrates chat operations and conversation management
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import uuid
import logging
from src.services.ai_service import AIService, AIRequest, AIResponse
from src.core.ai.context import ConversationMemory, Message

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """Chat message data structure"""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    metadata: Optional[Dict] = None


@dataclass
class ChatResponse:
    """Chat response data structure"""
    response: str
    conversation_id: str
    metadata: Dict
    timestamp: str


class ChatService:
    """Orchestrates chat operations and conversation management"""
    
    def __init__(self, ai_service: AIService, conversation_memory: ConversationMemory):
        self.ai_service = ai_service
        self.conversation_memory = conversation_memory
    
    async def process_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> ChatResponse:
        """Process a chat message and return AI response"""
        
        # Generate conversation ID if not provided
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
        
        # Create AI request
        ai_request = AIRequest(
            message=message,
            context=[],  # Context is now handled by conversation memory
            user_id=user_id
        )
        
        # Generate AI response with conversation context
        ai_response = await self.ai_service.generate_response(
            ai_request, conversation_id
        )
        
        logger.info(f"Processed message for conversation {conversation_id}")
        
        return ChatResponse(
            response=ai_response.content,
            conversation_id=conversation_id,
            metadata=ai_response.metadata,
            timestamp=datetime.now().isoformat()
        )
    
    async def get_history(self, conversation_id: str, user_id: Optional[str] = None) -> List[Dict]:
        """Get conversation history"""
        messages = await self.conversation_memory.get_conversation_history(conversation_id)
        return [msg.to_dict() for msg in messages]
    
    async def delete_conversation(self, conversation_id: str, user_id: Optional[str] = None):
        """Delete conversation"""
        await self.conversation_memory.delete_conversation(conversation_id)
        logger.info(f"Deleted conversation {conversation_id}")
    
    async def get_conversation_summary(self, conversation_id: str) -> Optional[str]:
        """Get conversation summary"""
        return await self.conversation_memory.get_conversation_summary(conversation_id)
    
    async def get_conversation_stats(self) -> Dict[str, Any]:
        """Get conversation statistics"""
        return self.conversation_memory.get_conversation_stats()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of chat service"""
        return {
            "chat_service": True,
            "ai_service": await self.ai_service.health_check(),
            "conversation_memory": True
        }
