"""
Atulya Tantra - Skynet Task Scheduler
Version: 2.5.0
Task scheduling and execution system for autonomous operations
"""

import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import json
import uuid
import asyncio
from collections import defaultdict, deque
import threading
import time
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskPriority(Enum):
    """Task priority levels"""
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


class TriggerType(Enum):
    """Task trigger types"""
    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"
    RECURRING = "recurring"
    EVENT_DRIVEN = "event_driven"
    CONDITIONAL = "conditional"


@dataclass
class Task:
    """Task definition"""
    task_id: str
    name: str
    description: str
    function_name: str
    parameters: Dict[str, Any]
    priority: TaskPriority
    trigger_type: TriggerType
    trigger_config: Dict[str, Any]
    max_retries: int
    timeout_seconds: int
    created_at: datetime
    scheduled_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    status: TaskStatus
    error_message: Optional[str]
    retry_count: int
    dependencies: List[str]  # task_ids
    metadata: Dict[str, Any]


@dataclass
class TaskResult:
    """Task execution result"""
    task_id: str
    success: bool
    result: Any
    error_message: Optional[str]
    execution_time: float
    timestamp: datetime
    metadata: Dict[str, Any]


class TaskScheduler:
    """Advanced task scheduler for autonomous operations"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.tasks = {}  # task_id -> Task
        self.task_queue = deque()
        self.running_tasks = {}  # task_id -> asyncio.Task
        self.completed_tasks = deque(maxlen=1000)  # Keep last 1000 completed tasks
        self.event_handlers = {}  # event_type -> List[Callable]
        self.conditions = {}  # condition_name -> Callable
        self.executor = ThreadPoolExecutor(max_workers=config.get("max_workers", 10))
        self.is_running = False
        self.scheduler_thread = None
        self.lock = threading.Lock()
        
        # Statistics
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "cancelled_tasks": 0,
            "average_execution_time": 0.0
        }
        
        logger.info("TaskScheduler initialized")
    
    async def start(self):
        """Start the task scheduler"""
        
        if self.is_running:
            return {"error": "Scheduler already running"}
        
        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("Task scheduler started")
        return {"success": True, "status": "started"}
    
    async def stop(self):
        """Stop the task scheduler"""
        
        if not self.is_running:
            return {"error": "Scheduler not running"}
        
        self.is_running = False
        
        # Cancel all running tasks
        for task_id, task in list(self.running_tasks.items()):
            await self.cancel_task(task_id)
        
        # Wait for scheduler thread to finish
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        logger.info("Task scheduler stopped")
        return {"success": True, "status": "stopped"}
    
    async def schedule_task(
        self,
        name: str,
        description: str,
        function_name: str,
        parameters: Dict[str, Any] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        trigger_type: TriggerType = TriggerType.IMMEDIATE,
        trigger_config: Dict[str, Any] = None,
        max_retries: int = 3,
        timeout_seconds: int = 300,
        dependencies: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Schedule a new task"""
        
        task_id = str(uuid.uuid4())
        now = datetime.now()
        
        # Calculate scheduled time based on trigger
        scheduled_at = None
        if trigger_type == TriggerType.SCHEDULED:
            scheduled_at = trigger_config.get("scheduled_time")
        elif trigger_type == TriggerType.RECURRING:
            scheduled_at = now + timedelta(seconds=trigger_config.get("interval_seconds", 60))
        
        task = Task(
            task_id=task_id,
            name=name,
            description=description,
            function_name=function_name,
            parameters=parameters or {},
            priority=priority,
            trigger_type=trigger_type,
            trigger_config=trigger_config or {},
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            created_at=now,
            scheduled_at=scheduled_at,
            started_at=None,
            completed_at=None,
            status=TaskStatus.PENDING,
            error_message=None,
            retry_count=0,
            dependencies=dependencies or [],
            metadata=metadata or {}
        )
        
        with self.lock:
            self.tasks[task_id] = task
            self.stats["total_tasks"] += 1
        
        # Add to queue if immediate or ready to run
        if trigger_type == TriggerType.IMMEDIATE:
            await self._add_to_queue(task)
        elif trigger_type == TriggerType.SCHEDULED and scheduled_at <= now:
            await self._add_to_queue(task)
        
        logger.info(f"Scheduled task: {name} ({task_id})")
        return task_id
    
    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Cancel a scheduled or running task"""
        
        with self.lock:
            if task_id not in self.tasks:
                return {"error": "Task not found"}
            
            task = self.tasks[task_id]
            
            if task.status == TaskStatus.RUNNING:
                # Cancel running task
                if task_id in self.running_tasks:
                    self.running_tasks[task_id].cancel()
                    del self.running_tasks[task_id]
            
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            self.stats["cancelled_tasks"] += 1
            
            # Remove from queue if pending
            if task_id in [t.task_id for t in self.task_queue]:
                self.task_queue = deque([t for t in self.task_queue if t.task_id != task_id])
        
        logger.info(f"Cancelled task: {task_id}")
        return {"success": True, "task_id": task_id}
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a specific task"""
        
        with self.lock:
            if task_id not in self.tasks:
                return {"error": "Task not found"}
            
            task = self.tasks[task_id]
            
            return {
                "task_id": task_id,
                "name": task.name,
                "status": task.status.value,
                "created_at": task.created_at.isoformat(),
                "scheduled_at": task.scheduled_at.isoformat() if task.scheduled_at else None,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "retry_count": task.retry_count,
                "error_message": task.error_message,
                "metadata": task.metadata
            }
    
    async def get_scheduler_status(self) -> Dict[str, Any]:
        """Get overall scheduler status"""
        
        with self.lock:
            pending_count = len(self.task_queue)
            running_count = len(self.running_tasks)
            completed_count = self.stats["completed_tasks"]
            failed_count = self.stats["failed_tasks"]
            
            return {
                "is_running": self.is_running,
                "pending_tasks": pending_count,
                "running_tasks": running_count,
                "completed_tasks": completed_count,
                "failed_tasks": failed_count,
                "total_tasks": self.stats["total_tasks"],
                "average_execution_time": self.stats["average_execution_time"],
                "uptime": time.time() - self.start_time if hasattr(self, 'start_time') else 0
            }
    
    async def register_event_handler(self, event_type: str, handler: Callable):
        """Register an event handler"""
        
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        
        self.event_handlers[event_type].append(handler)
        logger.info(f"Registered event handler for: {event_type}")
    
    async def register_condition(self, condition_name: str, condition_func: Callable):
        """Register a condition function"""
        
        self.conditions[condition_name] = condition_func
        logger.info(f"Registered condition: {condition_name}")
    
    async def trigger_event(self, event_type: str, event_data: Dict[str, Any]):
        """Trigger an event"""
        
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    await handler(event_data)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}")
        
        # Check for event-driven tasks
        await self._check_event_driven_tasks(event_type, event_data)
    
    async def check_conditions(self, condition_name: str) -> bool:
        """Check if a condition is met"""
        
        if condition_name in self.conditions:
            try:
                return await self.conditions[condition_name]()
            except Exception as e:
                logger.error(f"Error checking condition {condition_name}: {e}")
                return False
        
        return False
    
    async def get_task_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get task execution history"""
        
        history = []
        
        # Add completed tasks from memory
        for result in list(self.completed_tasks)[-limit:]:
            history.append({
                "task_id": result.task_id,
                "success": result.success,
                "execution_time": result.execution_time,
                "timestamp": result.timestamp.isoformat(),
                "error_message": result.error_message
            })
        
        # Add current tasks
        with self.lock:
            for task in self.tasks.values():
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    history.append({
                        "task_id": task.task_id,
                        "name": task.name,
                        "status": task.status.value,
                        "created_at": task.created_at.isoformat(),
                        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                        "retry_count": task.retry_count,
                        "error_message": task.error_message
                    })
        
        # Sort by timestamp
        history.sort(key=lambda x: x.get("timestamp", x.get("completed_at", "")), reverse=True)
        
        return history[:limit]
    
    def _run_scheduler(self):
        """Main scheduler loop (runs in separate thread)"""
        
        self.start_time = time.time()
        
        while self.is_running:
            try:
                # Process scheduled tasks
                asyncio.run(self._process_scheduled_tasks())
                
                # Process pending tasks
                asyncio.run(self._process_pending_tasks())
                
                # Check recurring tasks
                asyncio.run(self._check_recurring_tasks())
                
                # Check conditional tasks
                asyncio.run(self._check_conditional_tasks())
                
                # Sleep for a short interval
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(5)
    
    async def _process_scheduled_tasks(self):
        """Process tasks that are scheduled to run now"""
        
        now = datetime.now()
        tasks_to_run = []
        
        with self.lock:
            for task in self.tasks.values():
                if (task.status == TaskStatus.PENDING and
                    task.trigger_type == TriggerType.SCHEDULED and
                    task.scheduled_at and
                    task.scheduled_at <= now):
                    tasks_to_run.append(task)
        
        for task in tasks_to_run:
            await self._add_to_queue(task)
    
    async def _process_pending_tasks(self):
        """Process tasks in the queue"""
        
        if not self.task_queue:
            return
        
        # Sort by priority
        sorted_tasks = sorted(self.task_queue, key=lambda t: t.priority.value, reverse=True)
        
        for task in sorted_tasks:
            # Check dependencies
            if await self._check_dependencies(task):
                await self._execute_task(task)
                break  # Process one task at a time
    
    async def _check_recurring_tasks(self):
        """Check for recurring tasks that need to be rescheduled"""
        
        now = datetime.now()
        
        with self.lock:
            for task in self.tasks.values():
                if (task.trigger_type == TriggerType.RECURRING and
                    task.status == TaskStatus.COMPLETED):
                    
                    interval = task.trigger_config.get("interval_seconds", 60)
                    next_run = task.completed_at + timedelta(seconds=interval)
                    
                    if next_run <= now:
                        # Create new task instance for next run
                        new_task = Task(
                            task_id=str(uuid.uuid4()),
                            name=task.name,
                            description=task.description,
                            function_name=task.function_name,
                            parameters=task.parameters,
                            priority=task.priority,
                            trigger_type=task.trigger_type,
                            trigger_config=task.trigger_config,
                            max_retries=task.max_retries,
                            timeout_seconds=task.timeout_seconds,
                            created_at=now,
                            scheduled_at=now,
                            started_at=None,
                            completed_at=None,
                            status=TaskStatus.PENDING,
                            error_message=None,
                            retry_count=0,
                            dependencies=task.dependencies,
                            metadata=task.metadata
                        )
                        
                        self.tasks[new_task.task_id] = new_task
                        await self._add_to_queue(new_task)
    
    async def _check_conditional_tasks(self):
        """Check conditional tasks"""
        
        with self.lock:
            for task in self.tasks.values():
                if (task.trigger_type == TriggerType.CONDITIONAL and
                    task.status == TaskStatus.PENDING):
                    
                    condition_name = task.trigger_config.get("condition")
                    if condition_name and await self.check_conditions(condition_name):
                        await self._add_to_queue(task)
    
    async def _check_event_driven_tasks(self, event_type: str, event_data: Dict[str, Any]):
        """Check for event-driven tasks"""
        
        with self.lock:
            for task in self.tasks.values():
                if (task.trigger_type == TriggerType.EVENT_DRIVEN and
                    task.status == TaskStatus.PENDING):
                    
                    required_event = task.trigger_config.get("event_type")
                    if required_event == event_type:
                        # Check event conditions if specified
                        conditions = task.trigger_config.get("conditions", {})
                        conditions_met = True
                        
                        for key, value in conditions.items():
                            if event_data.get(key) != value:
                                conditions_met = False
                                break
                        
                        if conditions_met:
                            await self._add_to_queue(task)
    
    async def _check_dependencies(self, task: Task) -> bool:
        """Check if task dependencies are satisfied"""
        
        if not task.dependencies:
            return True
        
        with self.lock:
            for dep_id in task.dependencies:
                if dep_id not in self.tasks:
                    return False
                
                dep_task = self.tasks[dep_id]
                if dep_task.status != TaskStatus.COMPLETED:
                    return False
        
        return True
    
    async def _add_to_queue(self, task: Task):
        """Add task to execution queue"""
        
        with self.lock:
            # Remove from queue if already there
            self.task_queue = deque([t for t in self.task_queue if t.task_id != task.task_id])
            
            # Add to queue
            self.task_queue.append(task)
    
    async def _execute_task(self, task: Task):
        """Execute a task"""
        
        # Remove from queue
        with self.lock:
            self.task_queue = deque([t for t in self.task_queue if t.task_id != task.task_id])
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
        
        # Execute in thread pool
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(
            self.executor,
            self._run_task_function,
            task
        )
        
        self.running_tasks[task.task_id] = future
        
        try:
            result = await asyncio.wait_for(future, timeout=task.timeout_seconds)
            await self._handle_task_completion(task, result)
        except asyncio.TimeoutError:
            await self._handle_task_failure(task, "Task timed out")
        except Exception as e:
            await self._handle_task_failure(task, str(e))
        finally:
            if task.task_id in self.running_tasks:
                del self.running_tasks[task.task_id]
    
    def _run_task_function(self, task: Task) -> Any:
        """Run the actual task function"""
        
        # This is a placeholder - in production, you'd have a registry of available functions
        # For now, we'll simulate task execution
        
        import time
        time.sleep(1)  # Simulate work
        
        # Simulate success/failure based on retry count
        if task.retry_count > 0 and task.retry_count % 2 == 0:
            raise Exception("Simulated task failure")
        
        return {
            "task_id": task.task_id,
            "result": "Task completed successfully",
            "execution_time": 1.0
        }
    
    async def _handle_task_completion(self, task: Task, result: Any):
        """Handle successful task completion"""
        
        with self.lock:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            self.stats["completed_tasks"] += 1
        
        # Create result record
        task_result = TaskResult(
            task_id=task.task_id,
            success=True,
            result=result,
            error_message=None,
            execution_time=result.get("execution_time", 0),
            timestamp=datetime.now(),
            metadata=task.metadata
        )
        
        self.completed_tasks.append(task_result)
        
        # Update average execution time
        total_time = sum(r.execution_time for r in self.completed_tasks)
        self.stats["average_execution_time"] = total_time / len(self.completed_tasks)
        
        logger.info(f"Task completed: {task.name} ({task.task_id})")
    
    async def _handle_task_failure(self, task: Task, error_message: str):
        """Handle task failure"""
        
        with self.lock:
            task.error_message = error_message
            task.retry_count += 1
            
            if task.retry_count < task.max_retries:
                task.status = TaskStatus.RETRYING
                # Reschedule for retry
                retry_delay = min(60 * (2 ** task.retry_count), 3600)  # Exponential backoff
                task.scheduled_at = datetime.now() + timedelta(seconds=retry_delay)
                await self._add_to_queue(task)
            else:
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                self.stats["failed_tasks"] += 1
        
        # Create result record
        task_result = TaskResult(
            task_id=task.task_id,
            success=False,
            result=None,
            error_message=error_message,
            execution_time=0,
            timestamp=datetime.now(),
            metadata=task.metadata
        )
        
        self.completed_tasks.append(task_result)
        
        logger.warning(f"Task failed: {task.name} ({task.task_id}) - {error_message}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of task scheduler"""
        return {
            "task_scheduler": True,
            "is_running": self.is_running,
            "total_tasks": len(self.tasks),
            "pending_tasks": len(self.task_queue),
            "running_tasks": len(self.running_tasks),
            "completed_tasks": len(self.completed_tasks),
            "event_handlers": len(self.event_handlers),
            "conditions": len(self.conditions)
        }
