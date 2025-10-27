"""
Comprehensive tests for authentication and authorization system
Tests JWT, password management, sessions, RBAC, and security features
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from Core.auth.jwt import JWTManager, create_access_token, verify_token, get_current_user
from Core.auth.password import PasswordManager, validate_password_strength, generate_secure_password
from Core.auth.session import SessionManager, create_session, get_session, delete_session
from Core.auth.rbac import RBACManager, Role, Permission, check_permission, check_role
from Core.auth.security import SecurityManager, validate_input, validate_email, detect_sql_injection
from Core.config.settings import settings

class TestJWTManager:
    """Test JWT token management"""
    
    def setup_method(self):
        self.jwt_manager = JWTManager()
        self.test_data = {"sub": "user123", "username": "testuser"}
    
    def test_create_access_token(self):
        """Test access token creation"""
        token = self.jwt_manager.create_access_token(self.test_data)
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_create_refresh_token(self):
        """Test refresh token creation"""
        token = self.jwt_manager.create_refresh_token(self.test_data)
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_verify_valid_token(self):
        """Test verifying valid token"""
        token = self.jwt_manager.create_access_token(self.test_data)
        payload = self.jwt_manager.verify_token(token)
        
        assert payload["sub"] == self.test_data["sub"]
        assert payload["username"] == self.test_data["username"]
        assert payload["type"] == "access"
    
    def test_verify_refresh_token(self):
        """Test verifying refresh token"""
        token = self.jwt_manager.create_refresh_token(self.test_data)
        payload = self.jwt_manager.verify_token(token, "refresh")
        
        assert payload["sub"] == self.test_data["sub"]
        assert payload["type"] == "refresh"
    
    def test_verify_expired_token(self):
        """Test verifying expired token"""
        # Create token with very short expiration
        token = self.jwt_manager.create_access_token(self.test_data, timedelta(seconds=-1))
        
        with pytest.raises(Exception):  # Should raise JWT error
            self.jwt_manager.verify_token(token)
    
    def test_verify_invalid_token(self):
        """Test verifying invalid token"""
        with pytest.raises(Exception):
            self.jwt_manager.verify_token("invalid.token.here")
    
    def test_refresh_access_token(self):
        """Test refreshing access token"""
        refresh_token = self.jwt_manager.create_refresh_token(self.test_data)
        new_access_token = self.jwt_manager.refresh_access_token(refresh_token)
        
        assert isinstance(new_access_token, str)
        payload = self.jwt_manager.verify_token(new_access_token)
        assert payload["sub"] == self.test_data["sub"]

class TestPasswordManager:
    """Test password management"""
    
    def setup_method(self):
        self.password_manager = PasswordManager()
    
    def test_hash_password(self):
        """Test password hashing"""
        password = "testpassword123"
        hashed = self.password_manager.hash_password(password)
        
        assert isinstance(hashed, str)
        assert hashed != password
        assert len(hashed) > 0
    
    def test_verify_password(self):
        """Test password verification"""
        password = "testpassword123"
        hashed = self.password_manager.hash_password(password)
        
        assert self.password_manager.verify_password(password, hashed) == True
        assert self.password_manager.verify_password("wrongpassword", hashed) == False
    
    def test_validate_password_strength(self):
        """Test password strength validation"""
        # Strong password
        is_valid, errors = self.password_manager.validate_password_strength("StrongPass123!")
        assert is_valid == True
        assert len(errors) == 0
        
        # Weak password
        is_valid, errors = self.password_manager.validate_password_strength("weak")
        assert is_valid == False
        assert len(errors) > 0
    
    def test_generate_secure_password(self):
        """Test secure password generation"""
        password = self.password_manager.generate_secure_password()
        
        assert isinstance(password, str)
        assert len(password) >= 16
        
        # Check strength
        is_valid, errors = self.password_manager.validate_password_strength(password)
        assert is_valid == True
    
    def test_password_strength_score(self):
        """Test password strength scoring"""
        # Very weak password
        score = self.password_manager.get_password_strength_score("123")
        assert score < 30
        
        # Strong password
        score = self.password_manager.get_password_strength_score("StrongPass123!")
        assert score > 70

class TestSessionManager:
    """Test session management"""
    
    def setup_method(self):
        self.session_manager = SessionManager()
    
    @pytest.mark.asyncio
    async def test_create_session(self):
        """Test session creation"""
        session = await self.session_manager.create_session(
            user_id="user123",
            username="testuser",
            ip_address="127.0.0.1"
        )
        
        assert session.user_id == "user123"
        assert session.username == "testuser"
        assert session.ip_address == "127.0.0.1"
        assert session.is_active == True
    
    @pytest.mark.asyncio
    async def test_get_session(self):
        """Test getting session"""
        # Mock database operations
        with patch('Core.auth.session.get_record_by_id') as mock_get:
            mock_get.return_value = {
                "session_id": "session123",
                "user_id": "user123",
                "username": "testuser",
                "created_at": datetime.utcnow().isoformat(),
                "last_accessed": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
                "is_active": True
            }
            
            session = await self.session_manager.get_session("session123")
            
            assert session is not None
            assert session.user_id == "user123"
            assert session.username == "testuser"
    
    @pytest.mark.asyncio
    async def test_validate_session(self):
        """Test session validation"""
        with patch('Core.auth.session.get_record_by_id') as mock_get:
            mock_get.return_value = {
                "session_id": "session123",
                "user_id": "user123",
                "username": "testuser",
                "created_at": datetime.utcnow().isoformat(),
                "last_accessed": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
                "is_active": True
            }
            
            is_valid = await self.session_manager.validate_session("session123")
            assert is_valid == True
    
    @pytest.mark.asyncio
    async def test_delete_session(self):
        """Test session deletion"""
        with patch('Core.auth.session.delete_record') as mock_delete:
            mock_delete.return_value = True
            
            result = await self.session_manager.delete_session("session123")
            assert result == True

class TestRBACManager:
    """Test role-based access control"""
    
    def setup_method(self):
        self.rbac_manager = RBACManager()
        self.admin_user = {"user_id": "admin1", "role": "admin"}
        self.regular_user = {"user_id": "user1", "role": "user"}
        self.guest_user = {"user_id": "guest1", "role": "guest"}
    
    def test_get_user_permissions(self):
        """Test getting user permissions"""
        admin_perms = self.rbac_manager.get_user_permissions(self.admin_user)
        user_perms = self.rbac_manager.get_user_permissions(self.regular_user)
        guest_perms = self.rbac_manager.get_user_permissions(self.guest_user)
        
        # Admin should have more permissions
        assert len(admin_perms) > len(user_perms)
        assert len(user_perms) > len(guest_perms)
        
        # Check specific permissions
        assert Permission.SYSTEM_ADMIN in admin_perms
        assert Permission.SYSTEM_ADMIN not in user_perms
        assert Permission.CHAT_READ in user_perms
        assert Permission.CHAT_WRITE in user_perms
    
    def test_has_permission(self):
        """Test permission checking"""
        assert self.rbac_manager.has_permission(self.admin_user, Permission.SYSTEM_ADMIN) == True
        assert self.rbac_manager.has_permission(self.regular_user, Permission.SYSTEM_ADMIN) == False
        assert self.rbac_manager.has_permission(self.regular_user, Permission.CHAT_READ) == True
        assert self.rbac_manager.has_permission(self.guest_user, Permission.CHAT_WRITE) == False
    
    def test_has_role(self):
        """Test role checking"""
        assert self.rbac_manager.has_role(self.admin_user, Role.ADMIN) == True
        assert self.rbac_manager.has_role(self.regular_user, Role.ADMIN) == False
        assert self.rbac_manager.has_role(self.regular_user, Role.USER) == True
    
    def test_custom_permissions(self):
        """Test custom permissions"""
        user_id = "user123"
        permission = Permission.CHAT_DELETE
        
        # Add custom permission
        self.rbac_manager.add_custom_permission(user_id, permission)
        
        user = {"user_id": user_id, "role": "user"}
        assert self.rbac_manager.has_permission(user, permission) == True
        
        # Remove custom permission
        self.rbac_manager.remove_custom_permission(user_id, permission)
        assert self.rbac_manager.has_permission(user, permission) == False

class TestSecurityManager:
    """Test security utilities"""
    
    def setup_method(self):
        self.security_manager = SecurityManager()
    
    def test_sanitize_input(self):
        """Test input sanitization"""
        # Test XSS prevention
        malicious_input = "<script>alert('xss')</script>Hello"
        sanitized = self.security_manager.sanitize_input(malicious_input)
        assert "<script>" not in sanitized
        assert "Hello" in sanitized
        
        # Test SQL injection prevention
        sql_input = "'; DROP TABLE users; --"
        sanitized = self.security_manager.sanitize_input(sql_input)
        assert "DROP TABLE" not in sanitized
    
    def test_validate_email(self):
        """Test email validation"""
        assert self.security_manager.validate_email("test@example.com") == True
        assert self.security_manager.validate_email("invalid-email") == False
        assert self.security_manager.validate_email("") == False
    
    def test_validate_username(self):
        """Test username validation"""
        assert self.security_manager.validate_username("validuser123") == True
        assert self.security_manager.validate_username("user@name") == False
        assert self.security_manager.validate_username("ab") == False  # Too short
        assert self.security_manager.validate_username("a" * 51) == False  # Too long
    
    def test_detect_sql_injection(self):
        """Test SQL injection detection"""
        assert self.security_manager.detect_sql_injection("SELECT * FROM users") == True
        assert self.security_manager.detect_sql_injection("'; DROP TABLE users; --") == True
        assert self.security_manager.detect_sql_injection("normal text") == False
    
    def test_detect_xss(self):
        """Test XSS detection"""
        assert self.security_manager.detect_xss("<script>alert('xss')</script>") == True
        assert self.security_manager.detect_xss("javascript:alert('xss')") == True
        assert self.security_manager.detect_xss("normal text") == False
    
    def test_validate_file_upload(self):
        """Test file upload validation"""
        # Valid file
        result = self.security_manager.validate_file_upload(
            "test.pdf", "application/pdf", 1024
        )
        assert result["valid"] == True
        
        # Invalid file type
        result = self.security_manager.validate_file_upload(
            "test.exe", "application/octet-stream", 1024
        )
        assert result["valid"] == False

class TestIntegration:
    """Integration tests for authentication system"""
    
    @pytest.mark.asyncio
    async def test_full_auth_flow(self):
        """Test complete authentication flow"""
        # Mock database operations
        with patch('Core.auth.session.get_record_by_id') as mock_get, \
             patch('Core.auth.session.insert_record') as mock_insert, \
             patch('Core.auth.session.update_record') as mock_update:
            
            # Mock user data
            mock_get.return_value = {
                "user_id": "user123",
                "username": "testuser",
                "email": "test@example.com",
                "hashed_password": PasswordManager().hash_password("password123"),
                "role": "user",
                "is_active": True,
                "created_at": datetime.utcnow().isoformat(),
                "last_login": None
            }
            
            # Test password verification
            password_manager = PasswordManager()
            user_data = mock_get.return_value
            
            assert password_manager.verify_password(
                "password123", 
                user_data["hashed_password"]
            ) == True
            
            # Test JWT token creation
            jwt_manager = JWTManager()
            token = jwt_manager.create_access_token({
                "sub": user_data["user_id"],
                "username": user_data["username"]
            })
            
            # Test token verification
            payload = jwt_manager.verify_token(token)
            assert payload["sub"] == user_data["user_id"]
            
            # Test session creation
            session_manager = SessionManager()
            session = await session_manager.create_session(
                user_id=user_data["user_id"],
                username=user_data["username"]
            )
            
            assert session.user_id == user_data["user_id"]
            assert session.username == user_data["username"]
    
    def test_rbac_integration(self):
        """Test RBAC integration with different user types"""
        rbac_manager = RBACManager()
        
        # Test admin user
        admin_user = {"user_id": "admin1", "role": "admin"}
        admin_perms = rbac_manager.get_user_permissions(admin_user)
        
        # Admin should have all permissions
        assert Permission.SYSTEM_ADMIN in admin_perms
        assert Permission.USER_MANAGE in admin_perms
        assert Permission.CHAT_READ in admin_perms
        
        # Test regular user
        user = {"user_id": "user1", "role": "user"}
        user_perms = rbac_manager.get_user_permissions(user)
        
        # User should have limited permissions
        assert Permission.SYSTEM_ADMIN not in user_perms
        assert Permission.USER_MANAGE not in user_perms
        assert Permission.CHAT_READ in user_perms
        assert Permission.CHAT_WRITE in user_perms

if __name__ == "__main__":
    pytest.main([__file__, "-v"])