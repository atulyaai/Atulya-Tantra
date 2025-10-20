"""
Integration tests for API endpoints
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
import json


class TestAPIEndpoints:
    """Test API endpoint integration"""
    
    def setup_method(self):
        """Setup test client"""
        # Mock the main app components to avoid full initialization
        with patch('src.main.agent_coordinator'), \
             patch('src.main.system_monitor'), \
             patch('src.main.decision_engine'), \
             patch('src.main.multi_agent_coordinator'), \
             patch('src.main.voice_interface'), \
             patch('src.main.task_executor'), \
             patch('src.main.safety_system'), \
             patch('src.main.integrations'):
            
            from src.main import app
            self.client = TestClient(app)
    
    def test_root_endpoint(self):
        """Test root endpoint"""
        response = self.client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == "Atulya Tantra"
        assert data["version"] == "2.5.0"
        assert data["status"] == "operational"
    
    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = self.client.get("/api/health/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
    
    def test_health_detailed_endpoint(self):
        """Test detailed health check endpoint"""
        with patch('src.main.system_monitor') as mock_monitor, \
             patch('src.main.task_executor') as mock_executor, \
             patch('src.main.safety_system') as mock_safety:
            
            mock_monitor.return_value.health_check = AsyncMock(return_value={"system_monitor": True})
            mock_executor.health_check = AsyncMock(return_value={"executor_running": True})
            mock_safety.health_check = AsyncMock(return_value={"safety_system": True})
            
            response = self.client.get("/api/health/detailed")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "healthy"
            assert "components" in data
    
    def test_health_ready_endpoint(self):
        """Test readiness check endpoint"""
        with patch('src.main.system_monitor') as mock_monitor, \
             patch('src.main.task_executor') as mock_executor, \
             patch('src.main.safety_system') as mock_safety:
            
            mock_monitor.return_value.health_check = AsyncMock(return_value={"system_monitor": True})
            mock_executor.health_check = AsyncMock(return_value={"executor_running": True})
            mock_safety.health_check = AsyncMock(return_value={"safety_system": True})
            
            response = self.client.get("/api/health/ready")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] in ["ready", "not_ready"]
            assert "ready_components" in data
    
    def test_health_live_endpoint(self):
        """Test liveness check endpoint"""
        response = self.client.get("/api/health/live")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data
    
    def test_metrics_endpoint(self):
        """Test Prometheus metrics endpoint"""
        response = self.client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; version=0.0.4; charset=utf-8"
        
        # Check that metrics content is returned
        content = response.text
        assert "http_requests_total" in content or "prometheus" in content.lower()
    
    def test_admin_status_without_auth(self):
        """Test admin status endpoint without authentication"""
        response = self.client.get("/api/admin/status")
        assert response.status_code == 401
    
    def test_admin_status_with_invalid_token(self):
        """Test admin status endpoint with invalid token"""
        headers = {"Authorization": "Bearer invalid-token"}
        response = self.client.get("/api/admin/status", headers=headers)
        assert response.status_code == 401
    
    def test_admin_status_with_valid_token(self):
        """Test admin status endpoint with valid admin token"""
        # Mock the auth service to return a valid admin payload
        with patch('src.api.routes.admin.auth_service') as mock_auth:
            mock_auth.verify_token.return_value = {"sub": "admin", "roles": ["admin"]}
            mock_auth.require_roles.return_value = True
            
            # Mock the system components
            with patch('src.api.routes.admin.SystemMonitor') as mock_monitor, \
                 patch('src.api.routes.admin.AgentCoordinator') as mock_coordinator, \
                 patch('src.api.routes.admin.DecisionEngine') as mock_decision:
                
                mock_monitor.return_value.get_system_health = AsyncMock(return_value={"status": "healthy"})
                mock_coordinator.return_value.health_check = AsyncMock(return_value={"status": "healthy"})
                mock_decision.return_value.health_check = AsyncMock(return_value={"status": "healthy"})
                
                headers = {"Authorization": "Bearer valid-admin-token"}
                response = self.client.get("/api/admin/status", headers=headers)
                assert response.status_code == 200
                
                data = response.json()
                assert data["status"] == "healthy"
                assert "system_health" in data
    
    def test_chat_stream_endpoint(self):
        """Test chat streaming endpoint"""
        # Mock the chat service
        with patch('src.api.routes.chat.get_chat_service') as mock_service:
            mock_chat_service = AsyncMock()
            mock_chat_service.stream_message.return_value = [
                {"type": "content", "content": "Hello"},
                {"type": "done", "content": ""}
            ]
            mock_service.return_value = mock_chat_service
            
            payload = {
                "message": "Hello",
                "conversation_id": "test-conv",
                "user_id": "test-user"
            }
            
            response = self.client.post("/api/chat/stream", json=payload)
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/plain; charset=utf-8"
    
    def test_system_status_endpoint(self):
        """Test system status endpoint"""
        with patch('src.main.agent_coordinator') as mock_coordinator, \
             patch('src.main.system_monitor') as mock_monitor, \
             patch('src.main.decision_engine') as mock_decision, \
             patch('src.main.multi_agent_coordinator') as mock_multi, \
             patch('src.main.voice_interface') as mock_voice, \
             patch('src.main.task_executor') as mock_executor, \
             patch('src.main.safety_system') as mock_safety, \
             patch('src.main.integrations') as mock_integrations:
            
            # Mock all health checks
            mock_coordinator.return_value.health_check = AsyncMock(return_value={"status": "healthy"})
            mock_monitor.return_value.health_check = AsyncMock(return_value={"status": "healthy"})
            mock_decision.return_value.health_check = AsyncMock(return_value={"status": "healthy"})
            mock_multi.return_value.health_check = AsyncMock(return_value={"status": "healthy"})
            mock_voice.return_value.health_check = AsyncMock(return_value={"status": "healthy"})
            mock_executor.health_check = AsyncMock(return_value={"status": "healthy"})
            mock_safety.health_check = AsyncMock(return_value={"status": "healthy"})
            mock_integrations.values.return_value = [AsyncMock(health_check=AsyncMock(return_value={"status": "healthy"}))]
            
            response = self.client.get("/api/status")
            assert response.status_code == 200
            
            data = response.json()
            assert data["system"] == "operational"
            assert "components" in data