"""
Authentication service for Atulya Tantra Level 5 AGI System
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy.orm import Session
import secrets
import logging
import os

from ..core.database.schema import User, Session as UserSession
from ..core.database import get_db

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration (read from environment)
SECRET_KEY = os.getenv("JWT_SECRET", os.getenv("SECRET_KEY", "change-me"))
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_DAYS", "7"))

class AuthService:
    """Authentication and authorization service"""
    
    def __init__(self):
        self.pwd_context = pwd_context
        self.secret_key = SECRET_KEY
        self.algorithm = ALGORITHM
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password"""
        return self.pwd_context.hash(password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def generate_admin_token(self, subject: str = "admin", roles: Optional[list] = None, minutes: Optional[int] = None) -> str:
        """Generate an admin JWT for bootstrap scenarios (non-production)."""
        roles = roles or ["admin"]
        expires = timedelta(minutes=minutes or ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {"sub": subject, "roles": roles}
        return self.create_access_token(payload, expires)
    
    def create_refresh_token(self, data: dict) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            return None
    
    def authenticate_user(self, db: Session, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password"""
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        if not user.is_active:
            return None
        return user
    
    def create_user(self, db: Session, username: str, email: str, password: str) -> Optional[User]:
        """Create a new user"""
        # Check if user already exists
        if db.query(User).filter(User.username == username).first():
            return None
        if db.query(User).filter(User.email == email).first():
            return None
        
        # Create new user
        hashed_password = self.get_password_hash(password)
        user = User(
            username=username,
            email=email,
            password_hash=hashed_password,
            settings={
                "theme": "dark",
                "language": "en",
                "notifications": True,
                "voice_enabled": True
            }
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        logger.info(f"Created new user: {username}")
        return user
    
    def create_session(self, db: Session, user: User) -> str:
        """Create a new user session"""
        # Generate session token
        session_token = secrets.token_urlsafe(32)
        
        # Create session record
        session = UserSession(
            user_id=user.id,
            token=session_token,
            expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        )
        
        db.add(session)
        db.commit()
        
        return session_token
    
    def get_user_from_token(self, db: Session, token: str) -> Optional[User]:
        """Get user from JWT token"""
        payload = self.verify_token(token)
        if not payload:
            return None
        
        username = payload.get("sub")
        if not username:
            return None
        
        user = db.query(User).filter(User.username == username).first()
        return user

    def require_roles(self, payload: Dict[str, Any], required_roles: List[str]) -> bool:
        """Check if JWT payload has at least one required role"""
        roles = payload.get("roles", []) or []
        return any(role in roles for role in required_roles)
    
    def get_user_from_session(self, db: Session, session_token: str) -> Optional[User]:
        """Get user from session token"""
        session = db.query(UserSession).filter(
            UserSession.token == session_token,
            UserSession.expires_at > datetime.utcnow(),
            UserSession.is_active == True
        ).first()
        
        if not session:
            return None
        
        user = db.query(User).filter(User.id == session.user_id).first()
        return user
    
    def logout_user(self, db: Session, session_token: str) -> bool:
        """Logout user by deactivating session"""
        session = db.query(UserSession).filter(UserSession.token == session_token).first()
        if session:
            session.is_active = False
            db.commit()
            return True
        return False
    
    def logout_all_sessions(self, db: Session, user_id: int) -> int:
        """Logout user from all sessions"""
        sessions = db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True
        ).all()
        
        count = 0
        for session in sessions:
            session.is_active = False
            count += 1
        
        db.commit()
        return count
    
    def update_user_settings(self, db: Session, user_id: int, settings: Dict[str, Any]) -> bool:
        """Update user settings"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        # Merge with existing settings
        current_settings = user.settings or {}
        current_settings.update(settings)
        user.settings = current_settings
        user.updated_at = datetime.utcnow()
        
        db.commit()
        return True
    
    def change_password(self, db: Session, user_id: int, old_password: str, new_password: str) -> bool:
        """Change user password"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        if not self.verify_password(old_password, user.password_hash):
            return False
        
        user.password_hash = self.get_password_hash(new_password)
        user.updated_at = datetime.utcnow()
        
        db.commit()
        return True
    
    def reset_password(self, db: Session, email: str) -> Optional[str]:
        """Initiate password reset (returns reset token)"""
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None
        
        # Generate reset token
        reset_token = secrets.token_urlsafe(32)
        
        # Store reset token in user settings (in production, use a separate table)
        user.settings = user.settings or {}
        user.settings["password_reset_token"] = reset_token
        user.settings["password_reset_expires"] = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        
        db.commit()
        return reset_token
    
    def confirm_password_reset(self, db: Session, reset_token: str, new_password: str) -> bool:
        """Confirm password reset with token"""
        user = db.query(User).filter(
            User.settings["password_reset_token"].astext == reset_token
        ).first()
        
        if not user:
            return False
        
        # Check if token is expired
        reset_expires = user.settings.get("password_reset_expires")
        if reset_expires and datetime.fromisoformat(reset_expires) < datetime.utcnow():
            return False
        
        # Update password
        user.password_hash = self.get_password_hash(new_password)
        user.settings.pop("password_reset_token", None)
        user.settings.pop("password_reset_expires", None)
        user.updated_at = datetime.utcnow()
        
        db.commit()
        return True

# Global auth service instance
auth_service = AuthService()
