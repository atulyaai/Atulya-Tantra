"""
Unit tests for Skynet agent modules
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Import the system automation agents
from src.core.agents.system_control import SystemController
from src.core.agents.system_automation import DesktopAutomation
from src.core.agents.system_scheduler import TaskScheduler, TaskPriority
from src.core.agents.system_monitor import SystemMonitor, HealthStatus
from src.core.agents.system_healer import AutoHealingSystem, HealingAction
from src.core.agents.system_decision_engine import DecisionEngine, DecisionContext
from src.core.agents.system_coordinator import MultiAgentCoordinator
from src.core.agents.system_executor import TaskExecutor
from src.core.agents.system_safety import SafetySystem


class TestSystemController:
    """Test Skynet System Controller"""
    
    @pytest.fixture
    def system_controller(self):
        config = {"auto_mode": False}
        return SystemController(config)
    
    @pytest.mark.asyncio
    async def test_system_controller_initialization(self, system_controller):
        """Test system controller initialization"""
        assert system_controller.auto_mode == False
        assert system_controller.active_tasks == []
        assert system_controller.system_info is not None
    
    @pytest.mark.asyncio
    async def test_get_system_info(self, system_controller):
        """Test getting system information"""
        info = await system_controller.get_system_info()
        assert info is not None
        assert "cpu_percent" in info
        assert "memory_percent" in info
        assert "disk_usage" in info
    
    @pytest.mark.asyncio
    async def test_get_processes(self, system_controller):
        """Test getting running processes"""
        processes = await system_controller.get_running_processes()
        assert isinstance(processes, list)
        if processes:
            assert "pid" in processes[0]
            assert "name" in processes[0]
    
    @pytest.mark.asyncio
    async def test_kill_process(self, system_controller):
        """Test killing a process"""
        # Mock process killing for safety
        with patch.object(system_controller, '_kill_process') as mock_kill:
            mock_kill.return_value = True
            result = await system_controller.kill_process(9999)
            assert result == True


class TestDesktopAutomation:
    """Test Skynet Desktop Automation"""
    
    @pytest.fixture
    def desktop_automation(self):
        config = {"enabled": False}  # Disabled for safety in tests
        return DesktopAutomation(config)
    
    @pytest.mark.asyncio
    async def test_desktop_automation_initialization(self, desktop_automation):
        """Test desktop automation initialization"""
        assert desktop_automation.enabled == False
        assert desktop_automation.safety_enabled == True
    
    @pytest.mark.asyncio
    async def test_click_coordinates(self, desktop_automation):
        """Test clicking coordinates"""
        if desktop_automation.enabled:
            result = await desktop_automation.click(100, 200)
            assert result is not None
        else:
            # When disabled, should return error
            result = await desktop_automation.click(100, 200)
            assert "error" in result
    
    @pytest.mark.asyncio
    async def test_type_text(self, desktop_automation):
        """Test typing text"""
        if desktop_automation.enabled:
            result = await desktop_automation.type_text("Hello World")
            assert result is not None
        else:
            result = await desktop_automation.type_text("Hello World")
            assert "error" in result


class TestTaskScheduler:
    """Test Skynet Task Scheduler"""
    
    @pytest.fixture
    def task_scheduler(self):
        config = {}
        return TaskScheduler(config)
    
    @pytest.mark.asyncio
    async def test_task_scheduler_initialization(self, task_scheduler):
        """Test task scheduler initialization"""
        assert task_scheduler.scheduled_tasks == {}
        assert task_scheduler.running == False
    
    @pytest.mark.asyncio
    async def test_schedule_task(self, task_scheduler):
        """Test scheduling a task"""
        task_id = await task_scheduler.schedule_task(
            "test_task", 
            lambda: print("Hello"), 
            "*/1 * * * *",  # Every minute
            TaskPriority.NORMAL
        )
        assert task_id is not None
        assert task_id in task_scheduler.scheduled_tasks
    
    @pytest.mark.asyncio
    async def test_cancel_task(self, task_scheduler):
        """Test canceling a task"""
        task_id = await task_scheduler.schedule_task(
            "test_task", 
            lambda: print("Hello"), 
            "*/1 * * * *",
            TaskPriority.NORMAL
        )
        
        result = await task_scheduler.cancel_task(task_id)
        assert result == True
        assert task_id not in task_scheduler.scheduled_tasks
    
    @pytest.mark.asyncio
    async def test_get_scheduled_tasks(self, task_scheduler):
        """Test getting scheduled tasks"""
        await task_scheduler.schedule_task(
            "test_task", 
            lambda: print("Hello"), 
            "*/1 * * * *",
            TaskPriority.NORMAL
        )
        
        tasks = await task_scheduler.get_scheduled_tasks()
        assert len(tasks) == 1
        assert tasks[0].task_name == "test_task"


class TestSystemMonitor:
    """Test Skynet System Monitor"""
    
    @pytest.fixture
    def system_monitor(self):
        config = {"monitoring_interval": 5}
        return SystemMonitor(config)
    
    @pytest.mark.asyncio
    async def test_system_monitor_initialization(self, system_monitor):
        """Test system monitor initialization"""
        assert system_monitor.monitoring_interval == 5
        assert system_monitor.metrics_history == []
        assert system_monitor.alerts == []
    
    @pytest.mark.asyncio
    async def test_collect_metrics(self, system_monitor):
        """Test collecting system metrics"""
        metrics = await system_monitor.collect_metrics()
        assert metrics is not None
        assert "timestamp" in metrics
        assert "cpu_percent" in metrics
        assert "memory_percent" in metrics
        assert "disk_usage" in metrics
    
    @pytest.mark.asyncio
    async def test_check_health(self, system_monitor):
        """Test checking system health"""
        health = await system_monitor.check_health()
        assert health is not None
        assert "status" in health
        assert health["status"] in [HealthStatus.HEALTHY, HealthStatus.WARNING, HealthStatus.CRITICAL]
    
    @pytest.mark.asyncio
    async def test_generate_alert(self, system_monitor):
        """Test generating alerts"""
        alert = await system_monitor.generate_alert(
            "High CPU Usage", 
            "CPU usage is above 90%", 
            "warning"
        )
        assert alert is not None
        assert alert["message"] == "High CPU Usage"
        assert alert["severity"] == "warning"


class TestAutoHealingSystem:
    """Test Skynet Auto Healing System"""
    
    @pytest.fixture
    def auto_healer(self):
        config = {"enabled": True}
        return AutoHealingSystem(config)
    
    @pytest.mark.asyncio
    async def test_auto_healer_initialization(self, auto_healer):
        """Test auto healer initialization"""
        assert auto_healer.enabled == True
        assert auto_healer.healing_rules == {}
        assert auto_healer.healing_history == []
    
    @pytest.mark.asyncio
    async def test_analyze_alert(self, auto_healer):
        """Test analyzing alerts"""
        alert = {
            "type": "high_memory",
            "severity": "warning",
            "message": "High memory usage detected"
        }
        
        action = await auto_healer.analyze_alert(alert)
        assert action is not None
        assert action.action_type in ["restart_service", "clear_cache", "scale_resources", "no_action"]
    
    @pytest.mark.asyncio
    async def test_execute_healing_action(self, auto_healer):
        """Test executing healing actions"""
        action = HealingAction(
            action_type="clear_cache",
            description="Clear system cache",
            parameters={"cache_type": "memory"}
        )
        
        result = await auto_healer.execute_healing_action(action)
        assert result is not None
        assert "success" in result or "error" in result


class TestDecisionEngine:
    """Test Skynet Decision Engine"""
    
    @pytest.fixture
    def decision_engine(self):
        config = {"learning_enabled": True}
        return DecisionEngine(config)
    
    @pytest.mark.asyncio
    async def test_decision_engine_initialization(self, decision_engine):
        """Test decision engine initialization"""
        assert decision_engine.learning_enabled == True
        assert decision_engine.decision_history == []
        assert decision_engine.performance_metrics == {}
    
    @pytest.mark.asyncio
    async def test_make_decision(self, decision_engine):
        """Test making decisions"""
        context = DecisionContext(
            situation="high_cpu_usage",
            available_actions=["restart_service", "scale_up", "optimize_code"],
            constraints={"budget": 100, "downtime": 5},
            goals=["reduce_cpu_usage", "maintain_performance"]
        )
        
        decision = await decision_engine.make_decision(context)
        assert decision is not None
        assert decision.action in context.available_actions
        assert decision.confidence >= 0.0 and decision.confidence <= 1.0
    
    @pytest.mark.asyncio
    async def test_evaluate_decision(self, decision_engine):
        """Test evaluating decisions"""
        decision = {
            "action": "restart_service",
            "confidence": 0.8,
            "context": "high_cpu_usage"
        }
        
        result = {"cpu_usage": 50, "success": True}
        
        evaluation = await decision_engine.evaluate_decision(decision, result)
        assert evaluation is not None
        assert "effectiveness" in evaluation
        assert "lessons_learned" in evaluation


class TestMultiAgentCoordinator:
    """Test Skynet Multi-Agent Coordinator"""
    
    @pytest.fixture
    def coordinator(self):
        config = {"max_concurrent_tasks": 5}
        return MultiAgentCoordinator(config)
    
    @pytest.mark.asyncio
    async def test_coordinator_initialization(self, coordinator):
        """Test coordinator initialization"""
        assert coordinator.max_concurrent_tasks == 5
        assert coordinator.active_tasks == {}
        assert coordinator.agent_status == {}
    
    @pytest.mark.asyncio
    async def test_register_agent(self, coordinator):
        """Test registering agents"""
        agent_info = {
            "agent_id": "test_agent",
            "capabilities": ["monitoring", "automation"],
            "status": "available"
        }
        
        result = await coordinator.register_agent(agent_info)
        assert result == True
        assert "test_agent" in coordinator.agent_status
    
    @pytest.mark.asyncio
    async def test_assign_task(self, coordinator):
        """Test assigning tasks to agents"""
        # First register an agent
        agent_info = {
            "agent_id": "test_agent",
            "capabilities": ["monitoring"],
            "status": "available"
        }
        await coordinator.register_agent(agent_info)
        
        task = {
            "task_id": "task_1",
            "type": "monitoring",
            "priority": 1
        }
        
        result = await coordinator.assign_task(task)
        assert result is not None
        assert "assigned_agent" in result or "error" in result


class TestTaskExecutor:
    """Test Skynet Task Executor"""
    
    @pytest.fixture
    def task_executor(self):
        config = {"max_retries": 3}
        return TaskExecutor(config)
    
    @pytest.mark.asyncio
    async def test_task_executor_initialization(self, task_executor):
        """Test task executor initialization"""
        assert task_executor.max_retries == 3
        assert task_executor.execution_queue is not None
        assert task_executor.results == {}
    
    @pytest.mark.asyncio
    async def test_execute_task(self, task_executor):
        """Test executing tasks"""
        task = {
            "task_id": "test_task",
            "action": "echo",
            "parameters": {"message": "Hello World"}
        }
        
        result = await task_executor.execute_task(task)
        assert result is not None
        assert "task_id" in result
        assert "status" in result
    
    @pytest.mark.asyncio
    async def test_get_execution_status(self, task_executor):
        """Test getting execution status"""
        task_id = "test_task"
        status = await task_executor.get_execution_status(task_id)
        assert status is not None
        assert "status" in status


class TestSafetySystem:
    """Test Skynet Safety System"""
    
    @pytest.fixture
    def safety_system(self):
        config = {"strict_mode": True}
        return SafetySystem(config)
    
    @pytest.mark.asyncio
    async def test_safety_system_initialization(self, safety_system):
        """Test safety system initialization"""
        assert safety_system.strict_mode == True
        assert safety_system.permissions == {}
        assert safety_system.safety_rules == {}
    
    @pytest.mark.asyncio
    async def test_check_permission(self, safety_system):
        """Test checking permissions"""
        permission = await safety_system.check_permission("system_control", "restart_service")
        assert permission is not None
        assert "allowed" in permission
        assert "reason" in permission
    
    @pytest.mark.asyncio
    async def test_validate_action(self, safety_system):
        """Test validating actions"""
        action = {
            "type": "system_control",
            "action": "restart_service",
            "parameters": {"service": "web_server"}
        }
        
        validation = await safety_system.validate_action(action)
        assert validation is not None
        assert "valid" in validation
        assert "warnings" in validation


@pytest.mark.asyncio
async def test_skynet_health_checks():
    """Test health checks for all Skynet components"""
    config = {}
    
    system_controller = SystemController(config)
    task_scheduler = TaskScheduler(config)
    system_monitor = SystemMonitor(config)
    auto_healer = AutoHealingSystem(config)
    decision_engine = DecisionEngine(config)
    coordinator = MultiAgentCoordinator(config)
    task_executor = TaskExecutor(config)
    safety_system = SafetySystem(config)
    
    # Test health checks
    controller_health = await system_controller.health_check()
    scheduler_health = await task_scheduler.health_check()
    monitor_health = await system_monitor.health_check()
    healer_health = await auto_healer.health_check()
    decision_health = await decision_engine.health_check()
    coordinator_health = await coordinator.health_check()
    executor_health = await task_executor.health_check()
    safety_health = await safety_system.health_check()
    
    assert controller_health["system_controller"] == True
    assert scheduler_health["task_scheduler"] == True
    assert monitor_health["system_monitor"] == True
    assert healer_health["auto_healing_system"] == True
    assert decision_health["decision_engine"] == True
    assert coordinator_health["multi_agent_coordinator"] == True
    assert executor_health["task_executor"] == True
    assert safety_health["safety_system"] == True
