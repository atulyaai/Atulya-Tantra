"""
Atulya Tantra - Main Application Entry Point
Version: 2.5.0
Level 5 AGI System with JARVIS Intelligence, Skynet Operations, and Specialized Agents
"""

import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os

# Prometheus metrics
from prometheus_client import CollectorRegistry, CONTENT_TYPE_LATEST, generate_latest, Counter, Histogram
import time

# Import API routes
from src.api.routes import chat, admin, health, auth
from src.api.dependencies import get_chat_service, get_ai_service, get_multimodal_service

# Import core components
from src.core.agents.agent_coordinator import AgentCoordinator
from src.core.agents.skynet.monitor import SystemMonitor
from src.core.agents.skynet.decision_engine import DecisionEngine
from src.core.agents.skynet.executor import task_executor
from src.core.agents.skynet.coordinator import MultiAgentCoordinator
from src.core.agents.skynet.safety import safety_system
from src.core.agents.jarvis.voice import JARVISVoiceInterface
from src.core.security.rate_limiter import get_rate_limiter

# Import integrations
from src.integrations.calendar import CalendarIntegration
from src.integrations.email import EmailIntegration
from src.integrations.storage import StorageIntegration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/atulya-tantra.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Metrics registry and metrics
metrics_registry = CollectorRegistry()
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
    registry=metrics_registry,
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    registry=metrics_registry,
)

# Global instances
agent_coordinator = None
system_monitor = None
decision_engine = None
multi_agent_coordinator = None
voice_interface = None
integrations = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global agent_coordinator, system_monitor, decision_engine, multi_agent_coordinator, voice_interface
    
    logger.info("Starting Atulya Tantra Level 5 AGI System...")
    
    try:
        # Initialize core components
        logger.info("Initializing core components...")
        
        # Initialize agent coordinator
        agent_coordinator = AgentCoordinator()
        logger.info("Agent Coordinator initialized")
        
        # Initialize system monitor
        system_monitor = SystemMonitor()
        logger.info("System Monitor initialized")
        
        # Initialize decision engine
        decision_engine = DecisionEngine()
        logger.info("Decision Engine initialized")
        
        # Initialize multi-agent coordinator
        multi_agent_coordinator = MultiAgentCoordinator()
        logger.info("Multi-Agent Coordinator initialized")
        
        # Initialize voice interface
        voice_interface = JARVISVoiceInterface()
        await voice_interface.start_voice_interface()
        logger.info("JARVIS Voice Interface initialized")
        
        # Start task executor
        await task_executor.start()
        logger.info("Task Executor started")
        
        # Initialize integrations
        logger.info("Initializing integrations...")
        integrations["calendar"] = CalendarIntegration()
        integrations["email"] = EmailIntegration()
        integrations["storage"] = StorageIntegration()
        
        # Initialize integrations
        for name, integration in integrations.items():
            await integration.initialize()
            logger.info(f"{name.title()} Integration initialized")
        
        # Initialize safety permissions (moved from module import)
        try:
            if bool(int(os.getenv("ENABLE_SAFETY_DEFAULTS", "1"))):
                await safety_system.grant_user_permission("default_user", "read")
                await safety_system.grant_user_permission("default_user", "write")
                await safety_system.grant_agent_permission("code_agent", "read")
                await safety_system.grant_agent_permission("code_agent", "write")
                await safety_system.grant_agent_permission("research_agent", "network")
                await safety_system.grant_agent_permission("data_agent", "read")
                await safety_system.grant_agent_permission("data_agent", "write")
                logger.info("Safety default permissions initialized")
        except Exception as e:
            logger.warning(f"Safety defaults init skipped/failed: {e}")

        logger.info("Atulya Tantra Level 5 AGI System started successfully!")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start Atulya Tantra: {e}")
        raise
    finally:
        # Cleanup
        logger.info("Shutting down Atulya Tantra...")
        
        if voice_interface:
            await voice_interface.stop_voice_interface()
        
        if task_executor:
            await task_executor.stop()
        
        logger.info("Atulya Tantra shutdown complete")

# Create FastAPI application
app = FastAPI(
    title="Atulya Tantra",
    description="Level 5 AGI System with JARVIS Intelligence, Skynet Operations, and Specialized Agents",
    version="2.5.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware for API endpoints"""
    # Apply rate limiting to chat and admin endpoints
    if request.url.path.startswith("/api/chat/") or request.url.path.startswith("/api/admin/"):
        rate_limiter = get_rate_limiter()
        client_ip = request.client.host if request.client else "unknown"
        
        if not await rate_limiter.is_allowed(client_ip):
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "retry_after": 60}
            )
    
    response = await call_next(request)
    return response

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests"""
    start_time = time.perf_counter()
    
    # Measure duration and record metrics
    path = request.url.path
    method = request.method
    with http_request_duration_seconds.labels(method=method, path=path).time():
        response = await call_next(request)
    
    process_time = time.perf_counter() - start_time
    try:
        http_requests_total.labels(method=method, path=path, status=str(response.status_code)).inc()
    except Exception:
        # Best-effort metrics
        pass
    
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.3f}s"
    )
    
    return response

# Add global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred",
            "request_id": getattr(request.state, "request_id", "unknown")
        }
    )

# Include API routes
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])

# Mount static files
app.mount("/webui", StaticFiles(directory="webui"), name="webui")
app.mount("/admin", StaticFiles(directory="webui/admin"), name="admin")

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Atulya Tantra",
        "version": "2.7.5",
        "description": "Level 5 AGI System",
        "status": "operational",
        "features": {
            "jarvis_intelligence": True,
            "skynet_operations": True,
            "specialized_agents": True,
            "multimodal_input": True,
            "voice_interface": True,
            "autonomous_operations": True,
            "advanced_reasoning": True,
            "external_integrations": True
        }
    }

# System status endpoint
@app.get("/api/status")
async def system_status():
    """Get comprehensive system status"""
    try:
        status = {
            "system": "operational",
            "version": "2.7.5",
            "timestamp": asyncio.get_event_loop().time(),
            "components": {}
        }
        
        # Check agent coordinator
        if agent_coordinator:
            status["components"]["agent_coordinator"] = await agent_coordinator.health_check()
        
        # Check system monitor
        if system_monitor:
            status["components"]["system_monitor"] = await system_monitor.health_check()
        
        # Check decision engine
        if decision_engine:
            status["components"]["decision_engine"] = await decision_engine.health_check()
        
        # Check multi-agent coordinator
        if multi_agent_coordinator:
            status["components"]["multi_agent_coordinator"] = await multi_agent_coordinator.health_check()
        
        # Check voice interface
        if voice_interface:
            status["components"]["voice_interface"] = await voice_interface.health_check()
        
        # Check task executor
        status["components"]["task_executor"] = await task_executor.health_check()
        
        # Check safety system
        status["components"]["safety_system"] = await safety_system.health_check()
        
        # Check integrations
        status["components"]["integrations"] = {}
        for name, integration in integrations.items():
            status["components"]["integrations"][name] = await integration.health_check()
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return {
            "system": "error",
            "error": str(e),
            "timestamp": asyncio.get_event_loop().time()
        }

# WebSocket endpoint for real-time communication
@app.websocket("/ws")
async def websocket_endpoint(websocket):
    """WebSocket endpoint for real-time communication"""
    await websocket.accept()
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            
            # Process message (placeholder)
            response = {
                "type": "response",
                "message": f"Received: {data}",
                "timestamp": asyncio.get_event_loop().time()
            }
            
            # Send response back to client
            await websocket.send_text(str(response))
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await websocket.close()

# Metrics endpoint for monitoring
@app.get("/metrics")
async def prometheus_metrics():
    data = generate_latest(metrics_registry)
    return JSONResponse(content=data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    # Run the application
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
