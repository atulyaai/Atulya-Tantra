"""
Base agent framework for Atulya Tantra AGI
Abstract agent interface and orchestration system
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Callable, Awaitable
from datetime import datetime
import asyncio
import uuid
from enum import Enum

from ..config.settings import settings
from ..config.logging import get_logger
from ..config.exceptions import AgentError, AgentTimeoutError, AgentNotAvailableError
from ..brain import generate_response, get_llm_router
from ..database.service import get_db_service, insert_record, get_record_by_id, update_record

logger = get_logger(__name__)


class AgentStatus(str, Enum):
    """Agent execution status"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class AgentCapability(str, Enum):
    """Agent capability types"""
    TEXT_GENERATION = "text_generation"
    CODE_EXECUTION = "code_execution"
    DATA_ANALYSIS = "data_analysis"
    RESEARCH = "research"
    CREATIVE_WRITING = "creative_writing"
    SYSTEM_CONTROL = "system_control"
    FILE_PROCESSING = "file_processing"
    WEB_SEARCH = "web_search"
    IMAGE_PROCESSING = "image_processing"
    VOICE_PROCESSING = "voice_processing"


class AgentPriority(int, Enum):
    """Agent priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class AgentTask:
    """Represents a task for an agent"""
    
    def __init__(
        self,
        task_id: str = None,
        agent_type: str = None,
        task_type: str = None,
        description: str = None,
        input_data: Dict[str, Any] = None,
        priority: AgentPriority = AgentPriority.NORMAL,
        timeout_seconds: int = 300,
        metadata: Dict[str, Any] = None
    ):
        self.task_id = task_id or str(uuid.uuid4())
        self.agent_type = agent_type
        self.task_type = task_type
        self.description = description
        self.input_data = input_data or {}
        self.priority = priority
        self.timeout_seconds = timeout_seconds
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.status = AgentStatus.IDLE
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.progress: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary"""
        return {
            "task_id": self.task_id,
            "agent_type": self.agent_type,
            "task_type": self.task_type,
            "description": self.description,
            "input_data": self.input_data,
            "priority": self.priority.value,
            "timeout_seconds": self.timeout_seconds,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "progress": self.progress
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentTask':
        """Create task from dictionary"""
        task = cls(
            task_id=data.get("task_id"),
            agent_type=data.get("agent_type"),
            task_type=data.get("task_type"),
            description=data.get("description"),
            input_data=data.get("input_data", {}),
            priority=AgentPriority(data.get("priority", AgentPriority.NORMAL.value)),
            timeout_seconds=data.get("timeout_seconds", 300),
            metadata=data.get("metadata", {})
        )
        
        if data.get("started_at"):
            task.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            task.completed_at = datetime.fromisoformat(data["completed_at"])
        
        task.status = AgentStatus(data.get("status", AgentStatus.IDLE.value))
        task.result = data.get("result")
        task.error = data.get("error")
        task.progress = data.get("progress", 0.0)
        
        return task


class BaseAgent(ABC):
    """Abstract base class for all agents"""
    
    def __init__(
        self,
        agent_id: str = None,
        name: str = None,
        description: str = None,
        capabilities: List[AgentCapability] = None,
        max_concurrent_tasks: int = 1,
        timeout_seconds: int = 300
    ):
        self.agent_id = agent_id or str(uuid.uuid4())
        self.name = name or self.__class__.__name__
        self.description = description or f"{self.name} agent"
        self.capabilities = capabilities or []
        self.max_concurrent_tasks = max_concurrent_tasks
        self.timeout_seconds = timeout_seconds
        
        self.status = AgentStatus.IDLE
        self.current_tasks: Dict[str, AgentTask] = {}
        self.task_history: List[AgentTask] = []
        self.is_available = True
        self.last_heartbeat = datetime.utcnow()
        
        # Performance metrics
        self.total_tasks_completed = 0
        self.total_tasks_failed = 0
        self.average_execution_time = 0.0
        self.success_rate = 0.0
    
    @abstractmethod
    async def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        """Execute a task and return results"""
        pass
    
    @abstractmethod
    async def can_handle_task(self, task: AgentTask) -> bool:
        """Check if this agent can handle the given task"""
        pass
    
    @abstractmethod
    async def get_task_estimate(self, task: AgentTask) -> Dict[str, Any]:
        """Estimate task execution time and resource requirements"""
        pass
    
    async def start_task(self, task: AgentTask) -> bool:
        """Start executing a task"""
        if not self.is_available:
            raise AgentNotAvailableError(self.name)
        
        if len(self.current_tasks) >= self.max_concurrent_tasks:
            logger.warning(f"Agent {self.name} at capacity, cannot start task {task.task_id}")
            return False
        
        if not await self.can_handle_task(task):
            logger.warning(f"Agent {self.name} cannot handle task {task.task_id}")
            return False
        
        task.started_at = datetime.utcnow()
        task.status = AgentStatus.RUNNING
        self.current_tasks[task.task_id] = task
        self.status = AgentStatus.RUNNING
        
        logger.info(f"Agent {self.name} started task {task.task_id}")
        return True
    
    async def complete_task(self, task: AgentTask, result: Dict[str, Any] = None, error: str = None):
        """Complete a task with results or error"""
        task.completed_at = datetime.utcnow()
        task.result = result
        task.error = error
        
        if error:
            task.status = AgentStatus.FAILED
            self.total_tasks_failed += 1
            logger.error(f"Agent {self.name} failed task {task.task_id}: {error}")
        else:
            task.status = AgentStatus.COMPLETED
            self.total_tasks_completed += 1
            logger.info(f"Agent {self.name} completed task {task.task_id}")
        
        # Move task to history
        if task.task_id in self.current_tasks:
            del self.current_tasks[task.task_id]
        
        self.task_history.append(task)
        
        # Update metrics
        self._update_metrics()
        
        # Update status
        if not self.current_tasks:
            self.status = AgentStatus.IDLE
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task"""
        if task_id in self.current_tasks:
            task = self.current_tasks[task_id]
            task.status = AgentStatus.CANCELLED
            task.completed_at = datetime.utcnow()
            
            del self.current_tasks[task_id]
            self.task_history.append(task)
            
            logger.info(f"Agent {self.name} cancelled task {task_id}")
            return True
        
        return False
    
    def _update_metrics(self):
        """Update agent performance metrics"""
        total_tasks = self.total_tasks_completed + self.total_tasks_failed
        if total_tasks > 0:
            self.success_rate = self.total_tasks_completed / total_tasks
        
        # Calculate average execution time
        completed_tasks = [t for t in self.task_history if t.status == AgentStatus.COMPLETED and t.started_at and t.completed_at]
        if completed_tasks:
            total_time = sum((t.completed_at - t.started_at).total_seconds() for t in completed_tasks)
            self.average_execution_time = total_time / len(completed_tasks)
    
    async def heartbeat(self):
        """Update agent heartbeat"""
        self.last_heartbeat = datetime.utcnow()
    
    async def get_status(self) -> Dict[str, Any]:
        """Get agent status and metrics"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "capabilities": [cap.value for cap in self.capabilities],
            "status": self.status.value,
            "is_available": self.is_available,
            "current_tasks": len(self.current_tasks),
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "total_tasks_completed": self.total_tasks_completed,
            "total_tasks_failed": self.total_tasks_failed,
            "success_rate": self.success_rate,
            "average_execution_time": self.average_execution_time
        }
    
    async def get_task_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get task execution history"""
        recent_tasks = self.task_history[-limit:] if self.task_history else []
        return [task.to_dict() for task in recent_tasks]


class AgentRegistry:
    """Registry for managing agents"""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.agent_types: Dict[str, type] = {}
    
    def register_agent_type(self, agent_type: str, agent_class: type):
        """Register an agent type"""
        self.agent_types[agent_type] = agent_class
        logger.info(f"Registered agent type: {agent_type}")
    
    def register_agent(self, agent: BaseAgent):
        """Register an agent instance"""
        self.agents[agent.agent_id] = agent
        logger.info(f"Registered agent: {agent.name} ({agent.agent_id})")
    
    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent"""
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            del self.agents[agent_id]
            logger.info(f"Unregistered agent: {agent.name} ({agent_id})")
            return True
        return False
    
    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get agent by ID"""
        return self.agents.get(agent_id)
    
    def get_agents_by_capability(self, capability: AgentCapability) -> List[BaseAgent]:
        """Get agents that have a specific capability"""
        return [
            agent for agent in self.agents.values()
            if capability in agent.capabilities and agent.is_available
        ]
    
    def get_available_agents(self) -> List[BaseAgent]:
        """Get all available agents"""
        return [agent for agent in self.agents.values() if agent.is_available]
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents"""
        return {
            agent_id: {
                "name": agent.name,
                "status": agent.status.value,
                "is_available": agent.is_available,
                "current_tasks": len(agent.current_tasks),
                "capabilities": [cap.value for cap in agent.capabilities]
            }
            for agent_id, agent in self.agents.items()
        }


class AgentOrchestrator:
    """Orchestrates task execution across multiple agents"""
    
    def __init__(self):
        self.registry = AgentRegistry()
        self.task_queue: List[AgentTask] = []
        self.running_tasks: Dict[str, AgentTask] = {}
        self.completed_tasks: Dict[str, AgentTask] = {}
        self.is_running = False
        self.worker_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the orchestrator"""
        if self.is_running:
            return
        
        self.is_running = True
        self.worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Agent orchestrator started")
    
    async def stop(self):
        """Stop the orchestrator"""
        self.is_running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all running tasks
        for task in self.running_tasks.values():
            await self._cancel_task(task)
        
        logger.info("Agent orchestrator stopped")
    
    async def submit_task(self, task: AgentTask) -> str:
        """Submit a task for execution"""
        # Insert task in priority order to maintain sorted queue
        inserted = False
        for i, existing_task in enumerate(self.task_queue):
            if task.priority.value > existing_task.priority.value:
                self.task_queue.insert(i, task)
                inserted = True
                break
        
        if not inserted:
            self.task_queue.append(task)
        
        logger.info(f"Submitted task {task.task_id} to orchestrator")
        return task.task_id
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a task"""
        if task_id in self.running_tasks:
            return self.running_tasks[task_id].to_dict()
        elif task_id in self.completed_tasks:
            return self.completed_tasks[task_id].to_dict()
        else:
            # Check in queue
            for task in self.task_queue:
                if task.task_id == task_id:
                    return task.to_dict()
        return None
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task"""
        # Check if task is running
        if task_id in self.running_tasks:
            return await self._cancel_task(self.running_tasks[task_id])
        
        # Check if task is in queue
        for i, task in enumerate(self.task_queue):
            if task.task_id == task_id:
                task.status = AgentStatus.CANCELLED
                del self.task_queue[i]
                self.completed_tasks[task_id] = task
                logger.info(f"Cancelled queued task {task_id}")
                return True
        
        return False
    
    async def _worker_loop(self):
        """Main worker loop for processing tasks"""
        while self.is_running:
            try:
                if self.task_queue:
                    task = self.task_queue.pop(0)
                    await self._execute_task(task)
                else:
                    await asyncio.sleep(0.1)  # Small delay when no tasks
            except Exception as e:
                logger.error(f"Error in orchestrator worker loop: {e}")
                await asyncio.sleep(1)
    
    async def _execute_task(self, task: AgentTask):
        """Execute a task by finding the best agent"""
        try:
            # Find best agent for the task
            agent = await self._find_best_agent(task)
            if not agent:
                task.status = AgentStatus.FAILED
                task.error = "No available agent can handle this task"
                self.completed_tasks[task.task_id] = task
                logger.error(f"No agent available for task {task.task_id}")
                return
            
            # Start task on agent
            if not await agent.start_task(task):
                task.status = AgentStatus.FAILED
                task.error = "Agent could not start the task"
                self.completed_tasks[task.task_id] = task
                return
            
            self.running_tasks[task.task_id] = task
            
            # Execute task with timeout
            try:
                result = await asyncio.wait_for(
                    agent.execute_task(task),
                    timeout=task.timeout_seconds
                )
                await agent.complete_task(task, result)
            except asyncio.TimeoutError:
                await agent.complete_task(task, error="Task timeout")
                task.status = AgentStatus.TIMEOUT
            except Exception as e:
                await agent.complete_task(task, error=str(e))
            
            # Move to completed tasks
            self.completed_tasks[task.task_id] = task
            if task.task_id in self.running_tasks:
                del self.running_tasks[task.task_id]
            
        except Exception as e:
            logger.error(f"Error executing task {task.task_id}: {e}")
            task.status = AgentStatus.FAILED
            task.error = str(e)
            self.completed_tasks[task.task_id] = task
    
    async def _find_best_agent(self, task: AgentTask) -> Optional[BaseAgent]:
        """Find the best agent for a task"""
        available_agents = self.registry.get_available_agents()
        
        if not available_agents:
            return None
        
        # Filter agents that can handle the task
        capable_agents = []
        for agent in available_agents:
            if await agent.can_handle_task(task):
                capable_agents.append(agent)
        
        if not capable_agents:
            return None
        
        # Select agent with lowest load
        best_agent = min(capable_agents, key=lambda a: len(a.current_tasks))
        return best_agent
    
    async def _cancel_task(self, task: AgentTask) -> bool:
        """Cancel a running task"""
        # Find the agent running this task
        for agent in self.registry.agents.values():
            if task.task_id in agent.current_tasks:
                success = await agent.cancel_task(task.task_id)
                if success:
                    del self.running_tasks[task.task_id]
                    self.completed_tasks[task.task_id] = task
                    return True
        return False
    
    async def get_orchestrator_status(self) -> Dict[str, Any]:
        """Get orchestrator status"""
        return {
            "is_running": self.is_running,
            "queued_tasks": len(self.task_queue),
            "running_tasks": len(self.running_tasks),
            "completed_tasks": len(self.completed_tasks),
            "registered_agents": len(self.registry.agents),
            "available_agents": len(self.registry.get_available_agents())
        }


# Global orchestrator instance
_orchestrator: Optional[AgentOrchestrator] = None


async def get_orchestrator() -> AgentOrchestrator:
    """Get global agent orchestrator"""
    global _orchestrator
    
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
        await _orchestrator.start()
    
    return _orchestrator


async def submit_task(
    agent_type: str = None,
    task_type: str = None,
    description: str = None,
    input_data: Dict[str, Any] = None,
    priority: AgentPriority = AgentPriority.NORMAL,
    timeout_seconds: int = 300,
    metadata: Dict[str, Any] = None
) -> str:
    """Submit a task to the orchestrator"""
    orchestrator = await get_orchestrator()
    
    task = AgentTask(
        agent_type=agent_type,
        task_type=task_type,
        description=description,
        input_data=input_data,
        priority=priority,
        timeout_seconds=timeout_seconds,
        metadata=metadata
    )
    
    return await orchestrator.submit_task(task)


async def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """Get task status"""
    orchestrator = await get_orchestrator()
    return await orchestrator.get_task_status(task_id)


async def cancel_task(task_id: str) -> bool:
    """Cancel a task"""
    orchestrator = await get_orchestrator()
    return await orchestrator.cancel_task(task_id)


# Export public API
__all__ = [
    "AgentStatus",
    "AgentCapability", 
    "AgentPriority",
    "AgentTask",
    "BaseAgent",
    "AgentRegistry",
    "AgentOrchestrator",
    "get_orchestrator",
    "submit_task",
    "get_task_status",
    "cancel_task"
]
