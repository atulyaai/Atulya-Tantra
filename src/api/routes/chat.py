"""
Atulya Tantra - Chat API Routes
Version: 2.5.0
FastAPI routes for chat functionality
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from src.services.chat_service import ChatService
from src.api.dependencies import get_chat_service, get_current_user
import base64
import io

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
    request: Optional[ChatRequest] = None,
    message: Optional[str] = Form(None),
    conversation_id: Optional[str] = Form(None),
    model: str = Form("ollama"),
    attachments: List[UploadFile] = File([]),
    chat_service: ChatService = Depends(get_chat_service)
):
    """Send chat message with optional attachments and get AI response"""
    try:
        # Handle both JSON and form data
        if request:
            # JSON request
            message_text = request.message
            conv_id = request.conversation_id
            model_name = "ollama"  # Default for JSON requests
        else:
            # Form data request
            message_text = message
            conv_id = conversation_id
            model_name = model
        
        if not message_text:
            raise HTTPException(status_code=400, detail="Message is required")
        
        # Process attachments
        attachment_data = []
        for attachment in attachments:
            content = await attachment.read()
            attachment_data.append({
                "filename": attachment.filename,
                "content_type": attachment.content_type,
                "size": len(content),
                "data": base64.b64encode(content).decode('utf-8')
            })
        
        response = await chat_service.process_message(
            message=message_text,
            conversation_id=conv_id,
            model=model_name,
            attachments=attachment_data
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
    chat_service: ChatService = Depends(get_chat_service),
    current_user: Dict = Depends(get_current_user)
):
    """List all conversations"""
    try:
        # Get conversation stats from chat service
        stats = await chat_service.get_conversation_stats()
        
        # For now, return basic stats
        # In a real implementation, this would fetch from database
        conversations = []
        return {"conversations": conversations, "total": stats.get("total_conversations", 0)}
    except Exception as e:
        logger.error(f"Conversations endpoint error: {e}")
        return {"conversations": [], "total": 0}


@router.post("/simple", response_model=ChatResponse)
async def send_message_simple(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service)
):
    """Simple chat endpoint for testing"""
    try:
        response = await chat_service.process_message(
            message=request.message,
            conversation_id=None,
            user_id="test-user",
            model="ollama"
        )
        return response
    except Exception as e:
        logger.error(f"Simple chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
