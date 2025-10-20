"""
Atulya Tantra - Chat API Routes
Version: 2.5.0
FastAPI routes for chat functionality with streaming support
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, AsyncGenerator
from src.services.chat_service import ChatService
from src.services.multimodal_service import MultimodalService
from src.api.dependencies import get_chat_service, get_current_user, get_multimodal_service
import base64
import io
import json
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

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


class StreamChatRequest(BaseModel):
    """Streaming chat request model"""
    message: str
    conversation_id: Optional[str] = None
    stream: bool = True


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


@router.post("/stream")
async def stream_message(
    request: StreamChatRequest,
    chat_service: ChatService = Depends(get_chat_service)
):
    """Stream chat message with Server-Sent Events"""
    async def generate_stream():
        try:
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connection', 'status': 'connected'})}\n\n"
            
            # Generate streaming response
            async for chunk in chat_service.stream_message(
                message=request.message,
                conversation_id=request.conversation_id
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
            
            # Send completion message
            yield f"data: {json.dumps({'type': 'complete', 'status': 'done'})}\n\n"
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        }
    )


@router.websocket("/ws/{conversation_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: str,
    chat_service: ChatService = Depends(get_chat_service)
):
    """WebSocket endpoint for real-time chat"""
    await websocket.accept()
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Send typing indicator
            await websocket.send_text(json.dumps({
                "type": "typing",
                "status": "start"
            }))
            
            # Process message and stream response
            async for chunk in chat_service.stream_message(
                message=message_data["message"],
                conversation_id=conversation_id
            ):
                await websocket.send_text(json.dumps(chunk))
                
                # Allow other tasks to run
                await asyncio.sleep(0.01)
            
            # Send completion
            await websocket.send_text(json.dumps({
                "type": "complete",
                "status": "done"
            }))
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for conversation {conversation_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": str(e)
        }))


@router.post("/voice")
async def process_voice_input(
    audio_file: UploadFile = File(...),
    multimodal_service: MultimodalService = Depends(get_multimodal_service)
):
    """Process voice input and convert to text"""
    try:
        audio_data = await audio_file.read()
        text = await multimodal_service.process_voice_input(audio_data)
        return {"text": text, "filename": audio_file.filename}
    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vision")
async def process_vision_input(
    image_file: UploadFile = File(...),
    multimodal_service: MultimodalService = Depends(get_multimodal_service)
):
    """Process image input and extract information"""
    try:
        image_data = await image_file.read()
        analysis = await multimodal_service.process_image_input(image_data)
        return {"analysis": analysis, "filename": image_file.filename}
    except Exception as e:
        logger.error(f"Vision processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/multimodal")
async def process_multimodal_message(
    message: str = Form(...),
    conversation_id: Optional[str] = Form(None),
    attachments: List[UploadFile] = File([]),
    chat_service: ChatService = Depends(get_chat_service),
    multimodal_service: MultimodalService = Depends(get_multimodal_service)
):
    """Process message with multimodal attachments"""
    try:
        # Process attachments
        processed_attachments = []
        for attachment in attachments:
            file_data = await attachment.read()
            file_info = await multimodal_service.process_file_attachment(
                file_data, attachment.filename, attachment.content_type
            )
            processed_attachments.append(file_info)
        
        # Process message with attachments
        response = await chat_service.process_message(
            message=message,
            conversation_id=conversation_id,
            attachments=processed_attachments
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Multimodal processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tts")
async def text_to_speech(
    text: str = Form(...),
    voice: str = Form("en-US-AriaNeural"),
    multimodal_service: MultimodalService = Depends(get_multimodal_service)
):
    """Convert text to speech"""
    try:
        audio_data = await multimodal_service.generate_voice_output(text, voice)
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=speech.wav"}
        )
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
