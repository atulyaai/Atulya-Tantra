#!/usr/bin/env python3
"""
Atulya Tantra - Main Server
FastAPI server integrating JARVIS & SKYNET protocols
"""

import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uvicorn
from pathlib import Path

from core import get_config, get_logger
from configuration import JarvisInterface, SkynetOrchestrator

# Initialize
config = get_config()
logger = get_logger('server')

# Create FastAPI app
app = FastAPI(
    title="Atulya Tantra API",
    description="AI Assistant with JARVIS & SKYNET protocols",
    version=config.version
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for webui and audio
app.mount("/webui", StaticFiles(directory="webui"), name="webui")
app.mount("/data", StaticFiles(directory="data"), name="data")

# Initialize protocols
jarvis: Optional[JarvisInterface] = None
skynet: Optional[SkynetOrchestrator] = None


# ============================================================================
# REQUEST MODELS
# ============================================================================

class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None
    enable_voice: bool = False


class TaskRequest(BaseModel):
    task: str
    context: Optional[Dict[str, Any]] = None


# ============================================================================
# STARTUP/SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup():
    """Initialize protocols on startup"""
    global jarvis, skynet
    
    logger.info("=" * 70)
    logger.info(f"🤖 Atulya Tantra Server Starting (v{config.version})")
    logger.info("=" * 70)
    
    # Initialize JARVIS
    jarvis = JarvisInterface()
    await jarvis.activate()
    logger.info("✅ JARVIS Protocol activated")
    
    # Initialize SKYNET
    skynet = SkynetOrchestrator()
    await skynet.activate()
    logger.info("✅ SKYNET Protocol activated")
    
    logger.info("=" * 70)
    logger.info("🚀 Server ready!")
    logger.info("=" * 70)


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    global jarvis, skynet
    
    logger.info("Shutting down...")
    
    if jarvis:
        await jarvis.deactivate()
        logger.info("✅ JARVIS Protocol deactivated")
    
    if skynet:
        await skynet.deactivate()
        logger.info("✅ SKYNET Protocol deactivated")
    
    logger.info("Goodbye!")


# ============================================================================
# ROUTES
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint - health check"""
    return {
        "name": "Atulya Tantra",
        "version": config.version,
        "codename": config.codename,
        "status": "operational",
        "protocols": {
            "jarvis": jarvis.is_active if jarvis else False,
            "skynet": skynet.is_active if skynet else False
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "jarvis": "active" if (jarvis and jarvis.is_active) else "inactive",
        "skynet": "active" if (skynet and skynet.is_active) else "inactive"
    }


@app.get("/status")
async def status():
    """Detailed status endpoint"""
    return {
        "server": {
            "version": config.version,
            "codename": config.codename,
            "model": config.default_model
        },
        "jarvis": jarvis.get_status() if jarvis else {"status": "not initialized"},
        "skynet": skynet.get_status() if skynet else {"status": "not initialized"}
    }


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Chat with JARVIS Protocol
    
    Sends message to JARVIS for natural conversation with emotional intelligence
    """
    if not jarvis:
        raise HTTPException(status_code=503, detail="JARVIS not initialized")
    
    try:
        # Add voice enablement to context
        ctx = request.context or {}
        ctx['enable_voice'] = request.enable_voice
        
        result = await jarvis.process_message(
            message=request.message,
            context=ctx
        )
        return result
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/task")
async def execute_task(request: TaskRequest):
    """
    Execute task with SKYNET Protocol
    
    Routes task to appropriate specialized agent
    """
    if not skynet:
        raise HTTPException(status_code=503, detail="SKYNET not initialized")
    
    try:
        result = await skynet.route_task(
            task=request.task,
            context=request.context
        )
        return result
    except Exception as e:
        logger.error(f"Task error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/models")
async def list_models():
    """List available AI models"""
    return {
        "default": config.default_model,
        "supported": [
            "phi3:mini",
            "gemma:2b",
            "mistral",
            "codellama:7b"
        ]
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication"""
    await websocket.accept()
    logger.info("WebSocket connection established")
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            
            message_type = data.get("type", "chat")
            content = data.get("content", "")
            
            # Process based on type
            if message_type == "chat":
                result = await jarvis.process_message(content)
                await websocket.send_json({
                    "type": "response",
                    "data": result
                })
            
            elif message_type == "task":
                result = await skynet.route_task(content)
                await websocket.send_json({
                    "type": "task_result",
                    "data": result
                })
            
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })
    
    except WebSocketDisconnect:
        logger.info("WebSocket connection closed")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Start the server"""
    print("=" * 70)
    print(f"🤖 Atulya Tantra Server v{config.version}")
    print("=" * 70)
    print()
    print("Starting server...")
    print(f"📍 URL: http://localhost:8000")
    print(f"📚 Docs: http://localhost:8000/docs")
    print(f"🔧 Model: {config.default_model}")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 70)
    print()
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )


if __name__ == "__main__":
    main()

