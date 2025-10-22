"""
FastAPI Backend for Atulya Tantra AGI
REST API endpoints, JWT authentication, and real-time communication
"""

import asyncio
import json
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from enum import Enum
import uuid
import jwt
from passlib.context import CryptContext
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import uvicorn

from ..config.settings import settings
from ..config.logging import get_logger
from ..config.exceptions import AgentError
from ..jarvis import process_user_message, get_conversation_summary, reset_conversation
from ..agents import get_orchestrator, submit_task, get_task_status
from ..skynet import get_system_health, get_system_metrics, get_system_alerts
from ..database.service import get_db_service, insert_record, get_record_by_id, update_record

logger = get_logger(__name__)

# Security setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, List[str]] = {}
    
    async def connect(self, websocket: WebSocket, connection_id: str, user_id: str = None):
        """Accept a WebSocket connection"""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
            self.user_connections[user_id].append(connection_id)
        
        logger.info(f"WebSocket connected: {connection_id}")
    
    def disconnect(self, connection_id: str, user_id: str = None):
        """Disconnect a WebSocket connection"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        
        if user_id and user_id in self.user_connections:
            if connection_id in self.user_connections[user_id]:
                self.user_connections[user_id].remove(connection_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        logger.info(f"WebSocket disconnected: {connection_id}")
    
    async def send_personal_message(self, message: str, connection_id: str):
        """Send message to specific connection"""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            await websocket.send_text(message)
    
    async def send_to_user(self, message: str, user_id: str):
        """Send message to all connections for a user"""
        if user_id in self.user_connections:
            for connection_id in self.user_connections[user_id]:
                await self.send_personal_message(message, connection_id)
    
    async def broadcast(self, message: str):
        """Broadcast message to all connections"""
        for connection_id in self.active_connections:
            await self.send_personal_message(message, connection_id)

manager = ConnectionManager()

# Pydantic models
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., regex=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    user_sentiment: str
    jarvis_emotional_state: str
    conversation_context: Dict[str, Any]
    metadata: Dict[str, Any]

class TaskRequest(BaseModel):
    agent_type: str
    task_type: str
    description: str
    input_data: Optional[Dict[str, Any]] = None
    priority: str = "normal"
    timeout_seconds: Optional[int] = 300

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str
    metadata: Dict[str, Any]

class SystemStatus(BaseModel):
    overall_status: str
    timestamp: datetime
    checks: Dict[str, Any]
    metrics: Dict[str, Any]
    alerts: Dict[str, Any]

# Authentication functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def verify_token(token: str) -> Dict[str, Any]:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Get current authenticated user"""
    token = credentials.credentials
    payload = verify_token(token)
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    try:
        user = await get_record_by_id("users", user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_active_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Get current active user"""
    if not current_user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

# Create FastAPI app
app = FastAPI(
    title="Atulya Tantra AGI API",
    description="Advanced AI Assistant API with JARVIS and Skynet capabilities",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_hosts
)

# API Routes

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Atulya Tantra AGI API",
        "version": "3.0.0",
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        system_health = await get_system_health()
        return {
            "status": "healthy",
            "system_health": system_health,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

# Authentication endpoints
@app.post("/api/auth/register", response_model=UserResponse)
async def register_user(user: UserCreate):
    """Register a new user"""
    try:
        # Check if user already exists
        existing_user = await get_record_by_id("users", user.username, field="username")
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Username already registered"
            )
        
        # Create user
        user_id = str(uuid.uuid4())
        hashed_password = get_password_hash(user.password)
        
        user_data = {
            "user_id": user_id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "hashed_password": hashed_password,
            "is_active": True,
            "created_at": datetime.utcnow().isoformat(),
            "last_login": None
        }
        
        await insert_record("users", user_data)
        
        # Return user without password
        user_response = UserResponse(**{
            "user_id": user_id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": True,
            "created_at": datetime.fromisoformat(user_data["created_at"]),
            "last_login": None
        })
        
        logger.info(f"User registered: {user.username}")
        return user_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Registration failed"
        )

@app.post("/api/auth/login", response_model=Token)
async def login_user(user: UserLogin):
    """Login user and return access token"""
    try:
        # Get user by username
        user_data = await get_record_by_id("users", user.username, field="username")
        if not user_data:
            raise HTTPException(
                status_code=401,
                detail="Incorrect username or password"
            )
        
        # Verify password
        if not verify_password(user.password, user_data["hashed_password"]):
            raise HTTPException(
                status_code=401,
                detail="Incorrect username or password"
            )
        
        # Check if user is active
        if not user_data.get("is_active", True):
            raise HTTPException(
                status_code=400,
                detail="Inactive user"
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.jwt_expire_minutes)
        access_token = create_access_token(
            data={"sub": user_data["user_id"], "username": user_data["username"]},
            expires_delta=access_token_expires
        )
        
        # Update last login
        await update_record("users", user_data["user_id"], {
            "last_login": datetime.utcnow().isoformat()
        })
        
        logger.info(f"User logged in: {user.username}")
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.jwt_expire_minutes * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Login failed"
        )

@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """Get current user information"""
    return UserResponse(**{
        "user_id": current_user["user_id"],
        "username": current_user["username"],
        "email": current_user["email"],
        "full_name": current_user.get("full_name"),
        "is_active": current_user.get("is_active", True),
        "created_at": datetime.fromisoformat(current_user["created_at"]),
        "last_login": datetime.fromisoformat(current_user["last_login"]) if current_user.get("last_login") else None
    })

# Chat endpoints
@app.post("/api/chat/send", response_model=ChatResponse)
async def send_message(
    message: ChatMessage,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Send a message to JARVIS"""
    try:
        user_id = current_user["user_id"]
        conversation_id = message.conversation_id or str(uuid.uuid4())
        
        # Process message with JARVIS
        response_data = await process_user_message(
            user_id=user_id,
            message=message.message,
            metadata=message.metadata
        )
        
        # Create response
        chat_response = ChatResponse(
            response=response_data["response"],
            conversation_id=conversation_id,
            user_sentiment=response_data.get("user_sentiment", "neutral"),
            jarvis_emotional_state=response_data.get("jarvis_emotional_state", "neutral"),
            conversation_context=response_data.get("conversation_context", {}),
            metadata=response_data.get("metadata", {})
        )
        
        logger.info(f"Message processed for user {user_id}")
        return chat_response
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to process message"
        )

@app.get("/api/chat/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Get conversation history"""
    try:
        user_id = current_user["user_id"]
        
        # Get conversation summary
        summary = await get_conversation_summary(user_id)
        
        return {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "summary": summary,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Get conversation error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get conversation"
        )

@app.delete("/api/chat/conversations/{conversation_id}")
async def reset_conversation_endpoint(
    conversation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Reset conversation"""
    try:
        user_id = current_user["user_id"]
        
        # Reset conversation
        success = await reset_conversation(user_id)
        
        return {
            "success": success,
            "message": "Conversation reset successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Reset conversation error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to reset conversation"
        )

# Agent endpoints
@app.post("/api/agents/task", response_model=TaskResponse)
async def submit_agent_task(
    task: TaskRequest,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Submit a task to an agent"""
    try:
        user_id = current_user["user_id"]
        
        # Submit task to orchestrator
        task_id = await submit_task(
            agent_type=task.agent_type,
            task_type=task.task_type,
            description=task.description,
            input_data=task.input_data,
            priority=task.priority,
            timeout_seconds=task.timeout_seconds
        )
        
        return TaskResponse(
            task_id=task_id,
            status="submitted",
            message="Task submitted successfully",
            metadata={
                "user_id": user_id,
                "submitted_at": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Task submission error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to submit task"
        )

@app.get("/api/agents/task/{task_id}")
async def get_agent_task_status(
    task_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Get task status"""
    try:
        # Get task status
        status = await get_task_status(task_id)
        
        if not status:
            raise HTTPException(
                status_code=404,
                detail="Task not found"
            )
        
        return {
            "task_id": task_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get task status error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get task status"
        )

# System monitoring endpoints
@app.get("/api/system/health", response_model=SystemStatus)
async def get_system_health_endpoint(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Get system health status"""
    try:
        health = await get_system_health()
        
        return SystemStatus(
            overall_status=health.get("overall_status", "unknown"),
            timestamp=datetime.fromisoformat(health.get("timestamp", datetime.utcnow().isoformat())),
            checks=health.get("checks", {}),
            metrics=health.get("metrics", {}),
            alerts=health.get("alerts", {})
        )
        
    except Exception as e:
        logger.error(f"System health error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get system health"
        )

@app.get("/api/system/metrics")
async def get_system_metrics_endpoint(
    metric_name: Optional[str] = None,
    limit: int = 100,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Get system metrics"""
    try:
        metrics = await get_system_metrics(metric_name=metric_name, limit=limit)
        
        return {
            "metrics": metrics,
            "count": len(metrics),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"System metrics error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get system metrics"
        )

@app.get("/api/system/alerts")
async def get_system_alerts_endpoint(
    unresolved_only: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Get system alerts"""
    try:
        alerts = await get_system_alerts(unresolved_only=unresolved_only)
        
        return {
            "alerts": alerts,
            "count": len(alerts),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"System alerts error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get system alerts"
        )

# WebSocket endpoints
@app.websocket("/ws/{connection_id}")
async def websocket_endpoint(websocket: WebSocket, connection_id: str):
    """WebSocket endpoint for real-time communication"""
    await manager.connect(websocket, connection_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Process message
            if message_data.get("type") == "chat":
                user_id = message_data.get("user_id")
                message = message_data.get("message")
                
                if user_id and message:
                    # Process with JARVIS
                    response_data = await process_user_message(user_id, message)
                    
                    # Send response back
                    response = {
                        "type": "chat_response",
                        "response": response_data["response"],
                        "user_sentiment": response_data.get("user_sentiment"),
                        "jarvis_emotional_state": response_data.get("jarvis_emotional_state"),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
                    await manager.send_personal_message(json.dumps(response), connection_id)
            
            elif message_data.get("type") == "ping":
                # Respond to ping
                pong = {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                }
                await manager.send_personal_message(json.dumps(pong), connection_id)
    
    except WebSocketDisconnect:
        manager.disconnect(connection_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(connection_id)

# Streaming endpoints
@app.post("/api/chat/stream")
async def stream_chat_response(
    message: ChatMessage,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Stream chat response"""
    try:
        user_id = current_user["user_id"]
        
        async def generate_response():
            # Process message and stream response
            response_data = await process_user_message(
                user_id=user_id,
                message=message.message,
                metadata=message.metadata
            )
            
            # Stream the response
            response_text = response_data["response"]
            words = response_text.split()
            
            for i, word in enumerate(words):
                chunk = {
                    "chunk": word + " ",
                    "index": i,
                    "total": len(words),
                    "is_final": i == len(words) - 1,
                    "metadata": response_data.get("metadata", {})
                }
                
                yield f"data: {json.dumps(chunk)}\n\n"
                
                # Small delay for streaming effect
                await asyncio.sleep(0.05)
        
        return StreamingResponse(
            generate_response(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )
        
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to stream response"
        )

# Admin endpoints
@app.get("/api/admin/status")
async def get_admin_status(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """Get admin system status"""
    try:
        # Check if user has admin privileges
        if not current_user.get("is_admin", False):
            raise HTTPException(
                status_code=403,
                detail="Admin privileges required"
            )
        
        # Get comprehensive system status
        system_health = await get_system_health()
        
        return {
            "system_health": system_health,
            "active_connections": len(manager.active_connections),
            "user_connections": len(manager.user_connections),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin status error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get admin status"
        )

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "status_code": 500,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Application startup"""
    logger.info("Atulya Tantra AGI API starting up...")
    
    # Initialize database
    try:
        db_service = await get_db_service()
        logger.info("Database service initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    
    logger.info("API startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown"""
    logger.info("Atulya Tantra AGI API shutting down...")
    
    # Close all WebSocket connections
    for connection_id in list(manager.active_connections.keys()):
        manager.disconnect(connection_id)
    
    logger.info("API shutdown complete")

# Main application runner
def run_api(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Run the FastAPI application"""
    uvicorn.run(
        "Core.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )

if __name__ == "__main__":
    run_api()
