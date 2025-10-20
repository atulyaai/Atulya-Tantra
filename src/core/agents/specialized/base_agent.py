"""
Atulya Tantra - Base Agent Interface
Version: 2.5.0
Base interface for all specialized agents
"""

import logging
from typing import Dict, List, Optional, Any, Protocol
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent status"""
    IDLE = "idle"
    PROCESSING = "processing"
    ERROR = "error"
    DISABLED = "disabled"


class TaskComplexity(Enum):
    """Task complexity levels"""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"


@dataclass
class AgentCapability:
    """Agent capability definition"""
    name: str
    description: str
    supported_languages: List[str]
    supported_formats: List[str]
    max_complexity: TaskComplexity
    estimated_time: int  # minutes


@dataclass
class AgentTask:
    """Agent task definition"""
    task_id: str
    agent_id: str
    task_type: str
    input_data: Dict[str, Any]
    requirements: Dict[str, Any]
    priority: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    status: str
    result: Any
    error_message: Optional[str]


@dataclass
class AgentResult:
    """Agent execution result"""
    task_id: str
    agent_id: str
    success: bool
    result: Any
    metadata: Dict[str, Any]
    execution_time: float
    confidence: float
    timestamp: datetime


class BaseAgent(Protocol):
    """Base interface for all specialized agents"""
    
    @property
    def agent_id(self) -> str:
        """Get agent unique identifier"""
        ...
    
    @property
    def name(self) -> str:
        """Get agent name"""
        ...
    
    @property
    def capabilities(self) -> List[AgentCapability]:
        """Get agent capabilities"""
        ...
    
    @property
    def status(self) -> AgentStatus:
        """Get current agent status"""
        ...
    
    async def can_handle(self, task_type: str, requirements: Dict[str, Any]) -> bool:
        """Check if agent can handle a specific task"""
        ...
    
    async def process_task(self, task: AgentTask) -> AgentResult:
        """Process a task and return result"""
        ...
    
    async def get_capabilities(self) -> List[AgentCapability]:
        """Get detailed capabilities"""
        ...
    
    async def health_check(self) -> Dict[str, Any]:
        """Check agent health"""
        ...


class AgentManager:
    """Manager for coordinating specialized agents"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.agents = {}  # agent_id -> BaseAgent
        self.task_queue = []  # Pending tasks
        self.active_tasks = {}  # task_id -> AgentTask
        self.completed_tasks = {}  # task_id -> AgentResult
        
        logger.info("AgentManager initialized")
    
    def register_agent(self, agent: BaseAgent):
        """Register a new agent"""
        self.agents[agent.agent_id] = agent
        logger.info(f"Registered agent: {agent.name} ({agent.agent_id})")
    
    def unregister_agent(self, agent_id: str):
        """Unregister an agent"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            logger.info(f"Unregistered agent: {agent_id}")
    
    async def get_available_agents(self) -> List[BaseAgent]:
        """Get list of available agents"""
        return [
            agent for agent in self.agents.values()
            if agent.status == AgentStatus.IDLE
        ]
    
    async def find_best_agent(
        self,
        task_type: str,
        requirements: Dict[str, Any]
    ) -> Optional[BaseAgent]:
        """Find the best agent for a specific task"""
        
        suitable_agents = []
        
        for agent in self.agents.values():
            if await agent.can_handle(task_type, requirements):
                suitable_agents.append(agent)
        
        if not suitable_agents:
            return None
        
        # Simple selection - in production, you'd use more sophisticated logic
        # For now, return the first suitable agent
        return suitable_agents[0]
    
    async def submit_task(
        self,
        task_type: str,
        input_data: Dict[str, Any],
        requirements: Dict[str, Any] = None,
        priority: int = 5
    ) -> str:
        """Submit a task to be processed by an agent"""
        
        task_id = str(uuid.uuid4())
        
        # Find best agent
        agent = await self.find_best_agent(task_type, requirements or {})
        
        if not agent:
            raise ValueError(f"No suitable agent found for task type: {task_type}")
        
        # Create task
        task = AgentTask(
            task_id=task_id,
            agent_id=agent.agent_id,
            task_type=task_type,
            input_data=input_data,
            requirements=requirements or {},
            priority=priority,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        # Add to queue
        self.task_queue.append(task)
        
        # Process task if agent is available
        if agent.status == AgentStatus.IDLE:
            await self._process_next_task(agent)
        
        logger.info(f"Submitted task: {task_type} ({task_id}) to agent {agent.name}")
        return task_id
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a task"""
        
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            return {
                "task_id": task_id,
                "status": task.status,
                "agent_id": task.agent_id,
                "created_at": task.created_at.isoformat(),
                "started_at": task.started_at.isoformat() if task.started_at else None
            }
        elif task_id in self.completed_tasks:
            result = self.completed_tasks[task_id]
            return {
                "task_id": task_id,
                "status": "completed",
                "agent_id": result.agent_id,
                "success": result.success,
                "completed_at": result.timestamp.isoformat(),
                "execution_time": result.execution_time
            }
        else:
            return {"error": "Task not found"}
    
    async def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents"""
        
        return {
            "total_agents": len(self.agents),
            "available_agents": len(await self.get_available_agents()),
            "pending_tasks": len(self.task_queue),
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.completed_tasks),
            "agents": [
                {
                    "agent_id": agent.agent_id,
                    "name": agent.name,
                    "status": agent.status.value,
                    "capabilities": [cap.name for cap in agent.capabilities]
                }
                for agent in self.agents.values()
            ]
        }
    
    async def _process_next_task(self, agent: BaseAgent):
        """Process the next task for an agent"""
        
        if not self.task_queue:
            return
        
        # Find tasks for this agent
        agent_tasks = [
            task for task in self.task_queue
            if task.agent_id == agent.agent_id
        ]
        
        if not agent_tasks:
            return
        
        # Sort by priority (higher priority first)
        agent_tasks.sort(key=lambda t: t.priority, reverse=True)
        
        # Take the highest priority task
        task = agent_tasks[0]
        self.task_queue.remove(task)
        self.active_tasks[task.task_id] = task
        
        # Update task status
        task.status = "processing"
        task.started_at = datetime.now()
        
        try:
            # Process task
            result = await agent.process_task(task)
            
            # Store result
            self.completed_tasks[task.task_id] = result
            
            # Remove from active tasks
            del self.active_tasks[task.task_id]
            
            logger.info(f"Completed task: {task.task_id} by agent {agent.name}")
            
        except Exception as e:
            logger.error(f"Task failed: {task.task_id} - {e}")
            
            # Create error result
            error_result = AgentResult(
                task_id=task.task_id,
                agent_id=agent.agent_id,
                success=False,
                result=None,
                metadata={},
                execution_time=0,
                confidence=0,
                timestamp=datetime.now()
            )
            
            self.completed_tasks[task.task_id] = error_result
            del self.active_tasks[task.task_id]
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of agent manager"""
        return {
            "agent_manager": True,
            "total_agents": len(self.agents),
            "pending_tasks": len(self.task_queue),
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.completed_tasks)
        }
