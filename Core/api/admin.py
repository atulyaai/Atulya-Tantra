"""
Admin Management API for Atulya Tantra AGI
Administrative operations, user management, and system administration
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime

from ..auth.jwt import verify_token, TokenData
from ..auth.rbac import require_permission, Permission, Role
from ..auth.password import hash_password, validate_password_strength
from ..config.logging import get_logger
from ..config.exceptions import AdminError, ValidationError

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


class UserCreate(BaseModel):
    """User creation model"""
    username: str
    email: str
    password: str
    roles: List[str] = ["user"]
    metadata: Dict[str, Any] = {}


class UserUpdate(BaseModel):
    """User update model"""
    username: Optional[str] = None
    email: Optional[str] = None
    roles: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class UserResponse(BaseModel):
    """User response model"""
    user_id: str
    username: str
    email: str
    roles: List[str]
    created_at: str
    last_login: Optional[str] = None
    is_active: bool
    metadata: Dict[str, Any] = {}


class SystemStats(BaseModel):
    """System statistics model"""
    total_users: int
    active_users: int
    total_conversations: int
    total_messages: int
    system_uptime: str
    memory_usage: Dict[str, Any]
    disk_usage: Dict[str, Any]
    cpu_usage: float


def get_current_user(token: str = Depends(verify_token)) -> TokenData:
    """Get current user from token"""
    return token


def require_admin(current_user: TokenData = Depends(get_current_user)):
    """Require admin role"""
    if not current_user.roles or "admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Admin permission required")
    return current_user


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    limit: int = 10,
    offset: int = 0,
    admin_user: TokenData = Depends(require_admin)
):
    """List all users"""
    try:
        # In a real implementation, this would query the database
        # For now, return mock data
        users = [
            {
                "user_id": "user1",
                "username": "admin",
                "email": "admin@example.com",
                "roles": ["admin"],
                "created_at": "2024-01-01T00:00:00Z",
                "last_login": "2024-01-15T10:30:00Z",
                "is_active": True,
                "metadata": {}
            }
        ]
        
        user_responses = []
        for user in users:
            user_responses.append(UserResponse(**user))
        
        return user_responses
        
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(status_code=500, detail="Failed to list users")


@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    admin_user: TokenData = Depends(require_admin)
):
    """Create new user"""
    try:
        # Validate password strength
        password_validation = validate_password_strength(user_data.password)
        if not password_validation.is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Password validation failed: {', '.join(password_validation.issues)}"
            )
        
        # Hash password
        hashed_password = hash_password(user_data.password)
        
        # Create user (mock implementation)
        user_id = f"user_{len(admin_user.roles)}"  # Mock user ID
        
        user_response = UserResponse(
            user_id=user_id,
            username=user_data.username,
            email=user_data.email,
            roles=user_data.roles,
            created_at=datetime.utcnow().isoformat(),
            is_active=True,
            metadata=user_data.metadata
        )
        
        logger.info(f"User created: {user_data.username}")
        return user_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail="Failed to create user")


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    admin_user: TokenData = Depends(require_admin)
):
    """Get user details"""
    try:
        # Mock implementation
        if user_id == "user1":
            return UserResponse(
                user_id="user1",
                username="admin",
                email="admin@example.com",
                roles=["admin"],
                created_at="2024-01-01T00:00:00Z",
                last_login="2024-01-15T10:30:00Z",
                is_active=True,
                metadata={}
            )
        else:
            raise HTTPException(status_code=404, detail="User not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user")


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    admin_user: TokenData = Depends(require_admin)
):
    """Update user"""
    try:
        # Mock implementation
        if user_id == "user1":
            updated_user = UserResponse(
                user_id="user1",
                username=user_data.username or "admin",
                email=user_data.email or "admin@example.com",
                roles=user_data.roles or ["admin"],
                created_at="2024-01-01T00:00:00Z",
                last_login="2024-01-15T10:30:00Z",
                is_active=True,
                metadata=user_data.metadata or {}
            )
            return updated_user
        else:
            raise HTTPException(status_code=404, detail="User not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user")


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin_user: TokenData = Depends(require_admin)
):
    """Delete user"""
    try:
        # Mock implementation
        if user_id == "user1":
            return {"message": "User deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="User not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete user")


@router.post("/users/{user_id}/roles")
async def assign_role(
    user_id: str,
    role: str,
    admin_user: TokenData = Depends(require_admin)
):
    """Assign role to user"""
    try:
        # Validate role
        try:
            Role(role)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid role")
        
        # Mock implementation
        return {"message": f"Role {role} assigned to user {user_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning role: {e}")
        raise HTTPException(status_code=500, detail="Failed to assign role")


@router.delete("/users/{user_id}/roles/{role}")
async def revoke_role(
    user_id: str,
    role: str,
    admin_user: TokenData = Depends(require_admin)
):
    """Revoke role from user"""
    try:
        # Validate role
        try:
            Role(role)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid role")
        
        # Mock implementation
        return {"message": f"Role {role} revoked from user {user_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking role: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke role")


@router.get("/stats", response_model=SystemStats)
async def get_system_stats(admin_user: TokenData = Depends(require_admin)):
    """Get system statistics"""
    try:
        # Mock implementation
        stats = SystemStats(
            total_users=100,
            active_users=50,
            total_conversations=1000,
            total_messages=5000,
            system_uptime="7 days, 12 hours",
            memory_usage={"used": "2.5GB", "total": "8GB", "percentage": 31.25},
            disk_usage={"used": "50GB", "total": "100GB", "percentage": 50.0},
            cpu_usage=25.5
        )
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system stats")


@router.get("/logs")
async def get_admin_logs(
    level: Optional[str] = None,
    limit: int = 100,
    admin_user: TokenData = Depends(require_admin)
):
    """Get admin logs"""
    try:
        # Mock implementation
        logs = [
            {
                "timestamp": "2024-01-15T10:30:00Z",
                "level": "INFO",
                "message": "User admin logged in",
                "component": "auth"
            },
            {
                "timestamp": "2024-01-15T10:25:00Z",
                "level": "WARNING",
                "message": "High memory usage detected",
                "component": "monitor"
            }
        ]
        
        return {"logs": logs}
        
    except Exception as e:
        logger.error(f"Error getting admin logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to get admin logs")


@router.post("/backup")
async def create_backup(
    background_tasks: BackgroundTasks,
    admin_user: TokenData = Depends(require_admin)
):
    """Create system backup"""
    try:
        # Mock implementation
        backup_id = f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # Schedule backup in background
        background_tasks.add_task(create_backup_task, backup_id)
        
        return {"message": "Backup started", "backup_id": backup_id}
        
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        raise HTTPException(status_code=500, detail="Failed to create backup")


@router.get("/backups")
async def list_backups(admin_user: TokenData = Depends(require_admin)):
    """List system backups"""
    try:
        # Mock implementation
        backups = [
            {
                "backup_id": "backup_20240115_103000",
                "created_at": "2024-01-15T10:30:00Z",
                "size": "2.5GB",
                "status": "completed"
            }
        ]
        
        return {"backups": backups}
        
    except Exception as e:
        logger.error(f"Error listing backups: {e}")
        raise HTTPException(status_code=500, detail="Failed to list backups")


@router.post("/restore/{backup_id}")
async def restore_backup(
    backup_id: str,
    background_tasks: BackgroundTasks,
    admin_user: TokenData = Depends(require_admin)
):
    """Restore system from backup"""
    try:
        # Mock implementation
        background_tasks.add_task(restore_backup_task, backup_id)
        
        return {"message": f"Restore from backup {backup_id} started"}
        
    except Exception as e:
        logger.error(f"Error restoring backup: {e}")
        raise HTTPException(status_code=500, detail="Failed to restore backup")


async def create_backup_task(backup_id: str):
    """Background task to create backup"""
    logger.info(f"Creating backup: {backup_id}")
    # Mock backup creation
    await asyncio.sleep(5)  # Simulate backup time
    logger.info(f"Backup created: {backup_id}")


async def restore_backup_task(backup_id: str):
    """Background task to restore backup"""
    logger.info(f"Restoring from backup: {backup_id}")
    # Mock restore process
    await asyncio.sleep(10)  # Simulate restore time
    logger.info(f"Restore completed: {backup_id}")