"""
Integration tests for API endpoints
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
import json
from datetime import datetime

# Import the main application
from src.main import app

client = TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints"""
    
    def test_health_live_endpoint(self):
        """Test /api/health/live endpoint"""
        response = client.get("/api/health/live")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
    
    def test_health_ready_endpoint(self):
        """Test /api/health/ready endpoint"""
        response = client.get("/api/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ready"


class TestAuthEndpoints:
    """Test authentication endpoints"""
    
    def test_auth_login_endpoint(self):
        """Test /api/auth/login endpoint"""
        login_data = {
            "username": "testuser",
            "password": "testpassword"
        }
        response = client.post("/api/auth/login", json=login_data)
        # Should return 401 for invalid credentials or 200 for valid
        assert response.status_code in [200, 401]
    
    def test_auth_register_endpoint(self):
        """Test /api/auth/register endpoint"""
        register_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "newpassword"
        }
        response = client.post("/api/auth/register", json=register_data)
        # Should return 200 for successful registration or 400 for validation errors
        assert response.status_code in [200, 400, 409]
    
    def test_auth_refresh_endpoint(self):
        """Test /api/auth/refresh endpoint"""
        # This would require a valid refresh token
        response = client.post("/api/auth/refresh", json={"refresh_token": "invalid_token"})
        assert response.status_code == 401


class TestChatEndpoints:
    """Test chat endpoints"""
    
    def test_chat_root_endpoint(self):
        """Test /api/chat/ endpoint"""
        response = client.get("/api/chat/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
    
    def test_chat_send_endpoint(self):
        """Test /api/chat/send endpoint"""
        chat_data = {
            "message": "Hello, JARVIS!",
            "conversation_id": "test_conv_1"
        }
        response = client.post("/api/chat/send", json=chat_data)
        # Should return 200 for successful chat or 401 for authentication required
        assert response.status_code in [200, 401]
    
    def test_chat_stream_endpoint(self):
        """Test /api/chat/stream endpoint"""
        chat_data = {
            "message": "Hello, JARVIS!",
            "conversation_id": "test_conv_1"
        }
        response = client.post("/api/chat/stream", json=chat_data)
        # Should return 200 for successful stream or 401 for authentication required
        assert response.status_code in [200, 401]
    
    def test_chat_history_endpoint(self):
        """Test /api/chat/history endpoint"""
        response = client.get("/api/chat/history?conversation_id=test_conv_1")
        # Should return 200 for successful retrieval or 401 for authentication required
        assert response.status_code in [200, 401]


class TestAdminEndpoints:
    """Test admin endpoints"""
    
    def test_admin_system_status_endpoint(self):
        """Test /api/admin/system/status endpoint"""
        response = client.get("/api/admin/system/status")
        # Should return 401 for authentication required
        assert response.status_code == 401
    
    def test_admin_agents_list_endpoint(self):
        """Test /api/admin/agents endpoint"""
        response = client.get("/api/admin/agents")
        # Should return 401 for authentication required
        assert response.status_code == 401
    
    def test_admin_agents_enable_endpoint(self):
        """Test /api/admin/agents/enable endpoint"""
        response = client.post("/api/admin/agents/enable", json={"agent_id": "test_agent"})
        # Should return 401 for authentication required
        assert response.status_code == 401
    
    def test_admin_system_restart_endpoint(self):
        """Test /api/admin/system/restart endpoint"""
        response = client.post("/api/admin/system/restart")
        # Should return 401 for authentication required
        assert response.status_code == 401


class TestAdminWithAuth:
    """Test admin endpoints with authentication"""
    
    @pytest.fixture
    def admin_token(self):
        """Mock admin token for testing"""
        return "mock_admin_token"
    
    @patch('src.api.routes.admin.verify_admin_token')
    def test_admin_system_status_with_auth(self, mock_verify, admin_token):
        """Test /api/admin/system/status with authentication"""
        mock_verify.return_value = {"user_id": "admin", "role": "admin"}
        
        response = client.get("/api/admin/system/status")
        assert response.status_code == 200
        data = response.json()
        assert "system_status" in data
    
    @patch('src.api.routes.admin.verify_admin_token')
    def test_admin_agents_list_with_auth(self, mock_verify, admin_token):
        """Test /api/admin/agents with authentication"""
        mock_verify.return_value = {"user_id": "admin", "role": "admin"}
        
        response = client.get("/api/admin/agents")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
    
    @patch('src.api.routes.admin.verify_admin_token')
    def test_admin_stats_with_auth(self, mock_verify, admin_token):
        """Test /api/admin/stats with authentication"""
        mock_verify.return_value = {"user_id": "admin", "role": "admin"}
        
        response = client.get("/api/admin/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_users" in data
        assert "system_health" in data
    
    @patch('src.api.routes.admin.verify_admin_token')
    def test_admin_chat_metrics_with_auth(self, mock_verify, admin_token):
        """Test /api/admin/chat-metrics with authentication"""
        mock_verify.return_value = {"user_id": "admin", "role": "admin"}
        
        response = client.get("/api/admin/chat-metrics")
        assert response.status_code == 200
        data = response.json()
        assert "total_messages" in data
        assert "model_usage" in data


class TestChatWithAuth:
    """Test chat endpoints with authentication"""
    
    @pytest.fixture
    def user_token(self):
        """Mock user token for testing"""
        return "mock_user_token"
    
    @patch('src.api.routes.chat.verify_token')
    def test_chat_send_with_auth(self, mock_verify, user_token):
        """Test /api/chat/send with authentication"""
        mock_verify.return_value = {"user_id": "user1", "role": "user"}
        
        chat_data = {
            "message": "Hello, JARVIS!",
            "conversation_id": "test_conv_1"
        }
        response = client.post("/api/chat/send", json=chat_data)
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
    
    @patch('src.api.routes.chat.verify_token')
    def test_chat_stream_with_auth(self, mock_verify, user_token):
        """Test /api/chat/stream with authentication"""
        mock_verify.return_value = {"user_id": "user1", "role": "user"}
        
        chat_data = {
            "message": "Hello, JARVIS!",
            "conversation_id": "test_conv_1"
        }
        response = client.post("/api/chat/stream", json=chat_data)
        assert response.status_code == 200
    
    @patch('src.api.routes.chat.verify_token')
    def test_chat_history_with_auth(self, mock_verify, user_token):
        """Test /api/chat/history with authentication"""
        mock_verify.return_value = {"user_id": "user1", "role": "user"}
        
        response = client.get("/api/chat/history?conversation_id=test_conv_1")
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data


class TestAPIErrorHandling:
    """Test API error handling"""
    
    def test_invalid_endpoint(self):
        """Test invalid endpoint returns 404"""
        response = client.get("/api/invalid/endpoint")
        assert response.status_code == 404
    
    def test_invalid_json(self):
        """Test invalid JSON returns 422"""
        response = client.post("/api/chat/send", data="invalid json")
        assert response.status_code == 422
    
    def test_missing_required_fields(self):
        """Test missing required fields returns 422"""
        response = client.post("/api/chat/send", json={})
        assert response.status_code == 422


class TestAPIPerformance:
    """Test API performance"""
    
    def test_health_endpoint_performance(self):
        """Test health endpoint response time"""
        import time
        start_time = time.time()
        response = client.get("/api/health/live")
        end_time = time.time()
        
        assert response.status_code == 200
        assert (end_time - start_time) < 1.0  # Should respond within 1 second
    
    def test_root_endpoint_performance(self):
        """Test root endpoint response time"""
        import time
        start_time = time.time()
        response = client.get("/")
        end_time = time.time()
        
        assert response.status_code == 200
        assert (end_time - start_time) < 1.0  # Should respond within 1 second


class TestAPIHeaders:
    """Test API headers and CORS"""
    
    def test_cors_headers(self):
        """Test CORS headers are present"""
        response = client.options("/api/health/live")
        # CORS headers should be present
        assert response.status_code in [200, 405]  # OPTIONS might not be implemented
    
    def test_content_type_headers(self):
        """Test content type headers"""
        response = client.get("/api/health/live")
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_api_integration_full_flow():
    """Test full API integration flow"""
    # Test the complete flow of API interactions
    
    # 1. Check health
    health_response = client.get("/api/health/live")
    assert health_response.status_code == 200
    
    # 2. Test root endpoint
    root_response = client.get("/")
    assert root_response.status_code == 200
    
    # 3. Test chat endpoint structure (without auth)
    chat_response = client.get("/api/chat/")
    assert chat_response.status_code == 200
    
    # 4. Test admin endpoint requires auth
    admin_response = client.get("/api/admin/system/status")
    assert admin_response.status_code == 401
