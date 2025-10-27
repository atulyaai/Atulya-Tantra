"""
Streaming API endpoints for real-time communication
Handles Server-Sent Events (SSE) and WebSocket connections
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, AsyncGenerator
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config.logging import get_logger
from ..config.exceptions import TantraException
from ..auth.jwt import verify_token
from ..unified_agi_system import get_agi_system

logger = get_logger(__name__)
streaming_router = APIRouter()

# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, List[str]] = {}
    
    async def connect(self, websocket: WebSocket, connection_id: str, user_id: str):
        """Accept a WebSocket connection"""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(connection_id)
        
        logger.info(f"WebSocket connected: {connection_id} for user {user_id}")
    
    def disconnect(self, connection_id: str, user_id: str):
        """Remove a WebSocket connection"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        
        if user_id in self.user_connections:
            if connection_id in self.user_connections[user_id]:
                self.user_connections[user_id].remove(connection_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        logger.info(f"WebSocket disconnected: {connection_id}")
    
    async def send_personal_message(self, message: str, connection_id: str):
        """Send message to specific connection"""
        if connection_id in self.active_connections:
            try:
                await self.active_connections[connection_id].send_text(message)
            except Exception as e:
                logger.error(f"Error sending message to {connection_id}: {e}")
    
    async def send_to_user(self, message: str, user_id: str):
        """Send message to all connections for a user"""
        if user_id in self.user_connections:
            for connection_id in self.user_connections[user_id]:
                await self.send_personal_message(message, connection_id)
    
    async def broadcast(self, message: str):
        """Broadcast message to all connections"""
        for connection_id in self.active_connections:
            await self.send_personal_message(message, connection_id)

# Global connection manager
manager = ConnectionManager()

# Pydantic models
class StreamMessage(BaseModel):
    type: str = "message"
    content: str = ""
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    timestamp: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class StreamRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    user_id: str
    stream_type: str = "chat"  # chat, agent, system

@streaming_router.get("/events")
async def stream_events(
    user_id: str,
    conversation_id: Optional[str] = None,
    current_user: dict = Depends(verify_token),
    agi_system = Depends(get_agi_system)
):
    """Server-Sent Events endpoint for real-time streaming"""
    try:
        # Validate user access
        if user_id != current_user.get("user_id"):
            raise HTTPException(
                status_code=403,
                detail="Access denied: User ID mismatch"
            )
        
        async def event_generator():
            """Generate SSE events"""
            try:
                # Send connection established event
                yield f"data: {json.dumps({'type': 'connected', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
                
                # Keep connection alive with heartbeat
                while True:
                    yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
                    await asyncio.sleep(30)  # Heartbeat every 30 seconds
                    
            except asyncio.CancelledError:
                logger.info(f"SSE connection cancelled for user {user_id}")
            except Exception as e:
                logger.error(f"Error in SSE generator: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )
        
    except TantraException as e:
        logger.error(f"TantraException in stream_events: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Error in stream_events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@streaming_router.post("/chat/stream")
async def stream_chat_response(
    request: StreamRequest,
    current_user: dict = Depends(verify_token),
    agi_system = Depends(get_agi_system)
):
    """Stream chat response in real-time"""
    try:
        # Validate user access
        if request.user_id != current_user.get("user_id"):
            raise HTTPException(
                status_code=403,
                detail="Access denied: User ID mismatch"
            )
        
        conversation_id = request.conversation_id or str(uuid.uuid4())
        
        async def chat_stream_generator():
            """Generate streaming chat response"""
            try:
                # Send start event
                yield f"data: {json.dumps({'type': 'start', 'conversation_id': conversation_id, 'timestamp': datetime.utcnow().isoformat()})}\n\n"
                
                # Process message with AGI system
                async for chunk in agi_system.process_message_stream(
                    message=request.message,
                    user_id=request.user_id,
                    conversation_id=conversation_id
                ):
                    if chunk:
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk, 'timestamp': datetime.utcnow().isoformat()})}\n\n"
                
                # Send completion event
                yield f"data: {json.dumps({'type': 'complete', 'conversation_id': conversation_id, 'timestamp': datetime.utcnow().isoformat()})}\n\n"
                
            except Exception as e:
                logger.error(f"Error in chat stream: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'timestamp': datetime.utcnow().isoformat()})}\n\n"
        
        return StreamingResponse(
            chat_stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )
        
    except TantraException as e:
        logger.error(f"TantraException in stream_chat_response: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Error in stream_chat_response: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@streaming_router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    conversation_id: Optional[str] = None
):
    """WebSocket endpoint for bidirectional communication"""
    connection_id = str(uuid.uuid4())
    
    try:
        await manager.connect(websocket, connection_id, user_id)
        
        # Send welcome message
        welcome_message = {
            "type": "connected",
            "connection_id": connection_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        await websocket.send_text(json.dumps(welcome_message))
        
        # Listen for messages
        while True:
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Process different message types
                if message_data.get("type") == "ping":
                    # Respond to ping with pong
                    pong_message = {
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    await websocket.send_text(json.dumps(pong_message))
                
                elif message_data.get("type") == "chat":
                    # Process chat message
                    await process_websocket_chat(
                        websocket=websocket,
                        message_data=message_data,
                        user_id=user_id,
                        connection_id=connection_id
                    )
                
                elif message_data.get("type") == "agent_request":
                    # Process agent request
                    await process_websocket_agent_request(
                        websocket=websocket,
                        message_data=message_data,
                        user_id=user_id,
                        connection_id=connection_id
                    )
                
                else:
                    # Unknown message type
                    error_message = {
                        "type": "error",
                        "error": f"Unknown message type: {message_data.get('type')}",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    await websocket.send_text(json.dumps(error_message))
                    
            except json.JSONDecodeError:
                error_message = {
                    "type": "error",
                    "error": "Invalid JSON format",
                    "timestamp": datetime.utcnow().isoformat()
                }
                await websocket.send_text(json.dumps(error_message))
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(connection_id, user_id)

async def process_websocket_chat(
    websocket: WebSocket,
    message_data: Dict[str, Any],
    user_id: str,
    connection_id: str
):
    """Process chat message via WebSocket"""
    try:
        message = message_data.get("message", "")
        conversation_id = message_data.get("conversation_id")
        
        if not message:
            error_message = {
                "type": "error",
                "error": "Empty message",
                "timestamp": datetime.utcnow().isoformat()
            }
            await websocket.send_text(json.dumps(error_message))
            return
        
        # Get AGI system
        agi_system = get_agi_system()
        
        # Send processing start
        start_message = {
            "type": "processing_start",
            "conversation_id": conversation_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        await websocket.send_text(json.dumps(start_message))
        
        # Process message
        response = await agi_system.process_message(
            message=message,
            user_id=user_id,
            conversation_id=conversation_id
        )
        
        # Send response
        response_message = {
            "type": "chat_response",
            "content": response.get("response", ""),
            "conversation_id": conversation_id,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "tokens_used": response.get("tokens_used"),
                "processing_time": response.get("processing_time")
            }
        }
        await websocket.send_text(json.dumps(response_message))
        
    except Exception as e:
        logger.error(f"Error processing websocket chat: {e}")
        error_message = {
            "type": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
        await websocket.send_text(json.dumps(error_message))

async def process_websocket_agent_request(
    websocket: WebSocket,
    message_data: Dict[str, Any],
    user_id: str,
    connection_id: str
):
    """Process agent request via WebSocket"""
    try:
        agent_type = message_data.get("agent_type", "general")
        task = message_data.get("task", "")
        
        if not task:
            error_message = {
                "type": "error",
                "error": "Empty task",
                "timestamp": datetime.utcnow().isoformat()
            }
            await websocket.send_text(json.dumps(error_message))
            return
        
        # Get AGI system
        agi_system = get_agi_system()
        
        # Send processing start
        start_message = {
            "type": "agent_processing_start",
            "agent_type": agent_type,
            "timestamp": datetime.utcnow().isoformat()
        }
        await websocket.send_text(json.dumps(start_message))
        
        # Process with agent
        result = await agi_system.execute_agent_task(
            agent_type=agent_type,
            task=task,
            user_id=user_id
        )
        
        # Send result
        result_message = {
            "type": "agent_response",
            "agent_type": agent_type,
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        }
        await websocket.send_text(json.dumps(result_message))
        
    except Exception as e:
        logger.error(f"Error processing websocket agent request: {e}")
        error_message = {
            "type": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
        await websocket.send_text(json.dumps(error_message))

@streaming_router.get("/status")
async def get_streaming_status():
    """Get streaming service status"""
    return {
        "status": "active",
        "active_connections": len(manager.active_connections),
        "users_connected": len(manager.user_connections),
        "timestamp": datetime.utcnow().isoformat()
    }