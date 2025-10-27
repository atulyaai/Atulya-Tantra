"""
JWT Token Management for Atulya Tantra AGI
Access tokens, refresh tokens, and token validation
"""

import jwt
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union
from enum import Enum

from ..config.settings import settings
from ..config.logging import get_logger
from ..config.exceptions import AuthenticationError, TokenExpiredError, InvalidTokenError

logger = get_logger(__name__)


class TokenType(str, Enum):
    """Token types"""
    ACCESS = "access"
    REFRESH = "refresh"


class TokenData:
    """Token payload data"""
    
    def __init__(
        self,
        user_id: str,
        username: str,
        roles: list = None,
        permissions: list = None,
        token_type: TokenType = TokenType.ACCESS,
        issued_at: datetime = None,
        expires_at: datetime = None,
        jti: str = None
    ):
        self.user_id = user_id
        self.username = username
        self.roles = roles or []
        self.permissions = permissions or []
        self.token_type = token_type
        self.issued_at = issued_at or datetime.utcnow()
        self.expires_at = expires_at
        self.jti = jti or secrets.token_urlsafe(32)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JWT payload"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "roles": self.roles,
            "permissions": self.permissions,
            "token_type": self.token_type.value,
            "iat": int(self.issued_at.timestamp()),
            "exp": int(self.expires_at.timestamp()) if self.expires_at else None,
            "jti": self.jti
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TokenData':
        """Create from dictionary"""
        return cls(
            user_id=data.get("user_id"),
            username=data.get("username"),
            roles=data.get("roles", []),
            permissions=data.get("permissions", []),
            token_type=TokenType(data.get("token_type", TokenType.ACCESS.value)),
            issued_at=datetime.fromtimestamp(data.get("iat", 0)) if data.get("iat") else None,
            expires_at=datetime.fromtimestamp(data.get("exp", 0)) if data.get("exp") else None,
            jti=data.get("jti")
        )


class JWTManager:
    """JWT token management"""
    
    def __init__(self):
        self.secret_key = settings.JWT_SECRET
        self.algorithm = "HS256"
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = settings.REFRESH_TOKEN_EXPIRE_DAYS
    
    def create_access_token(
        self,
        user_id: str,
        username: str,
        roles: list = None,
        permissions: list = None,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create access token"""
        try:
            if expires_delta:
                expire = datetime.utcnow() + expires_delta
            else:
                expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
            
            token_data = TokenData(
                user_id=user_id,
                username=username,
                roles=roles or [],
                permissions=permissions or [],
                token_type=TokenType.ACCESS,
                expires_at=expire
            )
            
            payload = token_data.to_dict()
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            
            logger.info(f"Access token created for user {user_id}")
            return token
            
        except Exception as e:
            logger.error(f"Error creating access token: {e}")
            raise AuthenticationError("Failed to create access token")
    
    def create_refresh_token(
        self,
        user_id: str,
        username: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create refresh token"""
        try:
            if expires_delta:
                expire = datetime.utcnow() + expires_delta
            else:
                expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
            
            token_data = TokenData(
                user_id=user_id,
                username=username,
                token_type=TokenType.REFRESH,
                expires_at=expire
            )
            
            payload = token_data.to_dict()
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            
            logger.info(f"Refresh token created for user {user_id}")
            return token
            
        except Exception as e:
            logger.error(f"Error creating refresh token: {e}")
            raise AuthenticationError("Failed to create refresh token")
    
    def verify_token(self, token: str, token_type: TokenType = TokenType.ACCESS) -> TokenData:
        """Verify and decode token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check token type
            if payload.get("token_type") != token_type.value:
                raise InvalidTokenError("Invalid token type")
            
            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.utcnow() > datetime.fromtimestamp(exp):
                raise TokenExpiredError("Token has expired")
            
            token_data = TokenData.from_dict(payload)
            
            logger.debug(f"Token verified for user {token_data.user_id}")
            return token_data
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise TokenExpiredError("Token has expired")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise InvalidTokenError("Invalid token")
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            raise AuthenticationError("Failed to verify token")
    
    def decode_token(self, token: str) -> Dict[str, Any]:
        """Decode token without verification (for debugging)"""
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            return payload
        except Exception as e:
            logger.error(f"Error decoding token: {e}")
            raise InvalidTokenError("Failed to decode token")
    
    def get_token_payload(self, token: str) -> Dict[str, Any]:
        """Get token payload without verification"""
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            return payload
        except Exception as e:
            logger.error(f"Error getting token payload: {e}")
            raise InvalidTokenError("Failed to get token payload")
    
    def is_token_expired(self, token: str) -> bool:
        """Check if token is expired"""
        try:
            payload = self.get_token_payload(token)
            exp = payload.get("exp")
            if exp:
                return datetime.utcnow() > datetime.fromtimestamp(exp)
            return True
        except Exception:
            return True
    
    def get_token_expiry(self, token: str) -> Optional[datetime]:
        """Get token expiry time"""
        try:
            payload = self.get_token_payload(token)
            exp = payload.get("exp")
            if exp:
                return datetime.fromtimestamp(exp)
            return None
        except Exception:
            return None


# Global JWT manager instance
_jwt_manager = None


def get_jwt_manager() -> JWTManager:
    """Get global JWT manager instance"""
    global _jwt_manager
    if _jwt_manager is None:
        _jwt_manager = JWTManager()
    return _jwt_manager


# Convenience functions
def create_access_token(
    user_id: str,
    username: str,
    roles: list = None,
    permissions: list = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create access token"""
    manager = get_jwt_manager()
    return manager.create_access_token(user_id, username, roles, permissions, expires_delta)


def create_refresh_token(
    user_id: str,
    username: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create refresh token"""
    manager = get_jwt_manager()
    return manager.create_refresh_token(user_id, username, expires_delta)


def verify_token(token: str, token_type: TokenType = TokenType.ACCESS) -> TokenData:
    """Verify token"""
    manager = get_jwt_manager()
    return manager.verify_token(token, token_type)


def decode_token(token: str) -> Dict[str, Any]:
    """Decode token"""
    manager = get_jwt_manager()
    return manager.decode_token(token)


def get_token_payload(token: str) -> Dict[str, Any]:
    """Get token payload"""
    manager = get_jwt_manager()
    return manager.get_token_payload(token)


# Export public API
__all__ = [
    "TokenType",
    "TokenData",
    "JWTManager",
    "get_jwt_manager",
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "decode_token",
    "get_token_payload"
]