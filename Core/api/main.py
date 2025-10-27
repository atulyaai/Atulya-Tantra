"""
Atulya Tantra AGI - FastAPI Main Application
Production-ready REST API with comprehensive endpoints
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
import uvicorn

from .auth import auth_router
from .chat import chat_router
from .agents import agents_router
from .memory import memory_router
from .system import system_router
from .admin import admin_router
from .streaming import streaming_router
from ..config.settings import settings
from ..config.logging import get_logger
from ..config.exceptions import TantraException
from ..middleware.rate_limiter import RateLimiterMiddleware
from ..middleware.security_headers import SecurityHeadersMiddleware
from ..middleware.request_logger import RequestLoggerMiddleware
from ..unified_agi_system import get_agi_system, SystemMode

logger = get_logger(__name__)

# Global AGI system instance
agi_system = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global agi_system
    
    # Startup
    logger.info("🚀 Starting Atulya Tantra AGI API Server...")
    
    try:
        # Initialize AGI system
        agi_system = get_agi_system()
        await agi_system.initialize()
        await agi_system.start(SystemMode.CONVERSATIONAL)
        
        logger.info("✅ AGI System initialized successfully")
        logger.info(f"🌐 API Server running on {settings.API_HOST}:{settings.API_PORT}")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize AGI system: {e}")
        raise
    finally:
        # Shutdown
        logger.info("🛑 Shutting down AGI system...")
        if agi_system:
            await agi_system.stop()
        logger.info("✅ Shutdown complete")

def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title="Atulya Tantra AGI API",
        description="Advanced AGI system with JARVIS personality and Skynet capabilities",
        version="3.0.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan
    )
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS
    )
    
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggerMiddleware)
    app.add_middleware(RateLimiterMiddleware)
    
    # Mount static files
    app.mount("/static", StaticFiles(directory="Webui/static"), name="static")
    
    # Include routers
    app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
    app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])
    app.include_router(agents_router, prefix="/api/agents", tags=["Agents"])
    app.include_router(memory_router, prefix="/api/memory", tags=["Memory"])
    app.include_router(system_router, prefix="/api/system", tags=["System"])
    app.include_router(admin_router, prefix="/api/admin", tags=["Admin"])
    app.include_router(streaming_router, prefix="/api/stream", tags=["Streaming"])
    
    # Root endpoint
    @app.get("/", response_class=JSONResponse)
    async def root():
        """Root endpoint with system information"""
        return {
            "name": "Atulya Tantra AGI",
            "version": "3.0.0",
            "status": "operational",
            "timestamp": datetime.utcnow().isoformat(),
            "docs": "/docs" if settings.DEBUG else "Documentation disabled in production"
        }
    
    # Health check endpoint
    @app.get("/health", response_class=JSONResponse)
    async def health_check():
        """Health check endpoint"""
        global agi_system
        
        try:
            if agi_system and agi_system.is_active:
                return {
                    "status": "healthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "agi_system": "active",
                    "version": "3.0.0"
                }
            else:
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "unhealthy",
                        "timestamp": datetime.utcnow().isoformat(),
                        "agi_system": "inactive",
                        "version": "3.0.0"
                    }
                )
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e)
                }
            )
    
    # Global exception handler
    @app.exception_handler(TantraException)
    async def tantra_exception_handler(request: Request, exc: TantraException):
        """Handle custom Tantra exceptions"""
        logger.error(f"TantraException: {exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_type,
                "message": exc.message,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions"""
        logger.error(f"Unexpected error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    return app

def get_agi_system_dependency():
    """Dependency to get AGI system instance"""
    global agi_system
    if not agi_system:
        raise HTTPException(
            status_code=503,
            detail="AGI system not initialized"
        )
    return agi_system

# Create the application
app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "Core.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning"
    )