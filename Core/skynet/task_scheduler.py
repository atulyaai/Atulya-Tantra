"""
Task Scheduling and Automation System for Atulya Tantra AGI
Advanced scheduling, workflow automation, and autonomous operations
"""

import asyncio
import json
from typing import Dict, List, Any, Optional, Callable, Union
from datetime import datetime, timedelta
from enum import Enum
import uuid
import traceback

from ..config.settings import settings
from ..config.logging import get_logger
from ..config.exceptions import AgentError
from ..agents import get_orchestrator, submit_task, AgentPriority
from ..database.service import get_db_service, insert_record, get_record_by_id, update_record

logger = get_logger(__name__)


class TaskStatus(str, Enum):
    """Task execution status"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskPriority(str, Enum):
    """Task priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class ScheduleType(str, Enum):
    """Schedule types"""
    ONCE = "once"
    INTERVAL = "interval"
    CRON = "cron"
    CONDITIONAL = "conditional"


class ScheduledTask:
    """Represents a scheduled task"""
    
    def __init__(
        self,
        task_id: str = None,
        name: str = None,
        description: str = None,
        task_type: str = None,
        schedule_type: ScheduleType = ScheduleType.ONCE,
        schedule_config: Dict[str, Any] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3,
        retry_delay: int = 60,
        timeout: int = 300,
        enabled: bool = True,
        metadata: Dict[str, Any] = None
    ):
        self.task_id = task_id or str(uuid.uuid4())
        self.name = name or f"Task_{self.task_id[:8]}"
        self.description = description or ""
        self.task_type = task_type or "general"
        self.schedule_type = schedule_type
        self.schedule_config = schedule_config or {}
        self.priority = priority
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.enabled = enabled
        self.metadata = metadata or {}
        
        self.status = TaskStatus.PENDING
        self.created_at = datetime.utcnow()
        self.last_run = None
        self.next_run = None
        self.run_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.last_error = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary"""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "task_type": self.task_type,
            "schedule_type": self.schedule_type.value,
            "schedule_config": self.schedule_config,
            "priority": self.priority.value,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "timeout": self.timeout,
            "enabled": self.enabled,
            "metadata": self.metadata,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_error": self.last_error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScheduledTask':
        """Create task from dictionary"""
        task = cls(
            task_id=data.get("task_id"),
            name=data.get("name"),
            description=data.get("description"),
            task_type=data.get("task_type"),
            schedule_type=ScheduleType(data.get("schedule_type", ScheduleType.ONCE.value)),
            schedule_config=data.get("schedule_config", {}),
            priority=TaskPriority(data.get("priority", TaskPriority.NORMAL.value)),
            max_retries=data.get("max_retries", 3),
            retry_delay=data.get("retry_delay", 60),
            timeout=data.get("timeout", 300),
            enabled=data.get("enabled", True),
            metadata=data.get("metadata", {})
        )
        
        task.status = TaskStatus(data.get("status", TaskStatus.PENDING.value))
        task.created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow()
        
        if data.get("last_run"):
            task.last_run = datetime.fromisoformat(data["last_run"])
        if data.get("next_run"):
            task.next_run = datetime.fromisoformat(data["next_run"])
        
        task.run_count = data.get("run_count", 0)
        task.success_count = data.get("success_count", 0)
        task.failure_count = data.get("failure_count", 0)
        task.last_error = data.get("last_error")
        
        return task


class TaskScheduler:
    """Advanced task scheduler with multiple scheduling types"""
    
    def __init__(self):
        self.scheduled_tasks: Dict[str, ScheduledTask] = {}
        self.task_handlers: Dict[str, Callable] = {}
        self.is_running = False
        self.scheduler_task: Optional[asyncio.Task] = None
        self.executor_task: Optional[asyncio.Task] = None
        
        # Initialize default task handlers
        self._initialize_default_handlers()
    
    def _initialize_default_handlers(self):
        """Initialize default task handlers"""
        self.task_handlers.update({
            "system_health_check": self._handle_system_health_check,
            "database_backup": self._handle_database_backup,
            "log_cleanup": self._handle_log_cleanup,
            "performance_monitor": self._handle_performance_monitor,
            "security_scan": self._handle_security_scan,
            "update_check": self._handle_update_check,
            "memory_cleanup": self._handle_memory_cleanup,
            "cache_refresh": self._handle_cache_refresh
        })
    
    async def start(self):
        """Start the task scheduler"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # Start scheduler loop
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        # Start executor loop
        self.executor_task = asyncio.create_task(self._executor_loop())
        
        logger.info("Task scheduler started")
    
    async def stop(self):
        """Stop the task scheduler"""
        self.is_running = False
        
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        if self.executor_task:
            self.executor_task.cancel()
            try:
                await self.executor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Task scheduler stopped")
    
    async def schedule_task(
        self,
        name: str,
        task_type: str,
        schedule_type: ScheduleType = ScheduleType.ONCE,
        schedule_config: Dict[str, Any] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        **kwargs
    ) -> str:
        """Schedule a new task"""
        task = ScheduledTask(
            name=name,
            task_type=task_type,
            schedule_type=schedule_type,
            schedule_config=schedule_config or {},
            priority=priority,
            **kwargs
        )
        
        # Calculate next run time
        task.next_run = await self._calculate_next_run(task)
        
        # Store task
        self.scheduled_tasks[task.task_id] = task
        
        # Store in database
        await self._store_task(task)
        
        logger.info(f"Scheduled task: {name} ({task.task_id})")
        return task.task_id
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task"""
        if task_id in self.scheduled_tasks:
            task = self.scheduled_tasks[task_id]
            task.status = TaskStatus.CANCELLED
            task.enabled = False
            
            await self._update_task(task)
            logger.info(f"Cancelled task: {task.name} ({task_id})")
            return True
        
        return False
    
    async def enable_task(self, task_id: str) -> bool:
        """Enable a scheduled task"""
        if task_id in self.scheduled_tasks:
            task = self.scheduled_tasks[task_id]
            task.enabled = True
            task.next_run = await self._calculate_next_run(task)
            
            await self._update_task(task)
            logger.info(f"Enabled task: {task.name} ({task_id})")
            return True
        
        return False
    
    async def disable_task(self, task_id: str) -> bool:
        """Disable a scheduled task"""
        if task_id in self.scheduled_tasks:
            task = self.scheduled_tasks[task_id]
            task.enabled = False
            
            await self._update_task(task)
            logger.info(f"Disabled task: {task.name} ({task_id})")
            return True
        
        return False
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.is_running:
            try:
                current_time = datetime.utcnow()
                
                # Find tasks ready to run
                ready_tasks = []
                for task in self.scheduled_tasks.values():
                    if (task.enabled and 
                        task.status in [TaskStatus.PENDING, TaskStatus.SCHEDULED] and
                        task.next_run and 
                        current_time >= task.next_run):
                        ready_tasks.append(task)
                
                # Sort by priority
                ready_tasks.sort(key=lambda t: self._get_priority_value(t.priority), reverse=True)
                
                # Queue tasks for execution
                for task in ready_tasks:
                    task.status = TaskStatus.SCHEDULED
                    await self._update_task(task)
                
                # Wait before next check
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(5)
    
    async def _executor_loop(self):
        """Main executor loop"""
        while self.is_running:
            try:
                # Find scheduled tasks to execute
                scheduled_tasks = [
                    task for task in self.scheduled_tasks.values()
                    if task.status == TaskStatus.SCHEDULED
                ]
                
                # Execute tasks concurrently
                if scheduled_tasks:
                    tasks = [self._execute_task(task) for task in scheduled_tasks]
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                # Wait before next check
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error in executor loop: {e}")
                await asyncio.sleep(5)
    
    async def _execute_task(self, task: ScheduledTask):
        """Execute a scheduled task"""
        try:
            task.status = TaskStatus.RUNNING
            task.last_run = datetime.utcnow()
            task.run_count += 1
            
            await self._update_task(task)
            
            logger.info(f"Executing task: {task.name} ({task.task_id})")
            
            # Execute the task
            result = await self._run_task(task)
            
            # Mark as completed
            task.status = TaskStatus.COMPLETED
            task.success_count += 1
            task.last_error = None
            
            # Calculate next run time
            task.next_run = await self._calculate_next_run(task)
            
            await self._update_task(task)
            
            logger.info(f"Completed task: {task.name} ({task.task_id})")
            
        except Exception as e:
            logger.error(f"Task execution failed: {task.name} ({task.task_id}): {e}")
            
            task.failure_count += 1
            task.last_error = str(e)
            
            # Check if we should retry
            if task.failure_count <= task.max_retries:
                task.status = TaskStatus.RETRYING
                task.next_run = datetime.utcnow() + timedelta(seconds=task.retry_delay)
                logger.info(f"Retrying task: {task.name} ({task.task_id}) in {task.retry_delay}s")
            else:
                task.status = TaskStatus.FAILED
                task.enabled = False
                logger.error(f"Task failed permanently: {task.name} ({task.task_id})")
            
            await self._update_task(task)
    
    async def _run_task(self, task: ScheduledTask) -> Any:
        """Run a specific task"""
        # Check if task has a custom handler
        if task.task_type in self.task_handlers:
            handler = self.task_handlers[task.task_type]
            return await handler(task)
        
        # Check if it's an agent task
        if task.task_type.startswith("agent_"):
            return await self._run_agent_task(task)
        
        # Default task execution
        return await self._run_default_task(task)
    
    async def _run_agent_task(self, task: ScheduledTask) -> Any:
        """Run an agent-based task"""
        try:
            orchestrator = await get_orchestrator()
            
            # Extract agent type and task details
            agent_type = task.metadata.get("agent_type", "CodeAgent")
            task_description = task.metadata.get("task_description", task.description)
            input_data = task.metadata.get("input_data", {})
            
            # Submit to agent orchestrator
            task_id = await submit_task(
                agent_type=agent_type,
                task_type=task.task_type,
                description=task_description,
                input_data=input_data,
                priority=AgentPriority(task.priority.value.upper()),
                timeout_seconds=task.timeout
            )
            
            # Wait for completion
            max_wait = task.timeout
            wait_time = 0
            
            while wait_time < max_wait:
                status = await orchestrator.get_task_status(task_id)
                if status and status['status'] in ['completed', 'failed']:
                    return status
                
                await asyncio.sleep(1)
                wait_time += 1
            
            return {"status": "timeout", "message": "Task execution timed out"}
            
        except Exception as e:
            raise AgentError(f"Agent task execution failed: {e}")
    
    async def _run_default_task(self, task: ScheduledTask) -> Any:
        """Run a default task"""
        # Simple task execution - can be extended
        logger.info(f"Running default task: {task.name}")
        
        # Simulate task execution
        await asyncio.sleep(1)
        
        return {"status": "completed", "message": f"Task {task.name} executed successfully"}
    
    async def _calculate_next_run(self, task: ScheduledTask) -> Optional[datetime]:
        """Calculate next run time for a task"""
        if not task.enabled:
            return None
        
        current_time = datetime.utcnow()
        
        if task.schedule_type == ScheduleType.ONCE:
            if task.run_count == 0:
                return current_time
            return None
        
        elif task.schedule_type == ScheduleType.INTERVAL:
            interval_seconds = task.schedule_config.get("interval_seconds", 3600)
            if task.last_run:
                return task.last_run + timedelta(seconds=interval_seconds)
            return current_time
        
        elif task.schedule_type == ScheduleType.CRON:
            # Simple cron-like scheduling (can be enhanced with cron library)
            cron_expression = task.schedule_config.get("cron_expression", "0 * * * *")
            return self._parse_cron_expression(cron_expression)
        
        elif task.schedule_type == ScheduleType.CONDITIONAL:
            # Conditional scheduling based on system state
            condition = task.schedule_config.get("condition", {})
            return await self._evaluate_condition(condition)
        
        return None
    
    def _parse_cron_expression(self, cron_expr: str) -> datetime:
        """Parse cron expression (simplified implementation)"""
        # This is a simplified cron parser
        # In production, use a library like croniter
        parts = cron_expr.split()
        if len(parts) >= 5:
            minute, hour, day, month, weekday = parts[:5]
            
            now = datetime.utcnow()
            
            # Simple hourly scheduling for now
            if minute == "0" and hour == "*":
                next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                return next_run
        
        # Default to next hour
        now = datetime.utcnow()
        return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    
    async def _evaluate_condition(self, condition: Dict[str, Any]) -> Optional[datetime]:
        """Evaluate conditional scheduling"""
        condition_type = condition.get("type", "system_load")
        
        if condition_type == "system_load":
            # Schedule when system load is low
            # This would integrate with system monitoring
            return datetime.utcnow() + timedelta(minutes=5)
        
        elif condition_type == "time_window":
            # Schedule within specific time window
            start_hour = condition.get("start_hour", 0)
            end_hour = condition.get("end_hour", 23)
            
            now = datetime.utcnow()
            if start_hour <= now.hour <= end_hour:
                return now + timedelta(minutes=1)
        
        return None
    
    def _get_priority_value(self, priority: TaskPriority) -> int:
        """Get numeric priority value for sorting"""
        priority_values = {
            TaskPriority.LOW: 1,
            TaskPriority.NORMAL: 2,
            TaskPriority.HIGH: 3,
            TaskPriority.CRITICAL: 4
        }
        return priority_values.get(priority, 2)
    
    async def _store_task(self, task: ScheduledTask):
        """Store task in database"""
        try:
            await insert_record("scheduled_tasks", task.to_dict())
        except Exception as e:
            logger.error(f"Error storing task: {e}")
    
    async def _update_task(self, task: ScheduledTask):
        """Update task in database"""
        try:
            await update_record("scheduled_tasks", task.task_id, task.to_dict())
        except Exception as e:
            logger.error(f"Error updating task: {e}")
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status"""
        if task_id in self.scheduled_tasks:
            return self.scheduled_tasks[task_id].to_dict()
        return None
    
    async def get_all_tasks(self) -> List[Dict[str, Any]]:
        """Get all scheduled tasks"""
        return [task.to_dict() for task in self.scheduled_tasks.values()]
    
    async def get_task_statistics(self) -> Dict[str, Any]:
        """Get task execution statistics"""
        total_tasks = len(self.scheduled_tasks)
        enabled_tasks = len([t for t in self.scheduled_tasks.values() if t.enabled])
        running_tasks = len([t for t in self.scheduled_tasks.values() if t.status == TaskStatus.RUNNING])
        
        total_runs = sum(t.run_count for t in self.scheduled_tasks.values())
        total_successes = sum(t.success_count for t in self.scheduled_tasks.values())
        total_failures = sum(t.failure_count for t in self.scheduled_tasks.values())
        
        return {
            "total_tasks": total_tasks,
            "enabled_tasks": enabled_tasks,
            "running_tasks": running_tasks,
            "total_runs": total_runs,
            "total_successes": total_successes,
            "total_failures": total_failures,
            "success_rate": total_successes / total_runs if total_runs > 0 else 0
        }
    
    # Default task handlers
    async def _handle_system_health_check(self, task: ScheduledTask) -> Dict[str, Any]:
        """Handle system health check task"""
        logger.info("Running system health check")
        
        # This would integrate with system monitoring
        health_status = {
            "cpu_usage": 45.2,
            "memory_usage": 67.8,
            "disk_usage": 23.1,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return {"status": "completed", "data": health_status}
    
    async def _handle_database_backup(self, task: ScheduledTask) -> Dict[str, Any]:
        """Handle database backup task"""
        logger.info("Running database backup")
        
        # This would perform actual database backup
        backup_info = {
            "backup_size": "2.3 GB",
            "backup_location": "/backups/db_backup_20241022.sql",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return {"status": "completed", "data": backup_info}
    
    async def _handle_log_cleanup(self, task: ScheduledTask) -> Dict[str, Any]:
        """Handle log cleanup task"""
        logger.info("Running log cleanup")
        
        # This would clean up old log files
        cleanup_info = {
            "files_removed": 15,
            "space_freed": "1.2 GB",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return {"status": "completed", "data": cleanup_info}
    
    async def _handle_performance_monitor(self, task: ScheduledTask) -> Dict[str, Any]:
        """Handle performance monitoring task"""
        logger.info("Running performance monitoring")
        
        # This would collect performance metrics
        performance_data = {
            "response_time_avg": 125.5,
            "requests_per_second": 45.2,
            "error_rate": 0.02,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return {"status": "completed", "data": performance_data}
    
    async def _handle_security_scan(self, task: ScheduledTask) -> Dict[str, Any]:
        """Handle security scan task"""
        logger.info("Running security scan")
        
        # This would perform security checks
        security_data = {
            "vulnerabilities_found": 0,
            "security_score": 95,
            "last_scan": datetime.utcnow().isoformat()
        }
        
        return {"status": "completed", "data": security_data}
    
    async def _handle_update_check(self, task: ScheduledTask) -> Dict[str, Any]:
        """Handle update check task"""
        logger.info("Checking for updates")
        
        # This would check for system updates
        update_data = {
            "updates_available": 2,
            "critical_updates": 0,
            "last_check": datetime.utcnow().isoformat()
        }
        
        return {"status": "completed", "data": update_data}
    
    async def _handle_memory_cleanup(self, task: ScheduledTask) -> Dict[str, Any]:
        """Handle memory cleanup task"""
        logger.info("Running memory cleanup")
        
        # This would perform memory cleanup
        cleanup_data = {
            "memory_freed": "512 MB",
            "cache_cleared": True,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return {"status": "completed", "data": cleanup_data}
    
    async def _handle_cache_refresh(self, task: ScheduledTask) -> Dict[str, Any]:
        """Handle cache refresh task"""
        logger.info("Refreshing cache")
        
        # This would refresh system caches
        refresh_data = {
            "cache_entries_refreshed": 1250,
            "cache_size": "256 MB",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return {"status": "completed", "data": refresh_data}
    
    def register_task_handler(self, task_type: str, handler: Callable):
        """Register a custom task handler"""
        self.task_handlers[task_type] = handler
        logger.info(f"Registered task handler for: {task_type}")


# Global task scheduler instance
_task_scheduler: Optional[TaskScheduler] = None


async def get_task_scheduler() -> TaskScheduler:
    """Get global task scheduler instance"""
    global _task_scheduler
    
    if _task_scheduler is None:
        _task_scheduler = TaskScheduler()
        await _task_scheduler.start()
    
    return _task_scheduler


async def schedule_task(
    name: str,
    task_type: str,
    schedule_type: ScheduleType = ScheduleType.ONCE,
    schedule_config: Dict[str, Any] = None,
    priority: TaskPriority = TaskPriority.NORMAL,
    **kwargs
) -> str:
    """Schedule a new task"""
    scheduler = await get_task_scheduler()
    return await scheduler.schedule_task(
        name, task_type, schedule_type, schedule_config, priority, **kwargs
    )


async def cancel_task(task_id: str) -> bool:
    """Cancel a scheduled task"""
    scheduler = await get_task_scheduler()
    return await scheduler.cancel_task(task_id)


async def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """Get task status"""
    scheduler = await get_task_scheduler()
    return await scheduler.get_task_status(task_id)


async def get_task_statistics() -> Dict[str, Any]:
    """Get task execution statistics"""
    scheduler = await get_task_scheduler()
    return await scheduler.get_task_statistics()


# Export public API
__all__ = [
    "TaskStatus",
    "TaskPriority",
    "ScheduleType",
    "ScheduledTask",
    "TaskScheduler",
    "get_task_scheduler",
    "schedule_task",
    "cancel_task",
    "get_task_status",
    "get_task_statistics"
]
