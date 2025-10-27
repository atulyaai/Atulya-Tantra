"""
Session management for user authentication
Handles session creation, validation, and cleanup
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from ..config.settings import settings
from ..config.logging import get_logger
from ..database.service import get_db_service, insert_record, get_record_by_id, update_record, delete_record

logger = get_logger(__name__)

@dataclass
class SessionData:
    """Session data structure"""
    session_id: str
    user_id: str
    username: str
    created_at: datetime
    last_accessed: datetime
    expires_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool = True
    metadata: Optional[Dict[str, Any]] = None

class SessionManager:
    """Manages user sessions"""
    
    def __init__(self):
        self.default_expire_hours = 24
        self.max_sessions_per_user = 5
        self.cleanup_interval_hours = 1
    
    async def create_session(
        self, 
        user_id: str, 
        username: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expires_hours: Optional[int] = None
    ) -> SessionData:
        """Create a new user session"""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        expires_hours = expires_hours or self.default_expire_hours
        expires_at = now + timedelta(hours=expires_hours)
        
        session_data = SessionData(
            session_id=session_id,
            user_id=user_id,
            username=username,
            created_at=now,
            last_accessed=now,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            is_active=True,
            metadata=metadata or {}
        )
        
        # Store session in database
        await self._store_session(session_data)
        
        # Clean up old sessions for this user
        await self._cleanup_user_sessions(user_id)
        
        logger.info(f"Session created for user {username}: {session_id}")
        return session_data
    
    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session by ID"""
        try:
            session_record = await get_record_by_id("sessions", session_id)
            if not session_record:
                return None
            
            # Check if session is expired
            expires_at = datetime.fromisoformat(session_record["expires_at"])
            if datetime.utcnow() > expires_at:
                await self.delete_session(session_id)
                return None
            
            # Check if session is active
            if not session_record.get("is_active", True):
                return None
            
            # Update last accessed time
            await self._update_last_accessed(session_id)
            
            return SessionData(
                session_id=session_record["session_id"],
                user_id=session_record["user_id"],
                username=session_record["username"],
                created_at=datetime.fromisoformat(session_record["created_at"]),
                last_accessed=datetime.fromisoformat(session_record["last_accessed"]),
                expires_at=expires_at,
                ip_address=session_record.get("ip_address"),
                user_agent=session_record.get("user_agent"),
                is_active=session_record.get("is_active", True),
                metadata=session_record.get("metadata", {})
            )
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}")
            return None
    
    async def validate_session(self, session_id: str) -> bool:
        """Validate if session exists and is active"""
        session = await self.get_session(session_id)
        return session is not None
    
    async def refresh_session(self, session_id: str, expires_hours: Optional[int] = None) -> bool:
        """Refresh session expiration time"""
        try:
            session = await self.get_session(session_id)
            if not session:
                return False
            
            expires_hours = expires_hours or self.default_expire_hours
            new_expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
            
            await update_record("sessions", session_id, {
                "expires_at": new_expires_at.isoformat(),
                "last_accessed": datetime.utcnow().isoformat()
            })
            
            logger.info(f"Session refreshed: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error refreshing session {session_id}: {e}")
            return False
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        try:
            await delete_record("sessions", session_id)
            logger.info(f"Session deleted: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            return False
    
    async def delete_user_sessions(self, user_id: str) -> int:
        """Delete all sessions for a user"""
        try:
            # Get all sessions for user
            db_service = await get_db_service()
            sessions = await db_service.get_records_by_field("sessions", "user_id", user_id)
            
            deleted_count = 0
            for session in sessions:
                if await self.delete_session(session["session_id"]):
                    deleted_count += 1
            
            logger.info(f"Deleted {deleted_count} sessions for user {user_id}")
            return deleted_count
        except Exception as e:
            logger.error(f"Error deleting sessions for user {user_id}: {e}")
            return 0
    
    async def get_user_sessions(self, user_id: str) -> List[SessionData]:
        """Get all active sessions for a user"""
        try:
            db_service = await get_db_service()
            sessions = await db_service.get_records_by_field("sessions", "user_id", user_id)
            
            session_list = []
            for session_record in sessions:
                if session_record.get("is_active", True):
                    expires_at = datetime.fromisoformat(session_record["expires_at"])
                    if datetime.utcnow() <= expires_at:
                        session_list.append(SessionData(
                            session_id=session_record["session_id"],
                            user_id=session_record["user_id"],
                            username=session_record["username"],
                            created_at=datetime.fromisoformat(session_record["created_at"]),
                            last_accessed=datetime.fromisoformat(session_record["last_accessed"]),
                            expires_at=expires_at,
                            ip_address=session_record.get("ip_address"),
                            user_agent=session_record.get("user_agent"),
                            is_active=session_record.get("is_active", True),
                            metadata=session_record.get("metadata", {})
                        ))
            
            return session_list
        except Exception as e:
            logger.error(f"Error getting sessions for user {user_id}: {e}")
            return []
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        try:
            db_service = await get_db_service()
            all_sessions = await db_service.get_all_records("sessions")
            
            deleted_count = 0
            now = datetime.utcnow()
            
            for session in all_sessions:
                expires_at = datetime.fromisoformat(session["expires_at"])
                if now > expires_at:
                    if await self.delete_session(session["session_id"]):
                        deleted_count += 1
            
            logger.info(f"Cleaned up {deleted_count} expired sessions")
            return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")
            return 0
    
    async def _store_session(self, session_data: SessionData) -> None:
        """Store session in database"""
        session_record = {
            "session_id": session_data.session_id,
            "user_id": session_data.user_id,
            "username": session_data.username,
            "created_at": session_data.created_at.isoformat(),
            "last_accessed": session_data.last_accessed.isoformat(),
            "expires_at": session_data.expires_at.isoformat(),
            "ip_address": session_data.ip_address,
            "user_agent": session_data.user_agent,
            "is_active": session_data.is_active,
            "metadata": json.dumps(session_data.metadata) if session_data.metadata else "{}"
        }
        
        await insert_record("sessions", session_record)
    
    async def _update_last_accessed(self, session_id: str) -> None:
        """Update last accessed time for session"""
        await update_record("sessions", session_id, {
            "last_accessed": datetime.utcnow().isoformat()
        })
    
    async def _cleanup_user_sessions(self, user_id: str) -> None:
        """Clean up old sessions for a user if they exceed the limit"""
        try:
            sessions = await self.get_user_sessions(user_id)
            
            if len(sessions) > self.max_sessions_per_user:
                # Sort by last accessed and remove oldest
                sessions.sort(key=lambda x: x.last_accessed)
                sessions_to_remove = sessions[:-self.max_sessions_per_user]
                
                for session in sessions_to_remove:
                    await self.delete_session(session.session_id)
                
                logger.info(f"Cleaned up {len(sessions_to_remove)} old sessions for user {user_id}")
        except Exception as e:
            logger.error(f"Error cleaning up user sessions: {e}")

# Global session manager instance
session_manager = SessionManager()

# Convenience functions
async def create_session(
    user_id: str, 
    username: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    expires_hours: Optional[int] = None
) -> SessionData:
    """Create a new user session"""
    return await session_manager.create_session(
        user_id, username, ip_address, user_agent, metadata, expires_hours
    )

async def get_session(session_id: str) -> Optional[SessionData]:
    """Get session by ID"""
    return await session_manager.get_session(session_id)

async def delete_session(session_id: str) -> bool:
    """Delete a session"""
    return await session_manager.delete_session(session_id)