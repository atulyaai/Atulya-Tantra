# Atulya Tantra - Main Application Entry Point
# Simplified structure - All core functionality in one place

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import asyncio
from contextlib import asynccontextmanager

# Import consolidated modules
from .database import DatabaseManager
from .agents import AgentManager
from .ai import AIManager
from .auth import AuthManager
from .routes import router
from .security import SecurityManager

# Initialize managers
db_manager = DatabaseManager()
agent_manager = AgentManager()
ai_manager = AIManager()
auth_manager = AuthManager()
security_manager = SecurityManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    await db_manager.initialize()
    await agent_manager.initialize()
    await ai_manager.initialize()
    await auth_manager.initialize()
    await security_manager.initialize()
    
    yield
    
    # Shutdown
    await db_manager.close()
    await agent_manager.close()
    await ai_manager.close()
    await auth_manager.close()
    await security_manager.close()

# Create FastAPI app
app = FastAPI(
    title="Atulya Tantra",
    description="Level 5 AGI System",
    version="3.2.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add security middleware
app.add_middleware(security_manager.rate_limiter)

# Include routes
app.include_router(router)

# Mount static files
app.mount("/webui", StaticFiles(directory="../webui"), name="webui")
app.mount("/admin", StaticFiles(directory="../webui/admin"), name="admin")
app.mount("/admin-react", StaticFiles(directory="../webui/admin-react/dist"), name="admin-react")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Atulya Tantra",
        "version": "3.2.0",
        "description": "Level 5 AGI System - Simplified Structure",
        "status": "operational",
        "environment": os.getenv("APP_ENV", "development")
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": await db_manager.health_check(),
        "agents": await agent_manager.health_check(),
        "ai": await ai_manager.health_check()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
