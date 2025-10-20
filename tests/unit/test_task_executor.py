"""
Unit tests for task executor
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.core.agents.skynet.executor import TaskExecutor, TaskPriority, TaskStatus


class TestTaskExecutor:
    """Test task executor functionality"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.executor = TaskExecutor({"max_concurrent_tasks": 2, "max_retries": 2})
    
    @pytest.mark.asyncio
    async def test_submit_task(self):
        """Test task submission"""
        task_id = await self.executor.submit_task(
            "test_task",
            {"data": "test"},
            TaskPriority.NORMAL
        )
        
        assert task_id is not None
        assert task_id in self.executor.task_history
    
        task_info = self.executor.task_history[task_id]
        assert task_info["type"] == "test_task"
        assert task_info["status"] == TaskStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_task_execution_success(self):
        """Test successful task execution"""
        # Register a test handler
        async def test_handler(task_data):
            return {"result": "success", "data": task_data}
        
        self.executor.register_task("test_success", test_handler)
        
        # Submit and execute task
        task_id = await self.executor.submit_task("test_success", {"test": "data"})
        
        # Simulate task execution
        task_info = self.executor.task_history[task_id]
        await self.executor._execute_task(task_info)
        
        # Check result
        updated_task = self.executor.task_history[task_id]
        assert updated_task["status"] == TaskStatus.COMPLETED
        assert updated_task["result"]["result"] == "success"
    
    @pytest.mark.asyncio
    async def test_task_execution_failure_with_retry(self):
        """Test task execution failure with retry"""
        # Register a failing handler
        async def failing_handler(task_data):
            raise Exception("Test failure")
        
        self.executor.register_task("test_failure", failing_handler)
        
        # Submit task
        task_id = await self.executor.submit_task("test_failure", {"test": "data"})
        
        # Simulate task execution
        task_info = self.executor.task_history[task_id]
        await self.executor._execute_task(task_info)
        
        # Check that task is marked for retry
        updated_task = self.executor.task_history[task_id]
        assert updated_task["status"] == TaskStatus.RETRYING
        assert updated_task["retry_count"] == 1
    
    @pytest.mark.asyncio
    async def test_task_cancellation(self):
        """Test task cancellation"""
        task_id = await self.executor.submit_task("test_task", {"data": "test"})
        
        # Cancel the task
        cancelled = await self.executor.cancel_task(task_id)
        assert cancelled == True
        
        # Check task status
        task_info = self.executor.task_history[task_id]
        assert task_info["status"] == TaskStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_get_task_status(self):
        """Test getting task status"""
        task_id = await self.executor.submit_task("test_task", {"data": "test"})
        
        status = await self.executor.get_task_status(task_id)
        assert status is not None
        assert status["id"] == task_id
        assert status["status"] == TaskStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_get_queue_status(self):
        """Test getting queue status"""
        # Submit a few tasks
        await self.executor.submit_task("task1", {"data": "1"})
        await self.executor.submit_task("task2", {"data": "2"})
        
        status = await self.executor.get_queue_status()
        assert status["queue_size"] >= 2
        assert status["max_concurrent_tasks"] == 2
        assert status["total_tasks_processed"] >= 2
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test executor health check"""
        health = await self.executor.health_check()
        
        assert "executor_running" in health
        assert "queue_size" in health
        assert "running_tasks" in health
        assert "max_concurrent_tasks" in health
        assert "registered_task_types" in health
        assert "total_tasks_processed" in health
    
    @pytest.mark.asyncio
    async def test_start_stop_executor(self):
        """Test starting and stopping the executor"""
        # Start executor
        await self.executor.start()
        assert self.executor._is_running == True
        
        # Stop executor
        await self.executor.stop()
        assert self.executor._is_running == False
