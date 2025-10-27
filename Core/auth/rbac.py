"""
Role-Based Access Control (RBAC) for Atulya Tantra AGI
Roles, permissions, and authorization management
"""

from typing import Dict, List, Set, Optional, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

from ..config.logging import get_logger
from ..config.exceptions import AuthorizationError, ValidationError

logger = get_logger(__name__)


class Role(str, Enum):
    """System roles"""
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
    CHAT_STREAM = "chat:stream"
    
    # Agent permissions
    AGENT_READ = "agent:read"
    AGENT_EXECUTE = "agent:execute"
    AGENT_MANAGE = "agent:manage"
    
    # Memory permissions
    MEMORY_READ = "memory:read"
    MEMORY_WRITE = "memory:write"
    MEMORY_DELETE = "memory:delete"
    MEMORY_SEARCH = "memory:search"
    
    # System permissions
    SYSTEM_READ = "system:read"
    SYSTEM_MANAGE = "system:manage"
    SYSTEM_MONITOR = "system:monitor"
    
    # Admin permissions
    ADMIN_READ = "admin:read"
    ADMIN_WRITE = "admin:write"
    ADMIN_DELETE = "admin:delete"
    ADMIN_MANAGE = "admin:manage"
    
    # User management
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    USER_MANAGE = "user:manage"


@dataclass
class UserRole:
    """User role assignment"""
    user_id: str
    role: Role
    assigned_at: datetime
    assigned_by: str
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = None


@dataclass
class RolePermission:
    """Role permission mapping"""
    role: Role
    permission: Permission
    granted: bool = True
    conditions: Dict[str, Any] = None


class RBACManager:
    """Role-Based Access Control Manager"""
    
    def __init__(self):
        self.role_permissions = self._initialize_role_permissions()
        self.user_roles: Dict[str, List[UserRole]] = {}
        self.permission_cache: Dict[str, Set[Permission]] = {}
    
    def _initialize_role_permissions(self) -> Dict[Role, Set[Permission]]:
        """Initialize default role permissions"""
        return {
            Role.ADMIN: {
                Permission.CHAT_READ, Permission.CHAT_WRITE, Permission.CHAT_DELETE, Permission.CHAT_STREAM,
                Permission.AGENT_READ, Permission.AGENT_EXECUTE, Permission.AGENT_MANAGE,
                Permission.MEMORY_READ, Permission.MEMORY_WRITE, Permission.MEMORY_DELETE, Permission.MEMORY_SEARCH,
                Permission.SYSTEM_READ, Permission.SYSTEM_MANAGE, Permission.SYSTEM_MONITOR,
                Permission.ADMIN_READ, Permission.ADMIN_WRITE, Permission.ADMIN_DELETE, Permission.ADMIN_MANAGE,
                Permission.USER_READ, Permission.USER_WRITE, Permission.USER_DELETE, Permission.USER_MANAGE
            },
            Role.USER: {
                Permission.CHAT_READ, Permission.CHAT_WRITE, Permission.CHAT_STREAM,
                Permission.AGENT_READ, Permission.AGENT_EXECUTE,
                Permission.MEMORY_READ, Permission.MEMORY_WRITE, Permission.MEMORY_SEARCH,
                Permission.SYSTEM_READ
            },
            Role.AGENT: {
                Permission.CHAT_READ, Permission.CHAT_WRITE,
                Permission.AGENT_READ, Permission.AGENT_EXECUTE,
                Permission.MEMORY_READ, Permission.MEMORY_WRITE, Permission.MEMORY_SEARCH,
                Permission.SYSTEM_READ, Permission.SYSTEM_MONITOR
            },
            Role.GUEST: {
                Permission.CHAT_READ,
                Permission.AGENT_READ,
                Permission.MEMORY_READ
            }
        }
    
    def assign_role(self, user_id: str, role: Role, assigned_by: str, expires_at: Optional[datetime] = None) -> bool:
        """Assign role to user"""
        try:
            if user_id not in self.user_roles:
                self.user_roles[user_id] = []
            
            # Check if role already assigned
            for user_role in self.user_roles[user_id]:
                if user_role.role == role and not user_role.expires_at:
                    logger.warning(f"Role {role} already assigned to user {user_id}")
                    return False
            
            # Assign role
            user_role = UserRole(
                user_id=user_id,
                role=role,
                assigned_at=datetime.utcnow(),
                assigned_by=assigned_by,
                expires_at=expires_at
            )
            
            self.user_roles[user_id].append(user_role)
            
            # Clear permission cache
            if user_id in self.permission_cache:
                del self.permission_cache[user_id]
            
            logger.info(f"Role {role} assigned to user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error assigning role: {e}")
            return False
    
    def revoke_role(self, user_id: str, role: Role) -> bool:
        """Revoke role from user"""
        try:
            if user_id not in self.user_roles:
                return False
            
            # Remove role
            self.user_roles[user_id] = [
                user_role for user_role in self.user_roles[user_id]
                if user_role.role != role
            ]
            
            # Clear permission cache
            if user_id in self.permission_cache:
                del self.permission_cache[user_id]
            
            logger.info(f"Role {role} revoked from user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error revoking role: {e}")
            return False
    
    def get_user_roles(self, user_id: str) -> List[Role]:
        """Get user roles"""
        try:
            if user_id not in self.user_roles:
                return []
            
            current_time = datetime.utcnow()
            active_roles = []
            
            for user_role in self.user_roles[user_id]:
                # Check if role is not expired
                if not user_role.expires_at or user_role.expires_at > current_time:
                    active_roles.append(user_role.role)
            
            return active_roles
            
        except Exception as e:
            logger.error(f"Error getting user roles: {e}")
            return []
    
    def get_user_permissions(self, user_id: str) -> Set[Permission]:
        """Get user permissions based on roles"""
        try:
            # Check cache first
            if user_id in self.permission_cache:
                return self.permission_cache[user_id]
            
            roles = self.get_user_roles(user_id)
            permissions = set()
            
            for role in roles:
                if role in self.role_permissions:
                    permissions.update(self.role_permissions[role])
            
            # Cache permissions
            self.permission_cache[user_id] = permissions
            
            return permissions
            
        except Exception as e:
            logger.error(f"Error getting user permissions: {e}")
            return set()
    
    def get_role_permissions(self, role: Role) -> Set[Permission]:
        """Get permissions for a role"""
        return self.role_permissions.get(role, set())
    
    def check_permission(self, user_id: str, permission: Permission) -> bool:
        """Check if user has permission"""
        try:
            user_permissions = self.get_user_permissions(user_id)
            return permission in user_permissions
            
        except Exception as e:
            logger.error(f"Error checking permission: {e}")
            return False
    
    def require_permission(self, permission: Permission):
        """Decorator to require permission"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                # Extract user_id from arguments (this is a simplified implementation)
                user_id = kwargs.get('user_id') or (args[0] if args else None)
                
                if not user_id:
                    raise AuthorizationError("User ID required for permission check")
                
                if not self.check_permission(user_id, permission):
                    raise AuthorizationError(f"Permission {permission} required")
                
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def require_role(self, role: Role):
        """Decorator to require role"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                # Extract user_id from arguments
                user_id = kwargs.get('user_id') or (args[0] if args else None)
                
                if not user_id:
                    raise AuthorizationError("User ID required for role check")
                
                user_roles = self.get_user_roles(user_id)
                if role not in user_roles:
                    raise AuthorizationError(f"Role {role} required")
                
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def add_permission_to_role(self, role: Role, permission: Permission) -> bool:
        """Add permission to role"""
        try:
            if role not in self.role_permissions:
                self.role_permissions[role] = set()
            
            self.role_permissions[role].add(permission)
            
            # Clear all permission caches
            self.permission_cache.clear()
            
            logger.info(f"Permission {permission} added to role {role}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding permission to role: {e}")
            return False
    
    def remove_permission_from_role(self, role: Role, permission: Permission) -> bool:
        """Remove permission from role"""
        try:
            if role in self.role_permissions:
                self.role_permissions[role].discard(permission)
                
                # Clear all permission caches
                self.permission_cache.clear()
                
                logger.info(f"Permission {permission} removed from role {role}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error removing permission from role: {e}")
            return False
    
    def create_custom_role(self, role_name: str, permissions: Set[Permission]) -> bool:
        """Create custom role"""
        try:
            # Convert string to Role enum
            role = Role(role_name)
            
            self.role_permissions[role] = permissions
            
            # Clear all permission caches
            self.permission_cache.clear()
            
            logger.info(f"Custom role {role_name} created with {len(permissions)} permissions")
            return True
            
        except ValueError:
            logger.error(f"Invalid role name: {role_name}")
            return False
        except Exception as e:
            logger.error(f"Error creating custom role: {e}")
            return False
    
    def get_user_role_info(self, user_id: str) -> List[Dict[str, Any]]:
        """Get detailed user role information"""
        try:
            if user_id not in self.user_roles:
                return []
            
            role_info = []
            for user_role in self.user_roles[user_id]:
                role_info.append({
                    "role": user_role.role.value,
                    "assigned_at": user_role.assigned_at.isoformat(),
                    "assigned_by": user_role.assigned_by,
                    "expires_at": user_role.expires_at.isoformat() if user_role.expires_at else None,
                    "permissions": list(self.get_role_permissions(user_role.role))
                })
            
            return role_info
            
        except Exception as e:
            logger.error(f"Error getting user role info: {e}")
            return []
    
    def cleanup_expired_roles(self) -> int:
        """Clean up expired roles"""
        try:
            current_time = datetime.utcnow()
            cleaned_count = 0
            
            for user_id, user_roles in self.user_roles.items():
                original_count = len(user_roles)
                self.user_roles[user_id] = [
                    user_role for user_role in user_roles
                    if not user_role.expires_at or user_role.expires_at > current_time
                ]
                cleaned_count += original_count - len(self.user_roles[user_id])
            
            # Clear permission caches for users with cleaned roles
            self.permission_cache.clear()
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired roles")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired roles: {e}")
            return 0


# Global RBAC manager instance
_rbac_manager = None


def get_rbac_manager() -> RBACManager:
    """Get global RBAC manager instance"""
    global _rbac_manager
    if _rbac_manager is None:
        _rbac_manager = RBACManager()
    return _rbac_manager


# Convenience functions
def check_permission(user_id: str, permission: Permission) -> bool:
    """Check if user has permission"""
    manager = get_rbac_manager()
    return manager.check_permission(user_id, permission)


def require_permission(permission: Permission):
    """Decorator to require permission"""
    manager = get_rbac_manager()
    return manager.require_permission(permission)


def require_role(role: Role):
    """Decorator to require role"""
    manager = get_rbac_manager()
    return manager.require_role(role)


def get_user_permissions(user_id: str) -> Set[Permission]:
    """Get user permissions"""
    manager = get_rbac_manager()
    return manager.get_user_permissions(user_id)


def get_role_permissions(role: Role) -> Set[Permission]:
    """Get role permissions"""
    manager = get_rbac_manager()
    return manager.get_role_permissions(role)


# Export public API
__all__ = [
    "Role",
    "Permission",
    "UserRole",
    "RolePermission",
    "RBACManager",
    "get_rbac_manager",
    "check_permission",
    "require_permission",
    "require_role",
    "get_user_permissions",
    "get_role_permissions"
]