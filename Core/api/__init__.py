"""
Web API for Atulya Tantra AGI
FastAPI backend with REST endpoints, JWT authentication, and real-time streaming
"""

from .main import (
    app,
    run_api,
    UserCreate,
    UserLogin,
    UserResponse,
    Token,
    ChatMessage,
    ChatResponse,
    TaskRequest,
    TaskResponse,
    SystemStatus
)
from .streaming import (
    MessageType,
    StreamEvent,
    ConnectionManager,
    StreamingChatHandler,
    TaskStreamingHandler,
    SystemMonitoringStreamer,
    RealTimeManager,
    get_real_time_manager,
    stream_chat_response,
    stream_task_updates,
    send_notification,
    get_real_time_stats
)

__all__ = [
    # FastAPI App
    "app",
    "run_api",
    
    # Pydantic Models
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "Token",
    "ChatMessage",
    "ChatResponse",
    "TaskRequest",
    "TaskResponse",
    "SystemStatus",
    
    # Streaming Components
    "MessageType",
    "StreamEvent",
    "ConnectionManager",
    "StreamingChatHandler",
    "TaskStreamingHandler",
    "SystemMonitoringStreamer",
    "RealTimeManager",
    
    # Streaming Functions
    "get_real_time_manager",
    "stream_chat_response",
    "stream_task_updates",
    "send_notification",
    "get_real_time_stats"
]

