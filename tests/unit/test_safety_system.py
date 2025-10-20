"""
Unit tests for safety system
"""

import pytest
from unittest.mock import Mock, AsyncMock
from src.core.agents.system_safety import SafetySystem, ActionType, SafetyLevel, SafetyViolation


class TestSafetySystem:
    """Test safety system functionality"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.safety_system = SafetySystem()
    
    @pytest.mark.asyncio
    async def test_check_action_safety_safe_action(self):
        """Test safety check for safe actions"""
        result = await self.safety_system.check_action_safety(
            ActionType.READ,
            {"file_path": "/tmp/test.txt"},
            user_id="test_user"
        )
        
        assert result["safe"] == True
        assert result["blocked"] == False
        assert len(result["violations"]) == 0
    
    @pytest.mark.asyncio
    async def test_check_action_safety_blocked_deletion(self):
        """Test safety check blocks dangerous file deletion"""
        result = await self.safety_system.check_action_safety(
            ActionType.DELETE,
            {"file_path": "C:\\Windows\\System32\\kernel32.dll"},
            user_id="test_user"
        )
        
        assert result["safe"] == False
        assert result["blocked"] == True
        assert len(result["violations"]) > 0
    
    @pytest.mark.asyncio
    async def test_check_action_safety_unauthorized_user(self):
        """Test safety check for unauthorized user"""
        result = await self.safety_system.check_action_safety(
            ActionType.WRITE,
            {"file_path": "/tmp/test.txt"},
            user_id="unauthorized_user"
        )
        
        # Should be blocked due to lack of permissions
        assert result["blocked"] == True
        assert any("lacks permission" in v["message"] for v in result["violations"])
    
    @pytest.mark.asyncio
    async def test_grant_user_permission(self):
        """Test granting user permissions"""
        await self.safety_system.grant_user_permission("test_user", "read")
        await self.safety_system.grant_user_permission("test_user", "write")
        
        assert "read" in self.safety_system.user_permissions["test_user"]
        assert "write" in self.safety_system.user_permissions["test_user"]
    
    @pytest.mark.asyncio
    async def test_grant_agent_permission(self):
        """Test granting agent permissions"""
        await self.safety_system.grant_agent_permission("test_agent", "network")
        await self.safety_system.grant_agent_permission("test_agent", "system_access")
        
        assert "network" in self.safety_system.agent_permissions["test_agent"]
        assert "system_access" in self.safety_system.agent_permissions["test_agent"]
    
    @pytest.mark.asyncio
    async def test_add_safety_rule(self):
        """Test adding custom safety rules"""
        from src.core.agents.skynet.safety import SafetyRule
        from datetime import datetime
        
        rule = SafetyRule(
            rule_id="test_rule",
            name="Test Rule",
            description="Test safety rule",
            action_types=[ActionType.EXECUTE],
            safety_level=SafetyLevel.HIGH,
            conditions={"blocked_commands": ["rm -rf /"]},
            enforcement="block",
            created_at=datetime.now()
        )
        
        await self.safety_system.add_safety_rule(rule)
        assert "test_rule" in self.safety_system.safety_rules
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test safety system health check"""
        health = await self.safety_system.health_check()
        
        assert health["safety_system"] == True
        assert "total_rules" in health
        assert "total_events" in health
        assert "users_with_permissions" in health
        assert "agents_with_permissions" in health
    
    @pytest.mark.asyncio
    async def test_get_safety_events(self):
        """Test retrieving safety events"""
        # Create a test event by triggering a violation
        await self.safety_system.check_action_safety(
            ActionType.DELETE,
            {"file_path": "C:\\Windows\\System32\\kernel32.dll"},
            user_id="test_user"
        )
        
        events = await self.safety_system.get_safety_events(limit=10)
        assert len(events) > 0
        assert events[0].action_type == ActionType.DELETE
