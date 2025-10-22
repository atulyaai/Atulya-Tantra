"""
Database utility functions for Atulya Tantra AGI
Common database operations and helpers
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

from .database import get_database, DatabaseInterface
from ..config.exceptions import DatabaseError, RecordNotFoundError
from ..config.logging import get_logger

logger = get_logger(__name__)


class DatabaseService:
    """Service class for common database operations"""
    
    def __init__(self, db: DatabaseInterface = None):
        self.db = db
    
    async def get_or_create_user(self, username: str, email: str = None) -> Dict[str, Any]:
        """Get existing user or create new one"""
        if not self.db:
            self.db = await get_database()
        
        # Try to find existing user
        user = await self.db.get_by_field("users", "username", username)
        if user:
            return user
        
        # Create new user
        user_data = {
            "username": username,
            "email": email,
            "roles": "user",
            "is_active": True
        }
        
        user_id = await self.db.insert("users", user_data)
        return await self.db.get_by_id("users", user_id)
    
    async def create_conversation(self, user_id: str, title: str = None) -> Dict[str, Any]:
        """Create a new conversation"""
        if not self.db:
            self.db = await get_database()
        
        conversation_data = {
            "user_id": user_id,
            "title": title or f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "is_active": True
        }
        
        conversation_id = await self.db.insert("conversations", conversation_data)
        return await self.db.get_by_id("conversations", conversation_id)
    
    async def add_message(self, conversation_id: str, role: str, content: str, 
                         tokens_used: int = 0, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Add a message to a conversation"""
        if not self.db:
            self.db = await get_database()
        
        message_data = {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "tokens_used": tokens_used,
            "metadata": json.dumps(metadata) if metadata else None
        }
        
        message_id = await self.db.insert("messages", message_data)
        return await self.db.get_by_id("messages", message_id)
    
    async def get_conversation_messages(self, conversation_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get messages for a conversation"""
        if not self.db:
            self.db = await get_database()
        
        # Get messages ordered by timestamp
        messages = await self.db.execute_raw(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC LIMIT ?",
            [conversation_id, limit]
        )
        
        return messages
    
    async def get_user_conversations(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get conversations for a user"""
        if not self.db:
            self.db = await get_database()
        
        conversations = await self.db.execute_raw(
            "SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
            [user_id, limit]
        )
        
        return conversations
    
    async def create_session(self, user_id: str, token: str, expires_at: datetime, 
                           refresh_token: str = None) -> Dict[str, Any]:
        """Create a user session"""
        if not self.db:
            self.db = await get_database()
        
        session_data = {
            "user_id": user_id,
            "token": token,
            "refresh_token": refresh_token,
            "expires_at": expires_at.isoformat(),
            "is_active": True
        }
        
        session_id = await self.db.insert("sessions", session_data)
        return await self.db.get_by_id("sessions", session_id)
    
    async def get_active_session(self, token: str) -> Optional[Dict[str, Any]]:
        """Get active session by token"""
        if not self.db:
            self.db = await get_database()
        
        session = await self.db.get_by_field("sessions", "token", token)
        
        if not session:
            return None
        
        # Check if session is expired
        expires_at = datetime.fromisoformat(session["expires_at"])
        if expires_at < datetime.utcnow():
            # Mark session as inactive
            await self.db.update("sessions", session["id"], {"is_active": False})
            return None
        
        return session
    
    async def log_agent_execution(self, agent_type: str, task: str, status: str,
                                 duration_ms: int = None, result: str = None, 
                                 error: str = None, user_id: str = None,
                                 conversation_id: str = None) -> Dict[str, Any]:
        """Log agent execution"""
        if not self.db:
            self.db = await get_database()
        
        log_data = {
            "agent_type": agent_type,
            "task": task,
            "status": status,
            "duration_ms": duration_ms,
            "result": result,
            "error": error,
            "user_id": user_id,
            "conversation_id": conversation_id
        }
        
        log_id = await self.db.insert("agent_logs", log_data)
        return await self.db.get_by_id("agent_logs", log_id)
    
    async def store_memory(self, user_id: str, memory_type: str, content: str,
                          embedding_vector: List[float] = None, 
                          importance_score: int = 0,
                          metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Store a memory"""
        if not self.db:
            self.db = await get_database()
        
        memory_data = {
            "user_id": user_id,
            "memory_type": memory_type,
            "content": content,
            "embedding_vector": json.dumps(embedding_vector) if embedding_vector else None,
            "importance_score": importance_score,
            "metadata": json.dumps(metadata) if metadata else None
        }
        
        memory_id = await self.db.insert("memories", memory_data)
        return await self.db.get_by_id("memories", memory_id)
    
    async def search_memories(self, user_id: str, query: str, 
                            memory_types: List[str] = None,
                            limit: int = 10) -> List[Dict[str, Any]]:
        """Search memories for a user"""
        if not self.db:
            self.db = await get_database()
        
        # Build query safely with parameterized queries
        where_conditions = ["user_id = ?"]
        params = [user_id]
        
        if memory_types:
            placeholders = ",".join(["?" for _ in memory_types])
            where_conditions.append(f"memory_type IN ({placeholders})")
            params.extend(memory_types)
        
        where_clause = " AND ".join(where_conditions)
        
        sql = f"""
            SELECT * FROM memories 
            WHERE {where_clause} 
            AND content LIKE ? 
            ORDER BY importance_score DESC, created_at DESC 
            LIMIT ?
        """
        params.extend([f"%{query}%", limit])
        
        memories = await self.db.execute_raw(sql, params)
        return memories
    
    async def add_knowledge_node(self, node_type: str, name: str, 
                                description: str = None,
                                properties: Dict[str, Any] = None) -> Dict[str, Any]:
        """Add a knowledge graph node"""
        if not self.db:
            self.db = await get_database()
        
        node_data = {
            "node_type": node_type,
            "name": name,
            "description": description,
            "properties": json.dumps(properties) if properties else None
        }
        
        node_id = await self.db.insert("knowledge_nodes", node_data)
        return await self.db.get_by_id("knowledge_nodes", node_id)
    
    async def add_knowledge_edge(self, source_node_id: str, target_node_id: str,
                                relationship_type: str, weight: int = 1,
                                properties: Dict[str, Any] = None) -> Dict[str, Any]:
        """Add a knowledge graph edge"""
        if not self.db:
            self.db = await get_database()
        
        edge_data = {
            "source_node_id": source_node_id,
            "target_node_id": target_node_id,
            "relationship_type": relationship_type,
            "weight": weight,
            "properties": json.dumps(properties) if properties else None
        }
        
        edge_id = await self.db.insert("knowledge_edges", edge_data)
        return await self.db.get_by_id("knowledge_edges", edge_id)
    
    async def log_api_request(self, user_id: str, endpoint: str, method: str,
                             status_code: int, duration_ms: int = None,
                             request_size: int = None, response_size: int = None,
                             ip_address: str = None, user_agent: str = None) -> Dict[str, Any]:
        """Log API request"""
        if not self.db:
            self.db = await get_database()
        
        log_data = {
            "user_id": user_id,
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "request_size": request_size,
            "response_size": response_size,
            "ip_address": ip_address,
            "user_agent": user_agent
        }
        
        log_id = await self.db.insert("api_logs", log_data)
        return await self.db.get_by_id("api_logs", log_id)
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        if not self.db:
            self.db = await get_database()
        
        stats = {}
        
        # Count records in each table
        tables = ["users", "conversations", "messages", "sessions", "agent_logs", "memories"]
        for table in tables:
            stats[f"{table}_count"] = await self.db.count(table)
        
        # Get recent activity
        try:
            recent_messages = await self.db.execute_raw(
                "SELECT COUNT(*) as count FROM messages WHERE timestamp > ?",
                [datetime.utcnow() - timedelta(hours=24)]
            )
            stats["messages_last_24h"] = recent_messages[0]["count"] if recent_messages else 0
        except Exception as e:
            logger.warning(f"Failed to get recent message count: {e}")
            stats["messages_last_24h"] = 0
        
        return stats


# Global database service instance
_db_service: Optional[DatabaseService] = None


async def get_db_service() -> DatabaseService:
    """Get global database service instance"""
    global _db_service
    
    if _db_service is None:
        _db_service = DatabaseService()
    
    return _db_service


# Convenience functions for common operations
async def insert_record(table: str, data: Dict[str, Any]) -> str:
    """Insert a record into a table"""
    db_service = await get_db_service()
    return await db_service.db.insert(table, data)


async def get_record_by_id(table: str, record_id: str) -> Optional[Dict[str, Any]]:
    """Get a record by ID from a table"""
    db_service = await get_db_service()
    return await db_service.db.get_by_id(table, record_id)


async def update_record(table: str, record_id: str, data: Dict[str, Any]) -> bool:
    """Update a record by ID in a table"""
    db_service = await get_db_service()
    return await db_service.db.update(table, record_id, data)


# Export public API
__all__ = [
    "DatabaseService",
    "get_db_service",
    "insert_record",
    "get_record_by_id", 
    "update_record"
]
