"""
Session Management for Atulya Tantra AGI
User sessions, session data, and session lifecycle
"""

import json
import secrets
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

from ..config.logging import get_logger
from ..config.exceptions import SessionError, ValidationError

logger = get_logger(__name__)


@dataclass
class SessionData:
    """Session data structure"""
    session_id: str
    user_id: str
    created_at: datetime
    last_accessed: datetime
    expires_at: datetime
    ip_address: str
    user_agent: str
    data: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "data": self.data or {}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionData':
        """Create from dictionary"""
        return cls(
            session_id=data["session_id"],
            user_id=data["user_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            ip_address=data["ip_address"],
            user_agent=data["user_agent"],
            data=data.get("data", {})
        )


class SessionManager:
    """Session management utilities"""
    
    def __init__(self):
        self.sessions: Dict[str, SessionData] = {}
        self.default_session_duration = timedelta(hours=24)
        self.max_sessions_per_user = 5
    
    def create_session(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        duration: Optional[timedelta] = None
    ) -> str:
        """Create new session"""
        try:
            # Generate session ID
            session_id = secrets.token_urlsafe(32)
            
            # Set expiration
            expires_at = datetime.utcnow() + (duration or self.default_session_duration)
            
            # Create session data
            session_data = SessionData(
                session_id=session_id,
                user_id=user_id,
                created_at=datetime.utcnow(),
                last_accessed=datetime.utcnow(),
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=user_agent,
                data={}
            )
            
            # Store session
            self.sessions[session_id] = session_data
            
            # Clean up old sessions for user
            self._cleanup_user_sessions(user_id)
            
            logger.info(f"Session created for user {user_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise SessionError("Failed to create session")
    
    def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session by ID"""
        try:
            if session_id not in self.sessions:
                return None
            
            session = self.sessions[session_id]
            
            # Check if session is expired
            if datetime.utcnow() > session.expires_at:
                del self.sessions[session_id]
                return None
            
            # Update last accessed
            session.last_accessed = datetime.utcnow()
            
            return session
            
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return None
    
    def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Update session data"""
        try:
            if session_id not in self.sessions:
                return False
            
            session = self.sessions[session_id]
            
            # Check if session is expired
            if datetime.utcnow() > session.expires_at:
                del self.sessions[session_id]
                return False
            
            # Update data
            if session.data is None:
                session.data = {}
            session.data.update(data)
            session.last_accessed = datetime.utcnow()
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating session: {e}")
            return False
    
    def delete_session(self, session_id: str) -> bool:
        """Delete session"""
        try:
            if session_id in self.sessions:
                del self.sessions[session_id]
                logger.info(f"Session {session_id} deleted")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False
    
    def delete_user_sessions(self, user_id: str) -> int:
        """Delete all sessions for user"""
        try:
            deleted_count = 0
            sessions_to_delete = []
            
            for session_id, session in self.sessions.items():
                if session.user_id == user_id:
                    sessions_to_delete.append(session_id)
            
            for session_id in sessions_to_delete:
                del self.sessions[session_id]
                deleted_count += 1
            
            logger.info(f"Deleted {deleted_count} sessions for user {user_id}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error deleting user sessions: {e}")
            return 0
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        try:
            current_time = datetime.utcnow()
            expired_sessions = []
            
            for session_id, session in self.sessions.items():
                if current_time > session.expires_at:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self.sessions[session_id]
            
            if expired_sessions:
                logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
            
            return len(expired_sessions)
            
        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")
            return 0
    
    def _cleanup_user_sessions(self, user_id: str):
        """Clean up old sessions for user"""
        try:
            user_sessions = [
                (session_id, session) for session_id, session in self.sessions.items()
                if session.user_id == user_id
            ]
            
            if len(user_sessions) > self.max_sessions_per_user:
                # Sort by last accessed and keep only the most recent
                user_sessions.sort(key=lambda x: x[1].last_accessed, reverse=True)
                
                sessions_to_delete = user_sessions[self.max_sessions_per_user:]
                for session_id, _ in sessions_to_delete:
                    del self.sessions[session_id]
                
                logger.info(f"Cleaned up {len(sessions_to_delete)} old sessions for user {user_id}")
                
        except Exception as e:
            logger.error(f"Error cleaning up user sessions: {e}")
    
    def get_user_sessions(self, user_id: str) -> List[SessionData]:
        """Get all sessions for user"""
        try:
            return [
                session for session in self.sessions.values()
                if session.user_id == user_id and datetime.utcnow() <= session.expires_at
            ]
        except Exception as e:
            logger.error(f"Error getting user sessions: {e}")
            return []
    
    def extend_session(self, session_id: str, duration: timedelta) -> bool:
        """Extend session duration"""
        try:
            if session_id not in self.sessions:
                return False
            
            session = self.sessions[session_id]
            
            # Check if session is expired
            if datetime.utcnow() > session.expires_at:
                del self.sessions[session_id]
                return False
            
            # Extend expiration
            session.expires_at = datetime.utcnow() + duration
            session.last_accessed = datetime.utcnow()
            
            return True
            
        except Exception as e:
            logger.error(f"Error extending session: {e}")
            return False
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics"""
        try:
            current_time = datetime.utcnow()
            active_sessions = len([
                session for session in self.sessions.values()
                if current_time <= session.expires_at
            ])
            
            expired_sessions = len([
                session for session in self.sessions.values()
                if current_time > session.expires_at
            ])
            
            return {
                "total_sessions": len(self.sessions),
                "active_sessions": active_sessions,
                "expired_sessions": expired_sessions,
                "max_sessions_per_user": self.max_sessions_per_user
            }
            
        except Exception as e:
            logger.error(f"Error getting session stats: {e}")
            return {}


# Global session manager instance
_session_manager = None


def get_session_manager() -> SessionManager:
    """Get global session manager instance"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


# Convenience functions
def create_session(
    user_id: str,
    ip_address: str,
    user_agent: str,
    duration: Optional[timedelta] = None
) -> str:
    """Create new session"""
    manager = get_session_manager()
    return manager.create_session(user_id, ip_address, user_agent, duration)


def get_session(session_id: str) -> Optional[SessionData]:
    """Get session by ID"""
    manager = get_session_manager()
    return manager.get_session(session_id)


def update_session(session_id: str, data: Dict[str, Any]) -> bool:
    """Update session data"""
    manager = get_session_manager()
    return manager.update_session(session_id, data)


def delete_session(session_id: str) -> bool:
    """Delete session"""
    manager = get_session_manager()
    return manager.delete_session(session_id)


def cleanup_expired_sessions() -> int:
    """Clean up expired sessions"""
    manager = get_session_manager()
    return manager.cleanup_expired_sessions()


# Export public API
__all__ = [
    "SessionData",
    "SessionManager",
    "get_session_manager",
    "create_session",
    "get_session",
    "update_session",
    "delete_session",
    "cleanup_expired_sessions"
]