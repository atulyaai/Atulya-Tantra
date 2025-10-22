"""
Real-time Communication System for Atulya Tantra AGI
Server-Sent Events (SSE) and WebSocket implementation for streaming responses
"""

import asyncio
import json
import uuid
from typing import Dict, List, Any, Optional, AsyncGenerator, Callable
from datetime import datetime
from enum import Enum
import weakref

from ..config.settings import settings
from ..config.logging import get_logger
from ..config.exceptions import AgentError
from ..jarvis import process_user_message, get_conversational_ai
from ..agents import get_orchestrator, submit_task, get_task_status
from ..skynet import get_system_health, get_system_metrics

logger = get_logger(__name__)


class MessageType(str, Enum):
    """Types of real-time messages"""
    CHAT_MESSAGE = "chat_message"
    CHAT_RESPONSE = "chat_response"
    TASK_UPDATE = "task_update"
    SYSTEM_ALERT = "system_alert"
    SYSTEM_METRIC = "system_metric"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    NOTIFICATION = "notification"


class StreamEvent:
    """Represents a streaming event"""
    
    def __init__(
        self,
        event_type: str,
        data: Dict[str, Any],
        event_id: str = None,
        retry: int = None
    ):
        self.event_type = event_type
        self.data = data
        self.event_id = event_id or str(uuid.uuid4())
        self.retry = retry
        self.timestamp = datetime.utcnow()
    
    def to_sse_format(self) -> str:
        """Convert to Server-Sent Events format"""
        lines = []
        
        if self.event_id:
            lines.append(f"id: {self.event_id}")
        
        if self.event_type:
            lines.append(f"event: {self.event_type}")
        
        if self.retry:
            lines.append(f"retry: {self.retry}")
        
        # Add data
        data_str = json.dumps(self.data)
        lines.append(f"data: {data_str}")
        
        # Add timestamp
        lines.append(f"data: {self.timestamp.isoformat()}")
        
        return "\n".join(lines) + "\n\n"
    
    def to_websocket_format(self) -> Dict[str, Any]:
        """Convert to WebSocket format"""
        return {
            "type": self.event_type,
            "data": self.data,
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat()
        }


class ConnectionManager:
    """Manages real-time connections"""
    
    def __init__(self):
        self.sse_connections: Dict[str, Any] = {}
        self.websocket_connections: Dict[str, Any] = {}
        self.user_connections: Dict[str, List[str]] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Cleanup task
        self.cleanup_task: Optional[asyncio.Task] = None
        self.is_running = False
    
    async def start(self):
        """Start the connection manager"""
        if self.is_running:
            return
        
        self.is_running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Connection manager started")
    
    async def stop(self):
        """Stop the connection manager"""
        self.is_running = False
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        for connection_id in list(self.sse_connections.keys()):
            await self.remove_sse_connection(connection_id)
        
        for connection_id in list(self.websocket_connections.keys()):
            await self.remove_websocket_connection(connection_id)
        
        logger.info("Connection manager stopped")
    
    async def add_sse_connection(
        self, 
        connection_id: str, 
        response_writer: Any, 
        user_id: str = None,
        metadata: Dict[str, Any] = None
    ):
        """Add an SSE connection"""
        self.sse_connections[connection_id] = response_writer
        self.connection_metadata[connection_id] = {
            "type": "sse",
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "metadata": metadata or {}
        }
        
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
            self.user_connections[user_id].append(connection_id)
        
        logger.info(f"SSE connection added: {connection_id}")
    
    async def add_websocket_connection(
        self, 
        connection_id: str, 
        websocket: Any, 
        user_id: str = None,
        metadata: Dict[str, Any] = None
    ):
        """Add a WebSocket connection"""
        self.websocket_connections[connection_id] = websocket
        self.connection_metadata[connection_id] = {
            "type": "websocket",
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "metadata": metadata or {}
        }
        
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
            self.user_connections[user_id].append(connection_id)
        
        logger.info(f"WebSocket connection added: {connection_id}")
    
    async def remove_sse_connection(self, connection_id: str):
        """Remove an SSE connection"""
        if connection_id in self.sse_connections:
            del self.sse_connections[connection_id]
            
            # Remove from user connections
            metadata = self.connection_metadata.get(connection_id, {})
            user_id = metadata.get("user_id")
            if user_id and user_id in self.user_connections:
                if connection_id in self.user_connections[user_id]:
                    self.user_connections[user_id].remove(connection_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            
            # Remove metadata
            if connection_id in self.connection_metadata:
                del self.connection_metadata[connection_id]
            
            logger.info(f"SSE connection removed: {connection_id}")
    
    async def remove_websocket_connection(self, connection_id: str):
        """Remove a WebSocket connection"""
        if connection_id in self.websocket_connections:
            del self.websocket_connections[connection_id]
            
            # Remove from user connections
            metadata = self.connection_metadata.get(connection_id, {})
            user_id = metadata.get("user_id")
            if user_id and user_id in self.user_connections:
                if connection_id in self.user_connections[user_id]:
                    self.user_connections[user_id].remove(connection_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            
            # Remove metadata
            if connection_id in self.connection_metadata:
                del self.connection_metadata[connection_id]
            
            logger.info(f"WebSocket connection removed: {connection_id}")
    
    async def send_to_connection(
        self, 
        connection_id: str, 
        event: StreamEvent
    ) -> bool:
        """Send event to a specific connection"""
        try:
            metadata = self.connection_metadata.get(connection_id, {})
            connection_type = metadata.get("type")
            
            if connection_type == "sse" and connection_id in self.sse_connections:
                response_writer = self.sse_connections[connection_id]
                await response_writer.write(event.to_sse_format().encode())
                await response_writer.drain()
                
                # Update last activity
                self.connection_metadata[connection_id]["last_activity"] = datetime.utcnow()
                return True
            
            elif connection_type == "websocket" and connection_id in self.websocket_connections:
                websocket = self.websocket_connections[connection_id]
                await websocket.send_text(json.dumps(event.to_websocket_format()))
                
                # Update last activity
                self.connection_metadata[connection_id]["last_activity"] = datetime.utcnow()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error sending to connection {connection_id}: {e}")
            return False
    
    async def send_to_user(
        self, 
        user_id: str, 
        event: StreamEvent
    ) -> int:
        """Send event to all connections for a user"""
        sent_count = 0
        
        if user_id in self.user_connections:
            for connection_id in self.user_connections[user_id]:
                if await self.send_to_connection(connection_id, event):
                    sent_count += 1
        
        return sent_count
    
    async def broadcast(self, event: StreamEvent) -> int:
        """Broadcast event to all connections"""
        sent_count = 0
        
        # Send to SSE connections
        for connection_id in list(self.sse_connections.keys()):
            if await self.send_to_connection(connection_id, event):
                sent_count += 1
        
        # Send to WebSocket connections
        for connection_id in list(self.websocket_connections.keys()):
            if await self.send_to_connection(connection_id, event):
                sent_count += 1
        
        return sent_count
    
    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        return {
            "sse_connections": len(self.sse_connections),
            "websocket_connections": len(self.websocket_connections),
            "total_connections": len(self.sse_connections) + len(self.websocket_connections),
            "unique_users": len(self.user_connections),
            "connections_by_user": {user_id: len(conns) for user_id, conns in self.user_connections.items()}
        }
    
    async def _cleanup_loop(self):
        """Cleanup inactive connections"""
        while self.is_running:
            try:
                current_time = datetime.utcnow()
                inactive_connections = []
                
                # Find inactive connections (older than 1 hour)
                for connection_id, metadata in self.connection_metadata.items():
                    last_activity = metadata.get("last_activity")
                    if last_activity and (current_time - last_activity).total_seconds() > 3600:
                        inactive_connections.append(connection_id)
                
                # Remove inactive connections
                for connection_id in inactive_connections:
                    metadata = self.connection_metadata.get(connection_id, {})
                    if metadata.get("type") == "sse":
                        await self.remove_sse_connection(connection_id)
                    elif metadata.get("type") == "websocket":
                        await self.remove_websocket_connection(connection_id)
                
                if inactive_connections:
                    logger.info(f"Cleaned up {len(inactive_connections)} inactive connections")
                
                # Wait before next cleanup
                await asyncio.sleep(300)  # 5 minutes
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(60)


class StreamingChatHandler:
    """Handles streaming chat responses"""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
    
    async def stream_chat_response(
        self, 
        user_id: str, 
        message: str, 
        connection_id: str = None,
        metadata: Dict[str, Any] = None
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream chat response"""
        try:
            # Send initial event
            initial_event = StreamEvent(
                event_type=MessageType.CHAT_MESSAGE.value,
                data={
                    "message": message,
                    "user_id": user_id,
                    "status": "processing"
                }
            )
            
            if connection_id:
                await self.connection_manager.send_to_connection(connection_id, initial_event)
            else:
                await self.connection_manager.send_to_user(user_id, initial_event)
            
            yield initial_event
            
            # Process message with JARVIS
            response_data = await process_user_message(
                user_id=user_id,
                message=message,
                metadata=metadata
            )
            
            # Stream response word by word
            response_text = response_data["response"]
            words = response_text.split()
            
            for i, word in enumerate(words):
                chunk_event = StreamEvent(
                    event_type=MessageType.CHAT_RESPONSE.value,
                    data={
                        "chunk": word + " ",
                        "index": i,
                        "total": len(words),
                        "is_final": i == len(words) - 1,
                        "user_sentiment": response_data.get("user_sentiment"),
                        "jarvis_emotional_state": response_data.get("jarvis_emotional_state"),
                        "conversation_context": response_data.get("conversation_context", {})
                    }
                )
                
                if connection_id:
                    await self.connection_manager.send_to_connection(connection_id, chunk_event)
                else:
                    await self.connection_manager.send_to_user(user_id, chunk_event)
                
                yield chunk_event
                
                # Small delay for streaming effect
                await asyncio.sleep(0.05)
            
            # Send completion event
            completion_event = StreamEvent(
                event_type=MessageType.CHAT_RESPONSE.value,
                data={
                    "status": "completed",
                    "full_response": response_text,
                    "metadata": response_data.get("metadata", {})
                }
            )
            
            if connection_id:
                await self.connection_manager.send_to_connection(connection_id, completion_event)
            else:
                await self.connection_manager.send_to_user(user_id, completion_event)
            
            yield completion_event
            
        except Exception as e:
            logger.error(f"Error streaming chat response: {e}")
            
            error_event = StreamEvent(
                event_type=MessageType.ERROR.value,
                data={
                    "error": str(e),
                    "message": "Failed to process chat message"
                }
            )
            
            if connection_id:
                await self.connection_manager.send_to_connection(connection_id, error_event)
            else:
                await self.connection_manager.send_to_user(user_id, error_event)
            
            yield error_event


class TaskStreamingHandler:
    """Handles streaming task updates"""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
    
    async def stream_task_updates(
        self, 
        task_id: str, 
        user_id: str,
        connection_id: str = None
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream task execution updates"""
        try:
            # Send initial task event
            initial_event = StreamEvent(
                event_type=MessageType.TASK_UPDATE.value,
                data={
                    "task_id": task_id,
                    "status": "submitted",
                    "message": "Task submitted successfully"
                }
            )
            
            if connection_id:
                await self.connection_manager.send_to_connection(connection_id, initial_event)
            else:
                await self.connection_manager.send_to_user(user_id, initial_event)
            
            yield initial_event
            
            # Monitor task status
            orchestrator = await get_orchestrator()
            max_wait = 300  # 5 minutes
            wait_time = 0
            
            while wait_time < max_wait:
                try:
                    status = await orchestrator.get_task_status(task_id)
                    
                    if status:
                        status_event = StreamEvent(
                            event_type=MessageType.TASK_UPDATE.value,
                            data={
                                "task_id": task_id,
                                "status": status.get("status", "unknown"),
                                "progress": status.get("progress", 0),
                                "message": status.get("message", ""),
                                "result": status.get("result")
                            }
                        )
                        
                        if connection_id:
                            await self.connection_manager.send_to_connection(connection_id, status_event)
                        else:
                            await self.connection_manager.send_to_user(user_id, status_event)
                        
                        yield status_event
                        
                        # Check if task is complete
                        if status.get("status") in ["completed", "failed", "cancelled"]:
                            break
                    
                    await asyncio.sleep(2)
                    wait_time += 2
                    
                except Exception as e:
                    logger.error(f"Error monitoring task {task_id}: {e}")
                    break
            
            # Send final event
            final_event = StreamEvent(
                event_type=MessageType.TASK_UPDATE.value,
                data={
                    "task_id": task_id,
                    "status": "monitoring_complete",
                    "message": "Task monitoring completed"
                }
            )
            
            if connection_id:
                await self.connection_manager.send_to_connection(connection_id, final_event)
            else:
                await self.connection_manager.send_to_user(user_id, final_event)
            
            yield final_event
            
        except Exception as e:
            logger.error(f"Error streaming task updates: {e}")
            
            error_event = StreamEvent(
                event_type=MessageType.ERROR.value,
                data={
                    "error": str(e),
                    "task_id": task_id,
                    "message": "Failed to monitor task"
                }
            )
            
            if connection_id:
                await self.connection_manager.send_to_connection(connection_id, error_event)
            else:
                await self.connection_manager.send_to_user(user_id, error_event)
            
            yield error_event


class SystemMonitoringStreamer:
    """Streams system monitoring data"""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.is_streaming = False
        self.streaming_task: Optional[asyncio.Task] = None
    
    async def start_streaming(self):
        """Start streaming system monitoring data"""
        if self.is_streaming:
            return
        
        self.is_streaming = True
        self.streaming_task = asyncio.create_task(self._streaming_loop())
        logger.info("System monitoring streaming started")
    
    async def stop_streaming(self):
        """Stop streaming system monitoring data"""
        self.is_streaming = False
        
        if self.streaming_task:
            self.streaming_task.cancel()
            try:
                await self.streaming_task
            except asyncio.CancelledError:
                pass
        
        logger.info("System monitoring streaming stopped")
    
    async def _streaming_loop(self):
        """Main streaming loop for system monitoring"""
        while self.is_streaming:
            try:
                # Get system health
                health = await get_system_health()
                
                health_event = StreamEvent(
                    event_type=MessageType.SYSTEM_ALERT.value,
                    data={
                        "type": "health_update",
                        "overall_status": health.get("overall_status"),
                        "checks": health.get("checks", {}),
                        "alerts": health.get("alerts", {})
                    }
                )
                
                await self.connection_manager.broadcast(health_event)
                
                # Get recent metrics
                metrics = await get_system_metrics(limit=5)
                
                if metrics:
                    metrics_event = StreamEvent(
                        event_type=MessageType.SYSTEM_METRIC.value,
                        data={
                            "type": "metrics_update",
                            "metrics": metrics
                        }
                    )
                    
                    await self.connection_manager.broadcast(metrics_event)
                
                # Wait before next update
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in system monitoring stream: {e}")
                await asyncio.sleep(60)


class RealTimeManager:
    """Main real-time communication manager"""
    
    def __init__(self):
        self.connection_manager = ConnectionManager()
        self.chat_handler = StreamingChatHandler(self.connection_manager)
        self.task_handler = TaskStreamingHandler(self.connection_manager)
        self.system_monitor = SystemMonitoringStreamer(self.connection_manager)
    
    async def start(self):
        """Start the real-time manager"""
        await self.connection_manager.start()
        await self.system_monitor.start_streaming()
        logger.info("Real-time manager started")
    
    async def stop(self):
        """Stop the real-time manager"""
        await self.system_monitor.stop_streaming()
        await self.connection_manager.stop()
        logger.info("Real-time manager stopped")
    
    async def send_heartbeat(self):
        """Send heartbeat to all connections"""
        heartbeat_event = StreamEvent(
            event_type=MessageType.HEARTBEAT.value,
            data={
                "timestamp": datetime.utcnow().isoformat(),
                "server_status": "alive"
            }
        )
        
        sent_count = await self.connection_manager.broadcast(heartbeat_event)
        logger.debug(f"Heartbeat sent to {sent_count} connections")
    
    async def send_notification(
        self, 
        user_id: str, 
        title: str, 
        message: str, 
        notification_type: str = "info"
    ):
        """Send notification to a user"""
        notification_event = StreamEvent(
            event_type=MessageType.NOTIFICATION.value,
            data={
                "title": title,
                "message": message,
                "type": notification_type,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        sent_count = await self.connection_manager.send_to_user(user_id, notification_event)
        logger.info(f"Notification sent to user {user_id}: {sent_count} connections")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get real-time communication statistics"""
        connection_stats = await self.connection_manager.get_connection_stats()
        
        return {
            "connection_manager": connection_stats,
            "system_monitoring": {
                "streaming_active": self.system_monitor.is_streaming
            },
            "timestamp": datetime.utcnow().isoformat()
        }


# Global real-time manager instance
_real_time_manager: Optional[RealTimeManager] = None


async def get_real_time_manager() -> RealTimeManager:
    """Get global real-time manager instance"""
    global _real_time_manager
    
    if _real_time_manager is None:
        _real_time_manager = RealTimeManager()
        await _real_time_manager.start()
    
    return _real_time_manager


async def stream_chat_response(
    user_id: str, 
    message: str, 
    connection_id: str = None,
    metadata: Dict[str, Any] = None
) -> AsyncGenerator[StreamEvent, None]:
    """Stream chat response"""
    manager = await get_real_time_manager()
    async for event in manager.chat_handler.stream_chat_response(
        user_id, message, connection_id, metadata
    ):
        yield event


async def stream_task_updates(
    task_id: str, 
    user_id: str,
    connection_id: str = None
) -> AsyncGenerator[StreamEvent, None]:
    """Stream task updates"""
    manager = await get_real_time_manager()
    async for event in manager.task_handler.stream_task_updates(
        task_id, user_id, connection_id
    ):
        yield event


async def send_notification(
    user_id: str, 
    title: str, 
    message: str, 
    notification_type: str = "info"
):
    """Send notification to user"""
    manager = await get_real_time_manager()
    await manager.send_notification(user_id, title, message, notification_type)


async def get_real_time_stats() -> Dict[str, Any]:
    """Get real-time communication statistics"""
    manager = await get_real_time_manager()
    return await manager.get_stats()


# Export public API
__all__ = [
    "MessageType",
    "StreamEvent",
    "ConnectionManager",
    "StreamingChatHandler",
    "TaskStreamingHandler",
    "SystemMonitoringStreamer",
    "RealTimeManager",
    "get_real_time_manager",
    "stream_chat_response",
    "stream_task_updates",
    "send_notification",
    "get_real_time_stats"
]
