"""
Role-Based Access Control (RBAC) system
Handles user roles, permissions, and authorization
"""

from enum import Enum
from typing import Dict, List, Set, Optional, Any
from functools import wraps
from fastapi import HTTPException, Depends, status

from ..config.logging import get_logger
from .jwt import get_current_user

logger = get_logger(__name__)

class Role(str, Enum):
    """User roles"""
    ADMIN = "admin"
    USER = "user"
    AGENT = "agent"
    GUEST = "guest"

class Permission(str, Enum):
    """System permissions"""
    # Chat permissions
    CHAT_READ = "chat:read"
    CHAT_WRITE = "chat:write"
    CHAT_DELETE = "chat:delete"
    
    # Agent permissions
    AGENT_EXECUTE = "agent:execute"
    AGENT_MANAGE = "agent:manage"
    
    # System permissions
    SYSTEM_READ = "system:read"
    SYSTEM_MANAGE = "system:manage"
    SYSTEM_ADMIN = "system:admin"
    
    # User management
    USER_READ = "user:read"
    USER_MANAGE = "user:manage"
    USER_DELETE = "user:delete"
    
    # Memory permissions
    MEMORY_READ = "memory:read"
    MEMORY_WRITE = "memory:write"
    MEMORY_DELETE = "memory:delete"
    
    # File permissions
    FILE_UPLOAD = "file:upload"
    FILE_DOWNLOAD = "file:download"
    FILE_DELETE = "file:delete"

# Role-Permission mapping
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: {
        Permission.CHAT_READ, Permission.CHAT_WRITE, Permission.CHAT_DELETE,
        Permission.AGENT_EXECUTE, Permission.AGENT_MANAGE,
        Permission.SYSTEM_READ, Permission.SYSTEM_MANAGE, Permission.SYSTEM_ADMIN,
        Permission.USER_READ, Permission.USER_MANAGE, Permission.USER_DELETE,
        Permission.MEMORY_READ, Permission.MEMORY_WRITE, Permission.MEMORY_DELETE,
        Permission.FILE_UPLOAD, Permission.FILE_DOWNLOAD, Permission.FILE_DELETE
    },
    Role.USER: {
        Permission.CHAT_READ, Permission.CHAT_WRITE,
        Permission.AGENT_EXECUTE,
        Permission.SYSTEM_READ,
        Permission.MEMORY_READ, Permission.MEMORY_WRITE,
        Permission.FILE_UPLOAD, Permission.FILE_DOWNLOAD
    },
    Role.AGENT: {
        Permission.CHAT_READ, Permission.CHAT_WRITE,
        Permission.AGENT_EXECUTE,
        Permission.SYSTEM_READ,
        Permission.MEMORY_READ, Permission.MEMORY_WRITE,
        Permission.FILE_UPLOAD, Permission.FILE_DOWNLOAD
    },
    Role.GUEST: {
        Permission.CHAT_READ,
        Permission.SYSTEM_READ
    }
}

class RBACManager:
    """Manages role-based access control"""
    
    def __init__(self):
        self.role_permissions = ROLE_PERMISSIONS.copy()
        self.custom_permissions: Dict[str, Set[Permission]] = {}
    
    def get_user_permissions(self, user: Dict[str, Any]) -> Set[Permission]:
        """Get all permissions for a user"""
        user_role = Role(user.get("role", "user"))
        permissions = self.role_permissions.get(user_role, set())
        
        # Add custom permissions if any
        user_id = user.get("user_id")
        if user_id and user_id in self.custom_permissions:
            permissions.update(self.custom_permissions[user_id])
        
        return permissions
    
    def has_permission(self, user: Dict[str, Any], permission: Permission) -> bool:
        """Check if user has a specific permission"""
        user_permissions = self.get_user_permissions(user)
        return permission in user_permissions
    
    def has_role(self, user: Dict[str, Any], role: Role) -> bool:
        """Check if user has a specific role"""
        user_role = user.get("role", "user")
        return Role(user_role) == role
    
    def has_any_role(self, user: Dict[str, Any], roles: List[Role]) -> bool:
        """Check if user has any of the specified roles"""
        user_role = user.get("role", "user")
        return Role(user_role) in roles
    
    def add_custom_permission(self, user_id: str, permission: Permission) -> None:
        """Add custom permission to a user"""
        if user_id not in self.custom_permissions:
            self.custom_permissions[user_id] = set()
        self.custom_permissions[user_id].add(permission)
        logger.info(f"Added custom permission {permission} to user {user_id}")
    
    def remove_custom_permission(self, user_id: str, permission: Permission) -> None:
        """Remove custom permission from a user"""
        if user_id in self.custom_permissions:
            self.custom_permissions[user_id].discard(permission)
            if not self.custom_permissions[user_id]:
                del self.custom_permissions[user_id]
            logger.info(f"Removed custom permission {permission} from user {user_id}")
    
    def get_role_hierarchy(self, role: Role) -> List[Role]:
        """Get role hierarchy (roles that this role can manage)"""
        hierarchy = {
            Role.ADMIN: [Role.ADMIN, Role.USER, Role.AGENT, Role.GUEST],
            Role.USER: [Role.USER, Role.GUEST],
            Role.AGENT: [Role.AGENT],
            Role.GUEST: [Role.GUEST]
        }
        return hierarchy.get(role, [])
    
    def can_manage_user(self, manager: Dict[str, Any], target_user: Dict[str, Any]) -> bool:
        """Check if manager can manage target user"""
        manager_role = Role(manager.get("role", "user"))
        target_role = Role(target_user.get("role", "user"))
        
        manageable_roles = self.get_role_hierarchy(manager_role)
        return target_role in manageable_roles

# Global RBAC manager instance
rbac_manager = RBACManager()

# Authorization decorators
def require_auth(func):
    """Require authentication"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # This will be handled by FastAPI dependency injection
        return await func(*args, **kwargs)
    return wrapper

def require_role(required_role: Role):
    """Require specific role"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user: Dict[str, Any] = Depends(get_current_user), **kwargs):
            if not rbac_manager.has_role(current_user, required_role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role {required_role.value} required"
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator

def require_permission(required_permission: Permission):
    """Require specific permission"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user: Dict[str, Any] = Depends(get_current_user), **kwargs):
            if not rbac_manager.has_permission(current_user, required_permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission {required_permission.value} required"
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator

def require_any_role(required_roles: List[Role]):
    """Require any of the specified roles"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user: Dict[str, Any] = Depends(get_current_user), **kwargs):
            if not rbac_manager.has_any_role(current_user, required_roles):
                role_names = [role.value for role in required_roles]
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"One of these roles required: {', '.join(role_names)}"
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator

# Dependency functions
async def get_current_user_role(current_user: Dict[str, Any] = Depends(get_current_user)) -> Role:
    """Get current user's role"""
    return Role(current_user.get("role", "user"))

async def get_current_user_permissions(current_user: Dict[str, Any] = Depends(get_current_user)) -> Set[Permission]:
    """Get current user's permissions"""
    return rbac_manager.get_user_permissions(current_user)

# Utility functions
def check_permission(user: Dict[str, Any], permission: Permission) -> bool:
    """Check if user has permission"""
    return rbac_manager.has_permission(user, permission)

def check_role(user: Dict[str, Any], role: Role) -> bool:
    """Check if user has role"""
    return rbac_manager.has_role(user, role)

def get_available_permissions() -> List[Permission]:
    """Get all available permissions"""
    return list(Permission)

def get_available_roles() -> List[Role]:
    """Get all available roles"""
    return list(Role)

def get_role_permissions(role: Role) -> Set[Permission]:
    """Get permissions for a role"""
    return ROLE_PERMISSIONS.get(role, set())