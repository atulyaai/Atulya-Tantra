"""
Atulya Tantra Server - Main FastAPI Entry Point
Server-client architecture for multi-device access
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import asyncio
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Atulya Tantra Server",
    description="AI Server with multi-model support and real-time communication",
    version="1.0.0"
)

# CORS middleware for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models for request/response
class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = "phi3:mini"
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    model: str
    response_time: float
    conversation_id: str

class HealthResponse(BaseModel):
    status: str
    services: Dict[str, str]
    models_available: List[str]
    timestamp: str

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_json({"message": message})

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_json({"message": message})

manager = ConnectionManager()

# Health check endpoint
@app.get("/", response_model=HealthResponse)
async def root():
    """Health check and server info"""
    try:
        # Check available services (will implement actual checks)
        services = {
            "ai_service": "online",
            "memory_service": "online",
            "voice_service": "online",
        }
        
        models = ["phi3:mini"]  # Will check Ollama dynamically
        
        return HealthResponse(
            status="healthy",
            services=services,
            models_available=models,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Chat endpoint
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Main chat endpoint - uses agent orchestration"""
    try:
        start_time = asyncio.get_event_loop().time()
        
        # Import services
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from services.agent_orchestrator import orchestrator
        
        # Use agent orchestrator for intelligent routing
        result = await orchestrator.process(request.message)
        
        response_time = asyncio.get_event_loop().time() - start_time
        
        return ChatResponse(
            response=result['response'],
            model=result['model'],
            response_time=response_time,
            conversation_id=request.conversation_id or "default"
        )
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket endpoint for real-time communication
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time voice/text communication"""
    await manager.connect(websocket)
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message = data.get("message", "")
            model = data.get("model", "phi3:mini")
            
            if not message:
                continue
            
            # Process with AI
            import sys
            import os
            sys.path.insert(0, os.path.dirname(__file__))
            from services.ai_service import get_ai_response
            response = await get_ai_response(message, model)
            
            # Send response back
            await manager.send_personal_message(response, websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# Model listing endpoint
@app.get("/api/models")
async def list_models():
    """List available AI models"""
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from models.model_router import ModelRouter
        router = ModelRouter()
        return {
            "models": router.list_models(),
            "default": "phi3:mini"
        }
    except Exception as e:
        logger.error(f"List models error: {e}")
        return {"models": ["phi3:mini"], "default": "phi3:mini"}

# Memory endpoints
@app.post("/api/memory/save")
async def save_memory(data: dict):
    """Save conversation to memory"""
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from services.memory_service import save_conversation
        result = await save_conversation(data)
        return {"status": "saved", "id": result}
    except Exception as e:
        logger.error(f"Save memory error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/memory/{conversation_id}")
async def get_memory(conversation_id: str):
    """Retrieve conversation memory"""
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from services.memory_service import get_conversation
        memory = await get_conversation(conversation_id)
        return memory
    except Exception as e:
        logger.error(f"Get memory error: {e}")
        raise HTTPException(status_code=404, detail="Conversation not found")

@app.post("/api/task/execute")
async def execute_task(data: dict):
    """Execute a system task"""
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from services.task_service import task_service
        
        task_type = data.get("task_type")
        params = data.get("params", {})
        
        result = await task_service.execute_task(task_type, params)
        return result
    except Exception as e:
        logger.error(f"Task execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/voice/tts")
async def text_to_speech(data: dict):
    """Convert text to speech"""
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from services.voice_service import voice_service
        
        text = data.get("text", "")
        audio_data = await voice_service.text_to_speech(text)
        
        # Return audio as base64
        import base64
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        return {
            "audio": audio_base64,
            "format": "mp3"
        }
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/agents")
async def list_agents():
    """List available agents"""
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from services.agent_orchestrator import orchestrator
        
        agents = [
            {'name': name, 'model': agent.model}
            for name, agent in orchestrator.agents.items()
        ]
        return {'agents': agents}
    except Exception as e:
        logger.error(f"List agents error: {e}")
        return {'agents': []}

@app.get("/api/mcp/tools")
async def list_mcp_tools():
    """List available MCP tools"""
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from services.agent_orchestrator import mcp_server
        
        tools = mcp_server.list_tools()
        return {'tools': tools}
    except Exception as e:
        logger.error(f"List tools error: {e}")
        return {'tools': []}

@app.post("/api/mcp/execute")
async def execute_mcp_tool(data: dict):
    """Execute an MCP tool"""
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from services.agent_orchestrator import mcp_server
        
        tool_name = data.get('tool_name')
        params = data.get('params', {})
        
        result = await mcp_server.execute_tool(tool_name, params)
        return result
    except Exception as e:
        logger.error(f"MCP execute error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Atulya Tantra Server...")
    print("=" * 50)
    print("📡 Server: http://localhost:8000")
    print("📡 WebSocket: ws://localhost:8000/ws")
    print("📚 API Docs: http://localhost:8000/docs")
    print("🌐 Web Client: Open clients/web/index.html")
    print("=" * 50)
    print()
    print("✅ Services:")
    print("   • Agent Orchestrator (Multi-agent system)")
    print("   • MCP Server (Tool integration)")
    print("   • AI Service (Multi-model routing)")
    print("   • Memory Service (Conversation storage)")
    print("   • Voice Service (TTS/STT)")
    print("   • Task Service (System automation)")
    print()
    print("Press Ctrl+C to stop server")
    print("=" * 50)
    print()
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

