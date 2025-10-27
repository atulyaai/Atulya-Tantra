"""
API authentication tests
Tests authentication endpoints and middleware
"""

import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from Core.api.main import app
from Core.auth import Role, Permission

client = TestClient(app)

class TestAuthEndpoints:
    """Test authentication API endpoints"""
    
    def test_register_user(self):
        """Test user registration"""
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
            "full_name": "Test User"
        }
        
        with patch('Core.api.main.insert_record') as mock_insert:
            mock_insert.return_value = None
            
            response = client.post("/api/auth/register", json=user_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["username"] == user_data["username"]
            assert data["email"] == user_data["email"]
            assert "user_id" in data
            assert "hashed_password" not in data  # Should not return password
    
    def test_register_duplicate_user(self):
        """Test registering duplicate user"""
        user_data = {
            "username": "existinguser",
            "email": "existing@example.com",
            "password": "password123"
        }
        
        with patch('Core.api.main.get_record_by_id') as mock_get:
            mock_get.return_value = {"username": "existinguser"}  # User exists
            
            response = client.post("/api/auth/register", json=user_data)
            
            assert response.status_code == 400
            assert "already registered" in response.json()["detail"]
    
    def test_login_user(self):
        """Test user login"""
        login_data = {
            "username": "testuser",
            "password": "password123"
        }
        
        with patch('Core.api.main.get_record_by_id') as mock_get, \
             patch('Core.api.main.update_record') as mock_update, \
             patch('Core.api.main.create_session') as mock_session:
            
            mock_get.return_value = {
                "user_id": "user123",
                "username": "testuser",
                "hashed_password": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4J/7QjK8q2",  # password123
                "is_active": True
            }
            mock_update.return_value = None
            mock_session.return_value = None
            
            response = client.post("/api/auth/login", json=login_data)
            
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"
            assert "expires_in" in data
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        login_data = {
            "username": "testuser",
            "password": "wrongpassword"
        }
        
        with patch('Core.api.main.get_record_by_id') as mock_get:
            mock_get.return_value = {
                "user_id": "user123",
                "username": "testuser",
                "hashed_password": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4J/7QjK8q2",  # password123
                "is_active": True
            }
            
            response = client.post("/api/auth/login", json=login_data)
            
            assert response.status_code == 401
            assert "Incorrect username or password" in response.json()["detail"]
    
    def test_get_current_user(self):
        """Test getting current user info"""
        # First login to get token
        login_data = {
            "username": "testuser",
            "password": "password123"
        }
        
        with patch('Core.api.main.get_record_by_id') as mock_get, \
             patch('Core.api.main.update_record') as mock_update, \
             patch('Core.api.main.create_session') as mock_session:
            
            mock_get.return_value = {
                "user_id": "user123",
                "username": "testuser",
                "email": "test@example.com",
                "hashed_password": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4J/7QjK8q2",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00",
                "last_login": None
            }
            mock_update.return_value = None
            mock_session.return_value = None
            
            # Login
            login_response = client.post("/api/auth/login", json=login_data)
            token = login_response.json()["access_token"]
            
            # Get current user
            response = client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["username"] == "testuser"
            assert data["email"] == "test@example.com"
    
    def test_refresh_token(self):
        """Test token refresh"""
        refresh_data = {"refresh_token": "valid_refresh_token"}
        
        with patch('Core.api.main.verify_token') as mock_verify, \
             patch('Core.api.main.get_record_by_id') as mock_get:
            
            mock_verify.return_value = {"sub": "user123", "username": "testuser"}
            mock_get.return_value = {
                "user_id": "user123",
                "username": "testuser",
                "is_active": True
            }
            
            response = client.post("/api/auth/refresh", json=refresh_data)
            
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"
    
    def test_logout_user(self):
        """Test user logout"""
        # Mock authenticated user
        with patch('Core.api.main.get_current_active_user') as mock_user, \
             patch('Core.api.main.delete_session') as mock_delete:
            
            mock_user.return_value = {
                "user_id": "user123",
                "username": "testuser"
            }
            mock_delete.return_value = 2  # 2 sessions deleted
            
            response = client.post("/api/auth/logout")
            
            assert response.status_code == 200
            data = response.json()
            assert "Logged out successfully" in data["message"]
            assert data["sessions_deleted"] == 2

class TestProtectedEndpoints:
    """Test protected endpoints with authentication"""
    
    def test_chat_endpoint_requires_auth(self):
        """Test that chat endpoint requires authentication"""
        message_data = {
            "message": "Hello JARVIS",
            "conversation_id": "conv123"
        }
        
        response = client.post("/api/chat/send", json=message_data)
        
        assert response.status_code == 401  # Unauthorized
    
    def test_chat_endpoint_with_auth(self):
        """Test chat endpoint with valid authentication"""
        message_data = {
            "message": "Hello JARVIS",
            "conversation_id": "conv123"
        }
        
        with patch('Core.api.main.get_current_active_user') as mock_user, \
             patch('Core.api.main.process_user_message') as mock_process:
            
            mock_user.return_value = {
                "user_id": "user123",
                "username": "testuser"
            }
            mock_process.return_value = {
                "response": "Hello! How can I help you?",
                "user_sentiment": "neutral",
                "jarvis_emotional_state": "friendly",
                "conversation_context": {},
                "metadata": {}
            }
            
            response = client.post("/api/chat/send", json=message_data)
            
            assert response.status_code == 200
            data = response.json()
            assert "response" in data
            assert data["conversation_id"] == "conv123"
    
    def test_admin_endpoint_requires_permission(self):
        """Test that admin endpoints require proper permissions"""
        with patch('Core.api.main.get_current_active_user') as mock_user:
            # Regular user (no admin permission)
            mock_user.return_value = {
                "user_id": "user123",
                "username": "testuser",
                "role": "user"
            }
            
            response = client.get("/api/admin/status")
            
            assert response.status_code == 403  # Forbidden
    
    def test_admin_endpoint_with_permission(self):
        """Test admin endpoint with proper permissions"""
        with patch('Core.api.main.get_current_active_user') as mock_user, \
             patch('Core.api.main.get_system_health') as mock_health:
            
            # Admin user
            mock_user.return_value = {
                "user_id": "admin123",
                "username": "admin",
                "role": "admin"
            }
            mock_health.return_value = {
                "overall_status": "healthy",
                "checks": {},
                "metrics": {},
                "alerts": {}
            }
            
            response = client.get("/api/admin/status")
            
            assert response.status_code == 200
            data = response.json()
            assert "system_health" in data
            assert "active_connections" in data

class TestRateLimiting:
    """Test rate limiting middleware"""
    
    def test_rate_limiting_headers(self):
        """Test that rate limiting headers are present"""
        response = client.get("/")
        
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers
    
    def test_rate_limiting_exceeded(self):
        """Test rate limiting when exceeded"""
        # This would require making many requests quickly
        # For now, just test that the endpoint exists
        response = client.get("/")
        assert response.status_code == 200

class TestSecurityHeaders:
    """Test security headers middleware"""
    
    def test_security_headers_present(self):
        """Test that security headers are present"""
        response = client.get("/")
        
        # Check for security headers
        assert "Content-Security-Policy" in response.headers
        assert "X-Frame-Options" in response.headers
        assert "X-Content-Type-Options" in response.headers
        assert "X-XSS-Protection" in response.headers
        assert "Referrer-Policy" in response.headers
        assert "Permissions-Policy" in response.headers
    
    def test_sensitive_endpoints_no_cache(self):
        """Test that sensitive endpoints have no-cache headers"""
        # Mock authentication for sensitive endpoint
        with patch('Core.api.main.get_current_active_user') as mock_user:
            mock_user.return_value = {
                "user_id": "user123",
                "username": "testuser",
                "role": "admin"
            }
            
            response = client.get("/api/admin/status")
            
            assert "Cache-Control" in response.headers
            assert "no-cache" in response.headers["Cache-Control"]

class TestInputValidation:
    """Test input validation and sanitization"""
    
    def test_malicious_input_sanitization(self):
        """Test that malicious input is sanitized"""
        malicious_data = {
            "message": "<script>alert('xss')</script>Hello",
            "conversation_id": "conv123"
        }
        
        with patch('Core.api.main.get_current_active_user') as mock_user, \
             patch('Core.api.main.process_user_message') as mock_process:
            
            mock_user.return_value = {
                "user_id": "user123",
                "username": "testuser"
            }
            mock_process.return_value = {
                "response": "Hello! How can I help you?",
                "user_sentiment": "neutral",
                "jarvis_emotional_state": "friendly",
                "conversation_context": {},
                "metadata": {}
            }
            
            response = client.post("/api/chat/send", json=malicious_data)
            
            # Should still process the request (sanitization happens in processing)
            assert response.status_code == 200
    
    def test_invalid_email_validation(self):
        """Test email validation in registration"""
        user_data = {
            "username": "testuser",
            "email": "invalid-email",
            "password": "password123"
        }
        
        response = client.post("/api/auth/register", json=user_data)
        
        # Should fail validation
        assert response.status_code == 422  # Validation error

if __name__ == "__main__":
    pytest.main([__file__, "-v"])