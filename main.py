"""
Atulya Tantra - Main Application
Version: 2.5.0
FastAPI application factory with clean architecture
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
import uvicorn
import logging

from src.config.settings import get_settings
from src.api.routes import chat, admin, auth
from src.infrastructure.database.models import init_database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Application factory"""
    settings = get_settings()
    
    # Initialize database
    try:
        init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Level 5 Autonomous AGI System",
        docs_url="/api/docs",
        redoc_url="/api/redoc"
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )
    
    # Include routers
    app.include_router(chat.router)
    app.include_router(admin.router)
    app.include_router(auth.router)
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "version": settings.app_version,
            "service": settings.app_name,
            "environment": settings.environment
        }
    
    # Root endpoint - serve WebUI
    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Root endpoint - serve WebUI"""
        webui_path = Path("webui/index.html")
        if webui_path.exists():
            return webui_path.read_text(encoding="utf-8")
        else:
            return HTMLResponse("""
            <html>
            <head><title>Atulya Tantra</title></head>
            <body>
                <h1>Atulya Tantra v2.5.0</h1>
                <p>Level 5 Autonomous AGI System</p>
                <p><a href="/api/docs">API Documentation</a></p>
                <p><a href="/health">Health Check</a></p>
            </body>
            </html>
            """)
    
    # WebUI endpoint
    @app.get("/webui", response_class=HTMLResponse)
    async def webui():
        """WebUI endpoint"""
        webui_path = Path("webui/index.html")
        if webui_path.exists():
            return webui_path.read_text(encoding="utf-8")
        else:
            return HTMLResponse("WebUI not found")
    
    # Mount static files if they exist
    static_path = Path("webui/static")
    if static_path.exists():
        app.mount("/static", StaticFiles(directory="webui/static"), name="static")
    
    logger.info(f"Created FastAPI app: {settings.app_name} v{settings.app_version}")
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    settings = get_settings()
    
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    
    uvicorn.run(
        "main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.server_reload and settings.environment == "development",
        log_level="debug" if settings.debug else "info"
    )
