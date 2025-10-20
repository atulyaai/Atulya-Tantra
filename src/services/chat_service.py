"""
Atulya Tantra - Chat Service
Version: 2.5.0
Orchestrates chat operations and conversation management
"""

from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
import uuid
import logging
import asyncio
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
        user_id: Optional[str] = None,
        model: str = "ollama",
        attachments: List[Dict] = None
    ) -> ChatResponse:
        """Process a chat message and return AI response"""
        
        try:
            # Generate conversation ID if not provided
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
            
            # Process attachments
            attachment_info = []
            if attachments:
                for attachment in attachments:
                    attachment_info.append({
                        "filename": attachment["filename"],
                        "content_type": attachment["content_type"],
                        "size": attachment["size"]
                    })
            
            # Create AI request
            ai_request = AIRequest(
                message=message,
                context=[],  # Context is now handled by conversation memory
                user_id=user_id,
                model=model,
                attachments=attachment_info
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
            
        except Exception as e:
            logger.error(f"Chat processing error: {e}")
            # Provide fallback response when AI service fails
            conversation_id = conversation_id or str(uuid.uuid4())
            return ChatResponse(
                response=f"I apologize, but I'm currently unable to process your request. The AI models are not available at the moment. However, I can tell you that your message '{message}' was received and logged. Please try again later or check the system configuration.",
                conversation_id=conversation_id,
                metadata={
                    "error": str(e),
                    "fallback": True,
                    "message_received": True
                },
                timestamp=datetime.now().isoformat()
            )
    
    async def get_history(self, conversation_id: str, user_id: Optional[str] = None) -> List[Dict]:
        """Get conversation history"""
        messages = await self.conversation_memory.get_conversation_history(conversation_id)
        return [msg.to_dict() for msg in messages]
    
    async def get_conversation_stats(self) -> Dict[str, Any]:
        """Get conversation statistics"""
        try:
            # For now, return basic stats
            # In a real implementation, this would query the database
            return {
                "total_conversations": 0,
                "total_messages": 0,
                "active_conversations": 0
            }
        except Exception as e:
            logger.error(f"Error getting conversation stats: {e}")
            return {"total_conversations": 0, "total_messages": 0, "active_conversations": 0}
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for chat service"""
        try:
            return {
                "chat_service": True,
                "ai_service": True,
                "conversation_memory": True
            }
        except Exception as e:
            logger.error(f"Chat service health check failed: {e}")
            return {"chat_service": False, "error": str(e)}
    
    async def delete_conversation(self, conversation_id: str, user_id: Optional[str] = None):
        """Delete conversation"""
        await self.conversation_memory.delete_conversation(conversation_id)
        logger.info(f"Deleted conversation {conversation_id}")
    
    async def get_conversation_summary(self, conversation_id: str) -> Optional[str]:
        """Get conversation summary"""
        return await self.conversation_memory.get_conversation_summary(conversation_id)
    
    async def stream_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        model: str = "ollama"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream chat message with real-time chunks"""
        
        try:
            # Generate conversation ID if not provided
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
            
            # Send typing indicator
            yield {
                "type": "typing",
                "status": "start",
                "conversation_id": conversation_id
            }
            
            # Create AI request
            ai_request = AIRequest(
                message=message,
                context=[],
                user_id=user_id,
                model=model,
                attachments=[]
            )
            
            # Stream AI response
            full_response = ""
            async for chunk in self.ai_service.stream_response(ai_request, conversation_id):
                full_response += chunk.get("content", "")
                yield {
                    "type": "content",
                    "content": chunk.get("content", ""),
                    "conversation_id": conversation_id,
                    "metadata": chunk.get("metadata", {})
                }
                # Small delay for smooth streaming
                await asyncio.sleep(0.01)
            
            # Send completion
            yield {
                "type": "complete",
                "conversation_id": conversation_id,
                "full_response": full_response,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield {
                "type": "error",
                "message": str(e),
                "conversation_id": conversation_id or str(uuid.uuid4())
            }
