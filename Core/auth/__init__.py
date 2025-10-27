"""
Authentication and Authorization System for Atulya Tantra AGI
JWT tokens, password management, RBAC, security, and session management
"""

from .jwt import (
    create_access_token,
    create_refresh_token,
    verify_token,
    decode_token,
    get_token_payload,
    TokenData,
    TokenType
)
from .password import (
    hash_password,
    verify_password,
    validate_password_strength,
    PasswordStrength,
    PasswordValidationResult
)
from .rbac import (
    Role,
    Permission,
    check_permission,
    require_permission,
    require_role,
    get_user_permissions,
    get_role_permissions,
    RBACManager
)
from .security import (
    SecurityManager,
    generate_secure_token,
    validate_input,
    sanitize_input,
    SecurityLevel,
    SecurityViolation
)
from .session import (
    SessionManager,
    create_session,
    get_session,
    update_session,
    delete_session,
    cleanup_expired_sessions,
    SessionData
)

__all__ = [
    # JWT
    "create_access_token",
    "create_refresh_token", 
    "verify_token",
    "decode_token",
    "get_token_payload",
    "TokenData",
    "TokenType",
    
    # Password
    "hash_password",
    "verify_password",
    "validate_password_strength",
    "PasswordStrength",
    "PasswordValidationResult",
    
    # RBAC
    "Role",
    "Permission",
    "check_permission",
    "require_permission",
    "require_role",
    "get_user_permissions",
    "get_role_permissions",
    "RBACManager",
    
    # Security
    "SecurityManager",
    "generate_secure_token",
    "validate_input",
    "sanitize_input",
    "SecurityLevel",
    "SecurityViolation",
    
    # Session
    "SessionManager",
    "create_session",
    "get_session",
    "update_session",
    "delete_session",
    "cleanup_expired_sessions",
    "SessionData"
]