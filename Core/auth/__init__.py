"""
Authentication and authorization module for Atulya Tantra AGI
Provides JWT authentication, password management, and RBAC
"""

from .jwt import JWTManager, create_access_token, verify_token, get_current_user
from .password import PasswordManager, verify_password, get_password_hash
from .session import SessionManager, create_session, get_session, delete_session
from .rbac import RBACManager, require_auth, require_role, require_permission
from .security import SecurityManager, validate_input, sanitize_input

__all__ = [
    "JWTManager",
    "create_access_token", 
    "verify_token",
    "get_current_user",
    "PasswordManager",
    "verify_password",
    "get_password_hash",
    "SessionManager",
    "create_session",
    "get_session", 
    "delete_session",
    "RBACManager",
    "require_auth",
    "require_role",
    "require_permission",
    "SecurityManager",
    "validate_input",
    "sanitize_input"
]