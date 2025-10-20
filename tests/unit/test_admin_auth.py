"""
Unit tests for admin authentication and authorization
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from fastapi import HTTPException
from src.services.auth_service import AuthService
from src.api.routes.admin import verify_admin_token


class TestAdminAuth:
    """Test admin authentication and authorization"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.auth_service = AuthService()
    
    @pytest.mark.asyncio
    async def test_verify_admin_token_valid(self):
        """Test valid admin token verification"""
        # Create a valid admin token
        token_data = {"sub": "admin", "roles": ["admin"], "exp": 9999999999}
        with patch('src.api.routes.admin.auth_service') as mock_auth:
            mock_auth.verify_token.return_value = token_data
            mock_auth.require_roles.return_value = True
            
            # Mock the credentials
            credentials = Mock()
            credentials.credentials = "valid-token"
            
            # This should not raise an exception
            result = await verify_admin_token(credentials)
            assert result == token_data
    
    @pytest.mark.asyncio
    async def test_verify_admin_token_invalid(self):
        """Test invalid token verification"""
        with patch('src.api.routes.admin.auth_service') as mock_auth:
            mock_auth.verify_token.return_value = None
            
            credentials = Mock()
            credentials.credentials = "invalid-token"
            
            with pytest.raises(HTTPException) as exc_info:
                await verify_admin_token(credentials)
            
            assert exc_info.value.status_code == 401
            assert "Invalid or expired token" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_verify_admin_token_insufficient_roles(self):
        """Test token with insufficient roles"""
        token_data = {"sub": "user", "roles": ["user"], "exp": 9999999999}
        with patch('src.api.routes.admin.auth_service') as mock_auth:
            mock_auth.verify_token.return_value = token_data
            mock_auth.require_roles.return_value = False
            
            credentials = Mock()
            credentials.credentials = "user-token"
            
            with pytest.raises(HTTPException) as exc_info:
                await verify_admin_token(credentials)
            
            assert exc_info.value.status_code == 403
            assert "Insufficient permissions" in str(exc_info.value.detail)
    
    def test_generate_admin_token(self):
        """Test admin token generation"""
        token = self.auth_service.generate_admin_token("admin", ["admin"], 60)
        assert token is not None
        
        # Verify the token can be decoded
        payload = self.auth_service.verify_token(token)
        assert payload is not None
        assert payload["sub"] == "admin"
        assert "admin" in payload["roles"]
    
    def test_require_roles(self):
        """Test role requirement checking"""
        payload = {"roles": ["admin", "user"]}
        
        # Should pass with admin role
        assert self.auth_service.require_roles(payload, ["admin"]) == True
        
        # Should pass with user role
        assert self.auth_service.require_roles(payload, ["user"]) == True
        
        # Should fail with non-existent role
        assert self.auth_service.require_roles(payload, ["superuser"]) == False
        
        # Should fail with empty roles
        payload_no_roles = {}
        assert self.auth_service.require_roles(payload_no_roles, ["admin"]) == False
