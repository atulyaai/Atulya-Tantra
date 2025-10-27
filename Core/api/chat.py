"""
Chat API endpoints for Atulya Tantra AGI
Handles conversation management and real-time chat
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..config.logging import get_logger
from ..config.exceptions import TantraException, ValidationError
from ..auth.jwt import verify_token
from ..auth.rbac import require_permission, Permission
from ..unified_agi_system import get_agi_system, SystemMode
from ..memory.conversation_memory import ConversationMemory

logger = get_logger(__name__)
chat_router = APIRouter()

# Pydantic models
class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000, description="User message")
    conversation_id: Optional[str] = Field(None, description="Conversation ID")
    user_id: str = Field(..., description="User ID")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    stream: bool = Field(False, description="Enable streaming response")

class ChatResponse(BaseModel):
    response: str = Field(..., description="AI response")
    conversation_id: str = Field(..., description="Conversation ID")
    message_id: str = Field(..., description="Message ID")
    timestamp: datetime = Field(..., description="Response timestamp")
    tokens_used: Optional[int] = Field(None, description="Tokens used")
    processing_time: float = Field(..., description="Processing time in seconds")

class ConversationInfo(BaseModel):
    conversation_id: str = Field(..., description="Conversation ID")
    title: str = Field(..., description="Conversation title")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    message_count: int = Field(..., description="Number of messages")
    user_id: str = Field(..., description="User ID")

class ConversationHistory(BaseModel):
    conversation_id: str = Field(..., description="Conversation ID")
    messages: List[Dict[str, Any]] = Field(..., description="Message history")
    total_messages: int = Field(..., description="Total message count")

# Global conversation memory
conversation_memory = ConversationMemory()

@chat_router.post("/send", response_model=ChatResponse)
async def send_message(
    message_data: ChatMessage,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(verify_token),
    agi_system = Depends(get_agi_system)
):
    """Send a message and get AI response"""
    try:
        start_time = datetime.utcnow()
        
        # Validate user access
        if message_data.user_id != current_user.get("user_id"):
            raise HTTPException(
                status_code=403,
                detail="Access denied: User ID mismatch"
            )
        
        # Generate conversation ID if not provided
        conversation_id = message_data.conversation_id or str(uuid.uuid4())
        
        # Store user message
        user_message = {
            "id": str(uuid.uuid4()),
            "role": "user",
            "content": message_data.message,
            "timestamp": start_time.isoformat(),
            "user_id": message_data.user_id
        }
        
        # Process with AGI system
        logger.info(f"Processing message for user {message_data.user_id}")
        
        if message_data.stream:
            # For streaming, we'll handle it in the stream endpoint
            return ChatResponse(
                response="Streaming response initiated",
                conversation_id=conversation_id,
                message_id=user_message["id"],
                timestamp=start_time,
                processing_time=0.0
            )
        else:
            # Process synchronously
            agi_response = await agi_system.process_message(
                message=message_data.message,
                user_id=message_data.user_id,
                conversation_id=conversation_id,
                context=message_data.context or {}
            )
            
            # Create AI response
            ai_message = {
                "id": str(uuid.uuid4()),
                "role": "assistant",
                "content": agi_response.get("response", ""),
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": message_data.user_id,
                "tokens_used": agi_response.get("tokens_used"),
                "processing_time": agi_response.get("processing_time", 0.0)
            }
            
            # Store messages in memory
            background_tasks.add_task(
                conversation_memory.store_message,
                conversation_id=conversation_id,
                message=user_message
            )
            background_tasks.add_task(
                conversation_memory.store_message,
                conversation_id=conversation_id,
                message=ai_message
            )
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return ChatResponse(
                response=ai_message["content"],
                conversation_id=conversation_id,
                message_id=ai_message["id"],
                timestamp=datetime.utcnow(),
                tokens_used=ai_message.get("tokens_used"),
                processing_time=processing_time
            )
            
    except TantraException as e:
        logger.error(f"TantraException in send_message: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Error in send_message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@chat_router.get("/stream")
async def stream_response(
    message: str,
    conversation_id: Optional[str] = None,
    user_id: str = None,
    current_user: dict = Depends(verify_token),
    agi_system = Depends(get_agi_system)
):
    """Stream AI response in real-time"""
    try:
        # Validate user access
        if user_id and user_id != current_user.get("user_id"):
            raise HTTPException(
                status_code=403,
                detail="Access denied: User ID mismatch"
            )
        
        user_id = user_id or current_user.get("user_id")
        conversation_id = conversation_id or str(uuid.uuid4())
        
        async def generate_stream():
            """Generate streaming response"""
            try:
                # Send initial metadata
                yield f"data: {json.dumps({'type': 'start', 'conversation_id': conversation_id})}\n\n"
                
                # Process with AGI system (streaming)
                async for chunk in agi_system.process_message_stream(
                    message=message,
                    user_id=user_id,
                    conversation_id=conversation_id
                ):
                    if chunk:
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                
                # Send completion signal
                yield f"data: {json.dumps({'type': 'end', 'conversation_id': conversation_id})}\n\n"
                
            except Exception as e:
                logger.error(f"Error in stream generation: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )
        
    except TantraException as e:
        logger.error(f"TantraException in stream_response: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Error in stream_response: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@chat_router.get("/conversations", response_model=List[ConversationInfo])
async def get_conversations(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    current_user: dict = Depends(verify_token)
):
    """Get user's conversation list"""
    try:
        # Validate user access
        if user_id != current_user.get("user_id"):
            raise HTTPException(
                status_code=403,
                detail="Access denied: User ID mismatch"
            )
        
        conversations = await conversation_memory.get_user_conversations(
            user_id=user_id,
            limit=limit,
            offset=offset
        )
        
        return [
            ConversationInfo(
                conversation_id=conv["conversation_id"],
                title=conv.get("title", "Untitled Conversation"),
                created_at=conv["created_at"],
                updated_at=conv["updated_at"],
                message_count=conv["message_count"],
                user_id=conv["user_id"]
            )
            for conv in conversations
        ]
        
    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@chat_router.get("/history/{conversation_id}", response_model=ConversationHistory)
async def get_conversation_history(
    conversation_id: str,
    user_id: str,
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(verify_token)
):
    """Get conversation history"""
    try:
        # Validate user access
        if user_id != current_user.get("user_id"):
            raise HTTPException(
                status_code=403,
                detail="Access denied: User ID mismatch"
            )
        
        # Verify conversation belongs to user
        conversation = await conversation_memory.get_conversation(conversation_id)
        if not conversation or conversation["user_id"] != user_id:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found"
            )
        
        # Get messages
        messages = await conversation_memory.get_conversation_messages(
            conversation_id=conversation_id,
            limit=limit,
            offset=offset
        )
        
        return ConversationHistory(
            conversation_id=conversation_id,
            messages=messages,
            total_messages=len(messages)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@chat_router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user_id: str,
    current_user: dict = Depends(verify_token)
):
    """Delete a conversation"""
    try:
        # Validate user access
        if user_id != current_user.get("user_id"):
            raise HTTPException(
                status_code=403,
                detail="Access denied: User ID mismatch"
            )
        
        # Verify conversation belongs to user
        conversation = await conversation_memory.get_conversation(conversation_id)
        if not conversation or conversation["user_id"] != user_id:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found"
            )
        
        # Delete conversation
        await conversation_memory.delete_conversation(conversation_id)
        
        return {"message": "Conversation deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@chat_router.post("/multimodal")
async def process_multimodal(
    message: str,
    files: List[bytes],
    conversation_id: Optional[str] = None,
    user_id: str = None,
    current_user: dict = Depends(verify_token),
    agi_system = Depends(get_agi_system)
):
    """Process multimodal input (text + files)"""
    try:
        # Validate user access
        if user_id and user_id != current_user.get("user_id"):
            raise HTTPException(
                status_code=403,
                detail="Access denied: User ID mismatch"
            )
        
        user_id = user_id or current_user.get("user_id")
        conversation_id = conversation_id or str(uuid.uuid4())
        
        # Process files and message
        result = await agi_system.process_multimodal(
            message=message,
            files=files,
            user_id=user_id,
            conversation_id=conversation_id
        )
        
        return {
            "response": result.get("response", ""),
            "conversation_id": conversation_id,
            "files_processed": result.get("files_processed", 0),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except TantraException as e:
        logger.error(f"TantraException in process_multimodal: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Error in process_multimodal: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")