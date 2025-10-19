"""
Atulya Tantra - Chat API Routes
Version: 2.5.0
FastAPI routes for chat functionality
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from src.services.chat_service import ChatService
from src.api.dependencies import get_chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Chat request model"""
    message: str
    conversation_id: Optional[str] = None
    enable_voice: bool = False


class ChatResponse(BaseModel):
    """Chat response model"""
    response: str
    conversation_id: str
    metadata: Dict
    timestamp: str


class ConversationHistory(BaseModel):
    """Conversation history model"""
    messages: List[Dict]
    conversation_id: str


@router.post("/", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service)
):
    """Send chat message and get AI response"""
    try:
        response = await chat_service.process_message(
            message=request.message,
            conversation_id=request.conversation_id
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{conversation_id}", response_model=ConversationHistory)
async def get_history(
    conversation_id: str,
    chat_service: ChatService = Depends(get_chat_service)
):
    """Get conversation history"""
    try:
        messages = await chat_service.get_history(conversation_id)
        return ConversationHistory(
            messages=messages,
            conversation_id=conversation_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    chat_service: ChatService = Depends(get_chat_service)
):
    """Delete conversation"""
    try:
        await chat_service.delete_conversation(conversation_id)
        return {"status": "success", "message": f"Conversation {conversation_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations")
async def list_conversations(
    chat_service: ChatService = Depends(get_chat_service)
):
    """List all conversations"""
    try:
        conversations = []
        for conv_id, messages in chat_service.conversations.items():
            conversations.append({
                "conversation_id": conv_id,
                "message_count": len(messages),
                "last_message": messages[-1].content if messages else None,
                "created_at": messages[0].timestamp.isoformat() if messages else None
            })
        return {"conversations": conversations, "total": len(conversations)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
