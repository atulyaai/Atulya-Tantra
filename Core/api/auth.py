"""
Authentication API endpoints for Atulya Tantra AGI
Handles user authentication, registration, and session management
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from ..auth import (
    create_access_token, create_refresh_token, verify_token,
    hash_password, verify_password, validate_password_strength,
    get_user_permissions, require_permission, require_role,
    create_session, get_session, update_session, delete_session
)
from ..config.logging import get_logger
from ..config.exceptions import ValidationError, AuthenticationError

logger = get_logger(__name__)

# Create router
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

# Security scheme
security = HTTPBearer()

# Request/Response models
class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class UserProfile(BaseModel):
    username: str
    email: str
    full_name: Optional[str]
    roles: list
    permissions: list
    created_at: str
    last_login: Optional[str]

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class PasswordReset(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

# Dependency to get current user
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user"""
    try:
        token = credentials.credentials
        payload = verify_token(token)
        
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return payload
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

@auth_router.post("/register", response_model=Dict[str, Any])
async def register_user(user_data: UserRegister):
    """Register a new user"""
    try:
        # Validate password strength
        password_validation = validate_password_strength(user_data.password)
        if not password_validation.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password does not meet requirements: {password_validation.message}"
            )
        
        # Hash password
        hashed_password = hash_password(user_data.password)
        
        # Create user (mock implementation)
        user_id = f"user_{datetime.now().timestamp()}"
        user = {
            "id": user_id,
            "username": user_data.username,
            "email": user_data.email,
            "password_hash": hashed_password,
            "full_name": user_data.full_name,
            "roles": ["user"],
            "created_at": datetime.now().isoformat(),
            "is_active": True
        }
        
        # Create session
        session_id = await create_session(
            user_id=user_id,
            user_data=user,
            expires_in=timedelta(hours=24)
        )
        
        # Generate tokens
        access_token = create_access_token(
            data={"sub": user_id, "username": user_data.username}
        )
        refresh_token = create_refresh_token(
            data={"sub": user_id, "username": user_data.username}
        )
        
        logger.info(f"User registered: {user_data.username}")
        
        return {
            "message": "User registered successfully",
            "user_id": user_id,
            "session_id": session_id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@auth_router.post("/login", response_model=TokenResponse)
async def login_user(login_data: UserLogin):
    """Authenticate user and return tokens"""
    try:
        # Mock user lookup (in real implementation, query database)
        user = {
            "id": "user_123",
            "username": login_data.username,
            "password_hash": "$2b$12$example_hash",  # Mock hash
            "email": "user@example.com",
            "roles": ["user"],
            "is_active": True
        }
        
        # Verify password
        if not verify_password(login_data.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Create session
        session_id = await create_session(
            user_id=user["id"],
            user_data=user,
            expires_in=timedelta(hours=24)
        )
        
        # Generate tokens
        access_token = create_access_token(
            data={"sub": user["id"], "username": user["username"]}
        )
        refresh_token = create_refresh_token(
            data={"sub": user["id"], "username": user["username"]}
        )
        
        logger.info(f"User logged in: {login_data.username}")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=3600  # 1 hour
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str):
    """Refresh access token using refresh token"""
    try:
        # Verify refresh token
        payload = verify_token(refresh_token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Generate new access token
        access_token = create_access_token(
            data={"sub": payload["sub"], "username": payload["username"]}
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,  # Keep same refresh token
            expires_in=3600
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )

@auth_router.get("/me", response_model=UserProfile)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """Get current user profile"""
    try:
        user_id = current_user["sub"]
        
        # Mock user data (in real implementation, query database)
        user = {
            "username": current_user["username"],
            "email": "user@example.com",
            "full_name": "John Doe",
            "roles": ["user"],
            "created_at": "2024-01-01T00:00:00Z",
            "last_login": datetime.now().isoformat()
        }
        
        # Get user permissions
        permissions = get_user_permissions(user_id)
        
        return UserProfile(
            username=user["username"],
            email=user["email"],
            full_name=user["full_name"],
            roles=user["roles"],
            permissions=permissions,
            created_at=user["created_at"],
            last_login=user["last_login"]
        )
        
    except Exception as e:
        logger.error(f"Profile retrieval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user profile"
        )

@auth_router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: dict = Depends(get_current_user)
):
    """Change user password"""
    try:
        user_id = current_user["sub"]
        
        # Mock password verification (in real implementation, verify current password)
        if not verify_password(password_data.current_password, "mock_hash"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Validate new password strength
        password_validation = validate_password_strength(password_data.new_password)
        if not password_validation.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"New password does not meet requirements: {password_validation.message}"
            )
        
        # Hash new password
        new_password_hash = hash_password(password_data.new_password)
        
        # Update password (mock implementation)
        logger.info(f"Password changed for user: {user_id}")
        
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )

@auth_router.post("/logout")
async def logout_user(current_user: dict = Depends(get_current_user)):
    """Logout user and invalidate session"""
    try:
        user_id = current_user["sub"]
        
        # Delete session
        await delete_session(user_id)
        
        logger.info(f"User logged out: {user_id}")
        
        return {"message": "Logged out successfully"}
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )

@auth_router.post("/forgot-password")
async def forgot_password(reset_data: PasswordReset):
    """Request password reset"""
    try:
        # Mock password reset request
        logger.info(f"Password reset requested for: {reset_data.email}")
        
        return {"message": "Password reset instructions sent to your email"}
        
    except Exception as e:
        logger.error(f"Password reset request error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset request failed"
        )

@auth_router.post("/reset-password")
async def reset_password(reset_data: PasswordResetConfirm):
    """Reset password with token"""
    try:
        # Verify reset token
        payload = verify_token(reset_data.token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
        
        # Validate new password strength
        password_validation = validate_password_strength(reset_data.new_password)
        if not password_validation.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"New password does not meet requirements: {password_validation.message}"
            )
        
        # Hash new password
        new_password_hash = hash_password(reset_data.new_password)
        
        # Update password (mock implementation)
        logger.info(f"Password reset completed for user: {payload['sub']}")
        
        return {"message": "Password reset successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset failed"
        )

@auth_router.get("/sessions")
async def get_user_sessions(current_user: dict = Depends(get_current_user)):
    """Get user's active sessions"""
    try:
        user_id = current_user["sub"]
        
        # Get user sessions (mock implementation)
        sessions = [
            {
                "session_id": "session_123",
                "created_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0..."
            }
        ]
        
        return {"sessions": sessions}
        
    except Exception as e:
        logger.error(f"Session retrieval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sessions"
        )

@auth_router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Revoke a specific session"""
    try:
        user_id = current_user["sub"]
        
        # Delete session
        await delete_session(session_id)
        
        logger.info(f"Session revoked: {session_id}")
        
        return {"message": "Session revoked successfully"}
        
    except Exception as e:
        logger.error(f"Session revocation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke session"
        )

@auth_router.get("/permissions")
async def get_user_permissions_endpoint(current_user: dict = Depends(get_current_user)):
    """Get user permissions"""
    try:
        user_id = current_user["sub"]
        permissions = get_user_permissions(user_id)
        
        return {"permissions": permissions}
        
    except Exception as e:
        logger.error(f"Permission retrieval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve permissions"
        )

# Export router
__all__ = ["auth_router"]