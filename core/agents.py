"""
Atulya Tantra - Multi-Agent System
Version: 2.2.0
Handles multi-agent orchestration, agent hierarchy, and coordination.
"""

import asyncio
import uuid
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json

class AgentType(Enum):
    """Agent type enumeration"""
    CONVERSATION = "conversation"
    CODE = "code"
    RESEARCH = "research"
    DATA_ANALYSIS = "data_analysis"
    CREATIVE = "creative"
    TASK_PLANNER = "task_planner"
    COORDINATOR = "coordinator"

class AgentStatus(Enum):
    """Agent status enumeration"""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"

@dataclass
class AgentCapability:
    """Agent capability definition"""
    name: str
    description: str
    input_types: List[str]
    output_types: List[str]
    complexity_level: int  # 1-10

@dataclass
class Task:
    """Task data structure"""
    id: str
    description: str
    task_type: str
    priority: int  # 1-10
    assigned_agent: Optional[str] = None
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None

@dataclass
class AgentInfo:
    """Agent information structure"""
    id: str
    name: str
    agent_type: AgentType
    capabilities: List[AgentCapability]
    status: AgentStatus
    performance_score: float
    created_at: datetime
    last_active: datetime

class BaseAgent:
    """Base agent class"""
    
    def __init__(self, agent_id: str, name: str, agent_type: AgentType):
        self.id = agent_id
        self.name = name
        self.agent_type = agent_type
        self.status = AgentStatus.IDLE
        self.capabilities: List[AgentCapability] = []
        self.performance_score = 1.0
        self.created_at = datetime.now()
        self.last_active = datetime.now()
        self.current_task: Optional[Task] = None
    
    async def execute_task(self, task: Task) -> Any:
        """Execute a task (to be implemented by subclasses)"""
        self.status = AgentStatus.BUSY
        self.current_task = task
        self.last_active = datetime.now()
        
        try:
            result = await self._process_task(task)
            task.status = "completed"
            task.result = result
            task.completed_at = datetime.now()
            self.status = AgentStatus.IDLE
            return result
        except Exception as e:
            task.status = "error"
            task.error = str(e)
            self.status = AgentStatus.ERROR
            raise
    
    async def _process_task(self, task: Task) -> Any:
        """Process task (implemented by subclasses)"""
        raise NotImplementedError("Subclasses must implement _process_task")
    
    def get_info(self) -> AgentInfo:
        """Get agent information"""
        return AgentInfo(
            id=self.id,
            name=self.name,
            agent_type=self.agent_type,
            capabilities=self.capabilities,
            status=self.status,
            performance_score=self.performance_score,
            created_at=self.created_at,
            last_active=self.last_active
        )

class ConversationAgent(BaseAgent):
    """Conversation agent for natural language interactions"""
    
    def __init__(self, agent_id: str = None):
        super().__init__(
            agent_id or str(uuid.uuid4()),
            "Conversation Agent",
            AgentType.CONVERSATION
        )
        self.capabilities = [
            AgentCapability(
                name="natural_language_processing",
                description="Process and respond to natural language",
                input_types=["text", "voice"],
                output_types=["text", "voice"],
                complexity_level=7
            )
        ]
    
    async def _process_task(self, task: Task) -> str:
        """Process conversation task"""
        # Simulate conversation processing
        await asyncio.sleep(0.1)  # Simulate processing time
        return f"Conversation response for: {task.description}"

class CodeAgent(BaseAgent):
    """Code agent for programming tasks"""
    
    def __init__(self, agent_id: str = None):
        super().__init__(
            agent_id or str(uuid.uuid4()),
            "Code Agent",
            AgentType.CODE
        )
        self.capabilities = [
            AgentCapability(
                name="code_generation",
                description="Generate and analyze code",
                input_types=["text", "code"],
                output_types=["code", "analysis"],
                complexity_level=8
            )
        ]
    
    async def _process_task(self, task: Task) -> str:
        """Process code task"""
        await asyncio.sleep(0.2)  # Simulate processing time
        return f"Generated code for: {task.description}"

class ResearchAgent(BaseAgent):
    """Research agent for information gathering"""
    
    def __init__(self, agent_id: str = None):
        super().__init__(
            agent_id or str(uuid.uuid4()),
            "Research Agent",
            AgentType.RESEARCH
        )
        self.capabilities = [
            AgentCapability(
                name="information_research",
                description="Research and gather information",
                input_types=["text", "query"],
                output_types=["text", "data"],
                complexity_level=6
            )
        ]
    
    async def _process_task(self, task: Task) -> str:
        """Process research task"""
        await asyncio.sleep(0.3)  # Simulate processing time
        return f"Research results for: {task.description}"

class AgentRegistry:
    """Registry for managing agents"""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.agent_types: Dict[AgentType, List[str]] = {}
    
    def register_agent(self, agent: BaseAgent) -> None:
        """Register an agent"""
        self.agents[agent.id] = agent
        
        if agent.agent_type not in self.agent_types:
            self.agent_types[agent.agent_type] = []
        self.agent_types[agent.agent_type].append(agent.id)
    
    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent"""
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            if agent.agent_type in self.agent_types:
                self.agent_types[agent.agent_type].remove(agent_id)
            del self.agents[agent_id]
    
    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get agent by ID"""
        return self.agents.get(agent_id)
    
    def get_agents_by_type(self, agent_type: AgentType) -> List[BaseAgent]:
        """Get agents by type"""
        agent_ids = self.agent_types.get(agent_type, [])
        return [self.agents[aid] for aid in agent_ids if aid in self.agents]
    
    def get_available_agents(self) -> List[BaseAgent]:
        """Get all available agents"""
        return [agent for agent in self.agents.values() 
                if agent.status == AgentStatus.IDLE]
    
    def get_all_agents(self) -> List[BaseAgent]:
        """Get all registered agents"""
        return list(self.agents.values())

class TaskQueue:
    """Task queue for managing tasks"""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.pending_tasks: List[str] = []
        self.completed_tasks: List[str] = []
    
    def add_task(self, task: Task) -> None:
        """Add task to queue"""
        self.tasks[task.id] = task
        self.pending_tasks.append(task.id)
        # Sort by priority (higher priority first)
        self.pending_tasks.sort(key=lambda tid: self.tasks[tid].priority, reverse=True)
    
    def get_next_task(self) -> Optional[Task]:
        """Get next task from queue"""
        if self.pending_tasks:
            task_id = self.pending_tasks.pop(0)
            return self.tasks[task_id]
        return None
    
    def complete_task(self, task_id: str) -> None:
        """Mark task as completed"""
        if task_id in self.tasks:
            self.tasks[task_id].status = "completed"
            self.completed_tasks.append(task_id)
    
    def get_task_status(self, task_id: str) -> Optional[str]:
        """Get task status"""
        if task_id in self.tasks:
            return self.tasks[task_id].status
        return None

class MultiAgentOrchestrator:
    """Main orchestrator for multi-agent system"""
    
    def __init__(self):
        self.registry = AgentRegistry()
        self.task_queue = TaskQueue()
        self.is_running = False
        self.orchestration_task: Optional[asyncio.Task] = None
        
        # Initialize default agents
        self._initialize_default_agents()
    
    def _initialize_default_agents(self):
        """Initialize default agents"""
        agents = [
            ConversationAgent(),
            CodeAgent(),
            ResearchAgent()
        ]
        
        for agent in agents:
            self.registry.register_agent(agent)
    
    async def start_orchestration(self):
        """Start the orchestration system"""
        if self.is_running:
            return
        
        self.is_running = True
        self.orchestration_task = asyncio.create_task(self._orchestration_loop())
    
    async def stop_orchestration(self):
        """Stop the orchestration system"""
        self.is_running = False
        if self.orchestration_task:
            self.orchestration_task.cancel()
            try:
                await self.orchestration_task
            except asyncio.CancelledError:
                pass
    
    async def _orchestration_loop(self):
        """Main orchestration loop"""
        while self.is_running:
            try:
                # Get next task
                task = self.task_queue.get_next_task()
                if task:
                    # Find best agent for task
                    agent = self._find_best_agent(task)
                    if agent:
                        # Execute task
                        await self._execute_task_with_agent(task, agent)
                
                await asyncio.sleep(0.1)  # Small delay
                
            except Exception as e:
                print(f"Orchestration error: {e}")
                await asyncio.sleep(1)
    
    def _find_best_agent(self, task: Task) -> Optional[BaseAgent]:
        """Find the best agent for a task"""
        available_agents = self.registry.get_available_agents()
        
        if not available_agents:
            return None
        
        # Simple agent selection (in production, use more sophisticated logic)
        for agent in available_agents:
            if self._can_handle_task(agent, task):
                return agent
        
        return available_agents[0]  # Fallback to first available
    
    def _can_handle_task(self, agent: BaseAgent, task: Task) -> bool:
        """Check if agent can handle task"""
        # Simple capability matching
        for capability in agent.capabilities:
            if task.task_type.lower() in capability.name.lower():
                return True
        return False
    
    async def _execute_task_with_agent(self, task: Task, agent: BaseAgent):
        """Execute task with specific agent"""
        try:
            task.assigned_agent = agent.id
            task.status = "in_progress"
            
            result = await agent.execute_task(task)
            
            self.task_queue.complete_task(task.id)
            print(f"Task {task.id} completed by {agent.name}")
            
        except Exception as e:
            task.status = "error"
            task.error = str(e)
            print(f"Task {task.id} failed: {e}")
    
    async def submit_task(self, description: str, task_type: str, priority: int = 5) -> str:
        """Submit a new task"""
        task = Task(
            id=str(uuid.uuid4()),
            description=description,
            task_type=task_type,
            priority=priority
        )
        
        self.task_queue.add_task(task)
        return task.id
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status"""
        agents = self.registry.get_all_agents()
        
        return {
            "is_running": self.is_running,
            "total_agents": len(agents),
            "available_agents": len(self.registry.get_available_agents()),
            "pending_tasks": len(self.task_queue.pending_tasks),
            "completed_tasks": len(self.task_queue.completed_tasks),
            "agents": [agent.get_info() for agent in agents]
        }

# Global instances
_agent_registry: Optional[AgentRegistry] = None
_multi_agent_orchestrator: Optional[MultiAgentOrchestrator] = None

def get_agent_registry() -> AgentRegistry:
    """Get global agent registry instance"""
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry()
    return _agent_registry

def get_multi_agent_orchestrator() -> MultiAgentOrchestrator:
    """Get global multi-agent orchestrator instance"""
    global _multi_agent_orchestrator
    if _multi_agent_orchestrator is None:
        _multi_agent_orchestrator = MultiAgentOrchestrator()
    return _multi_agent_orchestrator

# Export main classes and functions
__all__ = [
    "AgentType",
    "AgentStatus",
    "AgentCapability",
    "Task",
    "AgentInfo",
    "BaseAgent",
    "ConversationAgent",
    "CodeAgent",
    "ResearchAgent",
    "AgentRegistry",
    "TaskQueue",
    "MultiAgentOrchestrator",
    "get_agent_registry",
    "get_multi_agent_orchestrator"
]
