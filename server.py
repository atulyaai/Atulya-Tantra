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
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse
    import uvicorn
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

# Create FastAPI app
app = FastAPI(
    title="Atulya Tantra AGI System",
    description="Advanced Artificial General Intelligence with multi-agent orchestration",
    version="2.0.1",
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
        "version": "2.0.1",
        "service": "Atulya Tantra AGI System",
        "timestamp": asyncio.get_event_loop().time()
    }

# Root endpoint
@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with system information."""
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
            <div class="status">✅ System Online - Version 2.0.1</div>
            
            <div class="info">
                <h3>🚀 Quick Access</h3>
                <p>Welcome to Atulya Tantra, an advanced Artificial General Intelligence system with multi-agent orchestration, voice interaction, and desktop automation capabilities.</p>
            </div>
            
            <div class="links">
                <a href="/docs" class="link">📚 API Documentation</a>
                <a href="/admin" class="link">⚙️ Admin Panel</a>
                <a href="/health" class="link">🏥 Health Check</a>
                <a href="https://github.com/atulyaai/Atulya-Tantra" class="link">🐙 GitHub</a>
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
        "api_version": "2.0.1",
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

def main():
    """Main server entry point."""
    print("🚀 Starting Atulya Tantra AGI System v2.0.1")
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
