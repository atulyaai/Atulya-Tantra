#!/usr/bin/env python3
"""
Atulya Tantra - Advanced AGI System
Production Server Entry Point

This is the main server file for the Atulya Tantra AGI system.
It provides a FastAPI-based web server with comprehensive AI capabilities.
"""

import asyncio
import logging
import os
import sys
import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse
    import uvicorn
    
    # AI Model Clients
    import ollama
    import openai
    import anthropic
    from openai import OpenAI
    from anthropic import Anthropic
    
except ImportError as e:
    print(f"❌ Missing required dependencies: {e}")
    print("📦 Please install requirements: pip install -r requirements.txt")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('data/logs/server.log', mode='a')
    ]
)

logger = logging.getLogger(__name__)

# Global conversation storage
conversations: Dict[str, List[Dict]] = {}

# Initialize AI clients
openai_client = None
anthropic_client = None
ollama_available = False
available_models = []

def initialize_ai_clients():
    """Initialize AI model clients with fallback handling."""
    global openai_client, anthropic_client, ollama_available, available_models
    
    print("🔧 Initializing AI clients...")
    
    # Initialize OpenAI client
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        try:
            openai_client = OpenAI(api_key=openai_api_key)
            logger.info("✅ OpenAI client initialized")
        except Exception as e:
            logger.warning(f"⚠️ OpenAI client failed to initialize: {e}")
    else:
        logger.warning("⚠️ OPENAI_API_KEY not found, OpenAI disabled")
    
    # Initialize Anthropic client
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_api_key:
        try:
            anthropic_client = Anthropic(api_key=anthropic_api_key)
            logger.info("✅ Anthropic client initialized")
        except Exception as e:
            logger.warning(f"⚠️ Anthropic client failed to initialize: {e}")
    else:
        logger.warning("⚠️ ANTHROPIC_API_KEY not found, Anthropic disabled")
    
    # Check Ollama availability and get available models
    available_models = []
    try:
        print("🔧 Checking Ollama...")
        models_response = ollama.list()
        available_models = [model.model for model in models_response.models]
        ollama_available = True
        print(f"✅ Ollama available with models: {available_models}")
        logger.info(f"✅ Ollama client available with models: {available_models}")
    except Exception as e:
        print(f"❌ Ollama failed: {e}")
        logger.warning(f"⚠️ Ollama not available: {e}")
        ollama_available = False

# Initialize AI clients
initialize_ai_clients()

# Create FastAPI app
app = FastAPI(
    title="Atulya Tantra AI Assistant",
    description="Advanced AI Assistant with multi-agent orchestration",
    version="1.5.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "version": "1.5.0",
        "service": "Atulya Tantra AGI System",
        "timestamp": asyncio.get_event_loop().time()
    }

# Root endpoint - redirect to WebUI
@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint - redirect to WebUI."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Atulya Tantra AGI System</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #2c3e50; text-align: center; }
            .status { background: #27ae60; color: white; padding: 10px; border-radius: 5px; text-align: center; margin: 20px 0; }
            .links { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 30px 0; }
            .link { background: #3498db; color: white; padding: 20px; text-decoration: none; border-radius: 5px; text-align: center; transition: background 0.3s; }
            .link:hover { background: #2980b9; }
            .info { background: #ecf0f1; padding: 20px; border-radius: 5px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Atulya Tantra AGI System</h1>
            <div class="status">✅ System Online - Version 1.5.0 (Foundation)</div>
            
            <div class="info">
                <h3>🚀 Quick Access</h3>
                <p>Welcome to Atulya Tantra, an advanced Artificial General Intelligence system with multi-agent orchestration, voice interaction, and desktop automation capabilities.</p>
            </div>
            
            <div class="links">
                <a href="/webui" class="link">💬 WebUI Interface</a>
                <a href="/admin" class="link">⚙️ Admin Panel</a>
                <a href="/docs" class="link">📚 API Documentation</a>
                <a href="/health" class="link">🏥 Health Check</a>
            </div>
            
            <div class="info">
                <h3>🔧 System Features</h3>
                <ul>
                    <li><strong>Multi-Agent AI:</strong> JARVIS conversational intelligence + SKYNET orchestration</li>
                    <li><strong>Voice Interface:</strong> Wake word detection, speech-to-text, text-to-speech</li>
                    <li><strong>Desktop Automation:</strong> Full desktop control and automation</li>
                    <li><strong>Security:</strong> 2FA, audit logging, encryption at rest</li>
                    <li><strong>Analytics:</strong> Real-time monitoring and performance optimization</li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """

# API endpoints placeholder
@app.get("/api/status")
async def api_status():
    """API status endpoint."""
    return {
        "api_version": "1.5.0",
        "status": "operational",
        "features": [
            "Multi-agent AI orchestration",
            "Voice interaction system",
            "Desktop automation",
            "Real-time analytics",
            "Advanced security"
        ]
    }

# Mount static files if they exist
if Path("webui/static").exists():
    app.mount("/static", StaticFiles(directory="webui/static"), name="static")

# Serve the main WebUI
@app.get("/webui", response_class=HTMLResponse)
async def webui():
    """Serve the main WebUI interface."""
    webui_path = Path("webui/index.html")
    if webui_path.exists():
        return webui_path.read_text(encoding="utf-8")
    else:
        return HTMLResponse("""
        <html>
        <head><title>WebUI Not Found</title></head>
        <body>
            <h1>WebUI Not Found</h1>
            <p>The WebUI files are missing. Please check the installation.</p>
            <a href="/">← Back to Home</a>
        </body>
        </html>
        """)

# Admin panel endpoint
@app.get("/admin", response_class=HTMLResponse)
async def admin_panel():
    """Serve the admin panel."""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Atulya Tantra - Admin Panel</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #2c3e50; text-align: center; }
            .status { background: #27ae60; color: white; padding: 10px; border-radius: 5px; text-align: center; margin: 20px 0; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 30px 0; }
            .card { background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #3498db; }
            .card h3 { margin-top: 0; color: #2c3e50; }
            .metric { font-size: 2rem; font-weight: bold; color: #3498db; }
            .btn { background: #3498db; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; margin: 5px; }
            .btn:hover { background: #2980b9; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>⚙️ Atulya Tantra - Admin Panel</h1>
            <div class="status">✅ System Online - Version 1.5.0 (Foundation)</div>
            
            <div class="grid">
                <div class="card">
                    <h3>📊 System Status</h3>
                    <div class="metric" id="uptime">Loading...</div>
                    <p>System Uptime</p>
                </div>
                <div class="card">
                    <h3>🧠 Core Modules</h3>
                    <div class="metric" id="modules">7/7</div>
                    <p>Active Modules</p>
                </div>
                <div class="card">
                    <h3>🤖 AI Models</h3>
                    <div class="metric" id="models">3</div>
                    <p>Available Models</p>
                </div>
                <div class="card">
                    <h3>👥 Active Users</h3>
                    <div class="metric" id="users">1</div>
                    <p>Current Sessions</p>
                </div>
            </div>
            
            <div class="grid">
                <div class="card">
                    <h3>🔧 System Controls</h3>
                    <a href="/api/status" class="btn">Check API Status</a>
                    <a href="/health" class="btn">Health Check</a>
                    <a href="/docs" class="btn">API Docs</a>
                </div>
                <div class="card">
                    <h3>📈 Monitoring</h3>
                    <a href="/api/metrics" class="btn">View Metrics</a>
                    <a href="/api/logs" class="btn">View Logs</a>
                    <button class="btn" onclick="refreshStatus()">Refresh Status</button>
                </div>
            </div>
            
            <div class="card">
                <h3>🚀 Quick Actions</h3>
                <a href="/webui" class="btn">Open WebUI</a>
                <a href="/" class="btn">Home Page</a>
                <a href="https://github.com/atulyaai/Atulya-Tantra" class="btn">GitHub</a>
            </div>
        </div>
        
        <script>
            function refreshStatus() {
                location.reload();
            }
            
            // Update uptime
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('uptime').textContent = 'Online';
                })
                .catch(error => {
                    document.getElementById('uptime').textContent = 'Error';
                });
        </script>
    </body>
    </html>
    """)

# Chat API endpoint
@app.post("/api/chat")
async def chat_endpoint(request: dict):
    """Handle chat requests with conversation context."""
    try:
        message = request.get("message", "")
        enable_voice = request.get("enable_voice", False)
        conversation_id = request.get("conversation_id", "default")
        
        if not message:
            raise HTTPException(status_code=400, detail="Message is required")
        
        # Generate conversation ID if not provided
        if conversation_id == "default":
            conversation_id = str(uuid.uuid4())
        
        # Get response from the AI system
        response_text = await generate_ai_response(message, conversation_id)
        
        # Get the model used from the last conversation entry
        model_used = "Unknown"
        if conversation_id in conversations and conversations[conversation_id]:
            last_message = conversations[conversation_id][-1]
            model_used = last_message.get("model", "Unknown")
        
        result = {
            "response": response_text,
            "conversation_id": conversation_id,
            "model": model_used,
            "timestamp": datetime.now().isoformat(),
            "conversation_length": len(conversations.get(conversation_id, []))
        }
        
        # Generate audio if requested
        if enable_voice:
            try:
                audio_file = await generate_audio_response(response_text)
                if audio_file:
                    result["audio_file"] = audio_file
            except Exception as e:
                logger.warning(f"Audio generation failed: {e}")
        
        return result
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Clear conversation endpoint
@app.post("/api/chat/clear")
async def clear_conversation(request: dict):
    """Clear a conversation."""
    try:
        conversation_id = request.get("conversation_id", "default")
        
        if conversation_id in conversations:
            del conversations[conversation_id]
            return {"status": "success", "message": f"Conversation {conversation_id} cleared"}
        else:
            return {"status": "success", "message": "Conversation not found"}
            
    except Exception as e:
        logger.error(f"Clear conversation error: {e}")
        return {"status": "error", "message": str(e)}

# Get conversation history endpoint
@app.get("/api/chat/history/{conversation_id}")
async def get_conversation_history(conversation_id: str):
    """Get conversation history."""
    try:
        if conversation_id in conversations:
            return {
                "status": "success",
                "conversation_id": conversation_id,
                "messages": conversations[conversation_id],
                "message_count": len(conversations[conversation_id])
            }
        else:
            return {"status": "error", "message": "Conversation not found"}
            
    except Exception as e:
        logger.error(f"Get history error: {e}")
        return {"status": "error", "message": str(e)}

# Get all conversations endpoint
@app.get("/api/chat/conversations")
async def get_all_conversations():
    """Get all active conversations."""
    try:
        conversation_list = []
        for conv_id, messages in conversations.items():
            conversation_list.append({
                "conversation_id": conv_id,
                "message_count": len(messages),
                "last_message": messages[-1] if messages else None,
                "created_at": messages[0]["timestamp"] if messages else None
            })
        
        return {
            "status": "success",
            "conversations": conversation_list,
            "total_conversations": len(conversations)
        }
        
    except Exception as e:
        logger.error(f"Get conversations error: {e}")
        return {"status": "error", "message": str(e)}

# Metrics endpoint
@app.get("/api/metrics")
async def get_metrics():
    """Get system metrics."""
    try:
        # Return basic system metrics
        return {
            "status": "success",
            "metrics": {
                "active_conversations": len(conversations),
                "total_messages": sum(len(conv) for conv in conversations.values()),
                "ollama_available": ollama_available,
                "openai_available": openai_client is not None,
                "anthropic_available": anthropic_client is not None,
                "uptime": "running",
                "version": "1.5.0"
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Metrics error: {e}")
        return {"status": "error", "message": str(e)}

# Logs endpoint
@app.get("/api/logs")
async def get_logs():
    """Get recent logs."""
    try:
        log_file = Path("data/logs/server.log")
        if log_file.exists():
            logs = log_file.read_text(encoding="utf-8").split('\n')[-50:]  # Last 50 lines
            return {
                "status": "success",
                "logs": logs,
                "timestamp": asyncio.get_event_loop().time()
            }
        else:
            return {"status": "success", "logs": [], "message": "No logs found"}
    except Exception as e:
        logger.error(f"Logs error: {e}")
        return {"status": "error", "message": str(e)}

# AI Response Generation
async def generate_ai_response(message: str, conversation_id: str = "default") -> str:
    """Generate AI response using real AI models with fallback system."""
    try:
        # Get or create conversation history
        if conversation_id not in conversations:
            conversations[conversation_id] = []
        
        # Add user message to conversation
        conversations[conversation_id].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        
        # Build context from conversation history (last 10 messages)
        context_messages = conversations[conversation_id][-10:]
        
        # Try models in order: Ollama -> OpenAI -> Anthropic
        response_text = None
        model_used = None
        
        # Try Ollama first (local, free)
        if ollama_available and not response_text:
            try:
                # Select best available model (prefer larger models for better responses)
                model_priority = ['mistral:latest', 'qwen2.5-coder:7b', 'gemma2:2b']
                selected_model = None
                
                for model in model_priority:
                    if model in available_models:
                        selected_model = model
                        break
                
                if not selected_model and available_models:
                    # Use first available model if none match priority
                    selected_model = available_models[0]
                
                if selected_model:
                    logger.info(f"🤖 Trying Ollama ({selected_model})...")
                    
                    # Convert conversation to Ollama format
                    ollama_messages = []
                    for msg in context_messages:
                        ollama_messages.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })
                    
                    response = ollama.chat(
                        model=selected_model,
                        messages=ollama_messages,
                        options={
                            'temperature': 0.7,
                            'top_p': 0.9,
                            'max_tokens': 1000
                        }
                    )
                    
                    response_text = response['message']['content']
                    model_used = f"Ollama ({selected_model})"
                    logger.info(f"✅ Ollama response generated using {selected_model}")
                else:
                    logger.warning("⚠️ No Ollama models available")
                
            except Exception as e:
                logger.warning(f"⚠️ Ollama failed: {e}")
        
        # Try OpenAI if Ollama failed
        if not response_text and openai_client:
            try:
                logger.info("🤖 Trying OpenAI (GPT-3.5)...")
                
                # Convert conversation to OpenAI format
                openai_messages = []
                for msg in context_messages:
                    openai_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
                
                response = openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=openai_messages,
                    max_tokens=1000,
                    temperature=0.7
                )
                
                response_text = response.choices[0].message.content
                model_used = "OpenAI (GPT-3.5)"
                logger.info("✅ OpenAI response generated")
                
            except Exception as e:
                logger.warning(f"⚠️ OpenAI failed: {e}")
        
        # Try Anthropic if others failed
        if not response_text and anthropic_client:
            try:
                logger.info("🤖 Trying Anthropic (Claude)...")
                
                # Convert conversation to Anthropic format
                anthropic_messages = []
                for msg in context_messages:
                    anthropic_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
                
                response = anthropic_client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=1000,
                    messages=anthropic_messages
                )
                
                response_text = response.content[0].text
                model_used = "Anthropic (Claude)"
                logger.info("✅ Anthropic response generated")
                
            except Exception as e:
                logger.warning(f"⚠️ Anthropic failed: {e}")
        
        # Fallback if all models failed
        if not response_text:
            logger.error("❌ All AI models failed, using fallback response")
            response_text = f"I'm sorry, I'm having trouble connecting to my AI models right now. You said: '{message}'. Please try again in a moment, or check if Ollama is running locally."
            model_used = "Fallback"
        
        # Add AI response to conversation
        conversations[conversation_id].append({
            "role": "assistant",
            "content": response_text,
            "model": model_used,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep conversation history manageable (last 20 messages)
        if len(conversations[conversation_id]) > 20:
            conversations[conversation_id] = conversations[conversation_id][-20:]
        
        logger.info(f"✅ AI response generated using {model_used}")
        return response_text
        
    except Exception as e:
        logger.error(f"AI response generation error: {e}")
        return f"I'm sorry, I encountered an error processing your message: '{message}'. Please try again."

# Audio Response Generation
async def generate_audio_response(text: str) -> str:
    """Generate audio response using TTS."""
    try:
        from core.voice import get_voice_engine
        
        voice_engine = get_voice_engine()
        # For now, return a placeholder - in production, generate actual audio
        return None  # Disabled for now to avoid audio issues
        
    except Exception as e:
        logger.warning(f"Audio generation error: {e}")
        return None

def main():
    """Main server entry point."""
    print("🚀 Starting Atulya Tantra AI Assistant v1.5.0 (Foundation)")
    print("=" * 50)
    
    # Ensure data directories exist
    data_dirs = ["data/logs", "data/uploads", "data/cache", "data/security", "data/analytics"]
    for dir_path in data_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    # Get configuration from environment
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    print(f"🌐 Server starting on http://{host}:{port}")
    print(f"📚 API Documentation: http://{host}:{port}/docs")
    print(f"⚙️ Admin Panel: http://{host}:{port}/admin")
    print(f"🏥 Health Check: http://{host}:{port}/health")
    print("=" * 50)
    
    try:
        uvicorn.run(
            "server:app",
            host=host,
            port=port,
            reload=debug,
            log_level="info" if not debug else "debug",
            access_log=True
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        print(f"❌ Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
