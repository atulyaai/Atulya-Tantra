"""
Atulya Tantra - Skynet Task Executor
Version: 2.5.0
Handles execution of scheduled and autonomous tasks
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import uuid
from enum import Enum
import traceback

logger = logging.getLogger(__name__)

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

class TaskPriority(int, Enum):
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20

class TaskExecutor:
    """
    Executes tasks with priority queuing, retry logic, and resource management
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.max_concurrent_tasks = self.config.get("max_concurrent_tasks", 10)
        self.max_retries = self.config.get("max_retries", 3)
        self.retry_delay = self.config.get("retry_delay", 60)  # seconds
        
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.task_history: Dict[str, Dict[str, Any]] = {}
        self.task_registry: Dict[str, Callable] = {}
        
        self._executor_task = None
        self._is_running = False
        
        logger.info("TaskExecutor initialized with max_concurrent_tasks=%d", self.max_concurrent_tasks)
    
    async def start(self):
        """Start the task executor"""
        if self._is_running:
            logger.warning("TaskExecutor is already running")
            return
        
        self._is_running = True
        self._executor_task = asyncio.create_task(self._executor_loop())
        logger.info("TaskExecutor started")
    
    async def stop(self):
        """Stop the task executor"""
        if not self._is_running:
            logger.warning("TaskExecutor is not running")
            return
        
        self._is_running = False
        
        # Cancel all running tasks
        for task_id, task in self.running_tasks.items():
            task.cancel()
            logger.info("Cancelled running task: %s", task_id)
        
        # Cancel executor loop
        if self._executor_task:
            self._executor_task.cancel()
            try:
                await self._executor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("TaskExecutor stopped")
    
    def register_task(self, task_type: str, handler: Callable):
        """Register a task handler"""
        self.task_registry[task_type] = handler
        logger.debug("Registered task handler: %s", task_type)
    
    async def submit_task(
        self,
        task_type: str,
        task_data: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        delay: Optional[int] = None
    ) -> str:
        """
        Submit a task for execution
        
        Args:
            task_type: Type of task to execute
            task_data: Task-specific data
            priority: Task priority
            delay: Delay in seconds before execution
            
        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        
        task_info = {
            "id": task_id,
            "type": task_type,
            "data": task_data,
            "priority": priority,
            "status": TaskStatus.PENDING,
            "created_at": datetime.now().isoformat(),
            "retry_count": 0,
            "delay": delay
        }
        
        # Store in history
        self.task_history[task_id] = task_info
        
        # Add to queue
        await self.task_queue.put((priority.value, task_info))
        
        logger.info("Task submitted: %s (type: %s, priority: %s)", task_id, task_type, priority.name)
        return task_id
    
    async def _executor_loop(self):
        """Main executor loop"""
        logger.info("Task executor loop started")
        
        while self._is_running:
            try:
                # Check if we can run more tasks
                if len(self.running_tasks) >= self.max_concurrent_tasks:
                    await asyncio.sleep(1)
                    continue
                
                # Get next task from queue
                try:
                    priority, task_info = await asyncio.wait_for(
                        self.task_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Check if task should be delayed
                if task_info.get("delay"):
                    await asyncio.sleep(task_info["delay"])
                
                # Execute task
                task_id = task_info["id"]
                self.running_tasks[task_id] = asyncio.create_task(
                    self._execute_task(task_info)
                )
                
            except Exception as e:
                logger.error("Error in executor loop: %s", e)
                await asyncio.sleep(1)
        
        logger.info("Task executor loop stopped")
    
    async def _execute_task(self, task_info: Dict[str, Any]):
        """Execute a single task"""
        task_id = task_info["id"]
        task_type = task_info["type"]
        task_data = task_info["data"]
        
        logger.info("Executing task: %s (type: %s)", task_id, task_type)
        
        try:
            # Update status
            self.task_history[task_id]["status"] = TaskStatus.RUNNING
            self.task_history[task_id]["started_at"] = datetime.now().isoformat()
            
            # Get task handler
            handler = self.task_registry.get(task_type)
            if not handler:
                raise ValueError(f"No handler registered for task type: {task_type}")
            
            # Execute task
            result = await handler(task_data)
            
            # Update status
            self.task_history[task_id]["status"] = TaskStatus.COMPLETED
            self.task_history[task_id]["completed_at"] = datetime.now().isoformat()
            self.task_history[task_id]["result"] = result
            
            logger.info("Task completed successfully: %s", task_id)
            
        except Exception as e:
            logger.error("Task failed: %s - %s", task_id, e)
            
            # Update status
            self.task_history[task_id]["status"] = TaskStatus.FAILED
            self.task_history[task_id]["failed_at"] = datetime.now().isoformat()
            self.task_history[task_id]["error"] = str(e)
            self.task_history[task_id]["traceback"] = traceback.format_exc()
            
            # Check if we should retry
            retry_count = self.task_history[task_id]["retry_count"]
            if retry_count < self.max_retries:
                logger.info("Retrying task: %s (attempt %d/%d)", task_id, retry_count + 1, self.max_retries)
                
                # Update retry count
                self.task_history[task_id]["retry_count"] = retry_count + 1
                self.task_history[task_id]["status"] = TaskStatus.RETRYING
                
                # Reschedule task with delay
                await asyncio.sleep(self.retry_delay)
                await self.task_queue.put((
                    self.task_history[task_id]["priority"].value,
                    self.task_history[task_id]
                ))
            else:
                logger.error("Task failed permanently: %s (max retries exceeded)", task_id)
        
        finally:
            # Remove from running tasks
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task"""
        if task_id in self.running_tasks:
            # Cancel running task
            self.running_tasks[task_id].cancel()
            del self.running_tasks[task_id]
            
            # Update status
            if task_id in self.task_history:
                self.task_history[task_id]["status"] = TaskStatus.CANCELLED
                self.task_history[task_id]["cancelled_at"] = datetime.now().isoformat()
            
            logger.info("Cancelled running task: %s", task_id)
            return True
        
        # Check if task is in queue (this is more complex with PriorityQueue)
        # For now, we'll mark it as cancelled in history
        if task_id in self.task_history:
            if self.task_history[task_id]["status"] == TaskStatus.PENDING:
                self.task_history[task_id]["status"] = TaskStatus.CANCELLED
                self.task_history[task_id]["cancelled_at"] = datetime.now().isoformat()
                logger.info("Cancelled pending task: %s", task_id)
                return True
        
        return False
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific task"""
        return self.task_history.get(task_id)
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        return {
            "queue_size": self.task_queue.qsize(),
            "running_tasks": len(self.running_tasks),
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "total_tasks_processed": len(self.task_history),
            "pending_tasks": sum(1 for t in self.task_history.values() if t["status"] == TaskStatus.PENDING),
            "running_task_ids": list(self.running_tasks.keys())
        }
    
    async def get_task_history(
        self,
        limit: int = 100,
        status_filter: Optional[TaskStatus] = None
    ) -> List[Dict[str, Any]]:
        """Get task history with optional filtering"""
        tasks = list(self.task_history.values())
        
        # Filter by status if specified
        if status_filter:
            tasks = [t for t in tasks if t["status"] == status_filter]
        
        # Sort by creation time (newest first)
        tasks.sort(key=lambda x: x["created_at"], reverse=True)
        
        # Limit results
        return tasks[:limit]
    
    async def health_check(self) -> Dict[str, Any]:
        """Get executor health status"""
        return {
            "executor_running": self._is_running,
            "queue_size": self.task_queue.qsize(),
            "running_tasks": len(self.running_tasks),
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "registered_task_types": list(self.task_registry.keys()),
            "total_tasks_processed": len(self.task_history)
        }


# Global task executor instance
task_executor = TaskExecutor()

# Register default task handlers
async def default_task_handler(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """Default task handler for testing"""
    logger.info("Executing default task with data: %s", task_data)
    await asyncio.sleep(1)  # Simulate work
    return {"status": "completed", "message": "Default task completed"}

task_executor.register_task("default", default_task_handler)

async def system_health_check_handler(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """System health check task handler"""
    from .system_monitor import SystemMonitor
    
    monitor = SystemMonitor()
    health = await monitor.get_system_health()
    
    return {
        "status": "completed",
        "health_check": health,
        "timestamp": datetime.now().isoformat()
    }

task_executor.register_task("system_health_check", system_health_check_handler)

async def cleanup_handler(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """Cleanup task handler"""
    # Simulate cleanup operations
    await asyncio.sleep(2)
    
    return {
        "status": "completed",
        "message": "Cleanup completed",
        "cleaned_items": 42
    }

task_executor.register_task("cleanup", cleanup_handler)
