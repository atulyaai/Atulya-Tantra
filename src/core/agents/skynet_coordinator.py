"""
Atulya Tantra - Skynet Multi-Agent Coordinator
Version: 2.5.0
Coordinates multiple agents for complex task execution
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
import uuid
from enum import Enum
from dataclasses import dataclass

from src.core.agents.specialized.base_agent import BaseAgent
from src.core.agents.skynet.decision_engine import DecisionEngine
from src.core.agents.skynet.executor import TaskExecutor, TaskPriority

logger = logging.getLogger(__name__)

class CoordinationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class AgentCapability:
    """Represents an agent's capability"""
    agent_id: str
    capability_type: str
    confidence: float
    resources_required: List[str]
    estimated_duration: int  # seconds

@dataclass
class TaskAssignment:
    """Represents a task assignment to an agent"""
    task_id: str
    agent_id: str
    task_data: Dict[str, Any]
    priority: TaskPriority
    dependencies: List[str]
    deadline: Optional[datetime] = None

class MultiAgentCoordinator:
    """
    Coordinates multiple agents for complex task execution
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.agents: Dict[str, BaseAgent] = {}
        self.agent_capabilities: Dict[str, List[AgentCapability]] = {}
        self.task_assignments: Dict[str, TaskAssignment] = {}
        self.coordination_sessions: Dict[str, Dict[str, Any]] = {}
        
        self.decision_engine = DecisionEngine(config)
        self.task_executor = TaskExecutor(config)
        
        self._coordination_lock = asyncio.Lock()
        
        logger.info("MultiAgentCoordinator initialized")
    
    def register_agent(self, agent: BaseAgent):
        """Register an agent with the coordinator"""
        self.agents[agent.agent_id] = agent
        
        # Initialize capabilities
        self.agent_capabilities[agent.agent_id] = []
        
        # Register agent with task executor
        self.task_executor.register_task(
            f"agent_{agent.agent_id}",
            self._create_agent_task_handler(agent)
        )
        
        logger.info("Registered agent: %s", agent.agent_id)
    
    def _create_agent_task_handler(self, agent: BaseAgent):
        """Create a task handler for a specific agent"""
        async def agent_task_handler(task_data: Dict[str, Any]) -> Dict[str, Any]:
            try:
                result = await agent.handle_task(
                    task_data.get("description", ""),
                    task_data.get("context", {})
                )
                return result
            except Exception as e:
                logger.error("Agent %s task failed: %s", agent.agent_id, e)
                raise
        
        return agent_task_handler
    
    async def add_agent_capability(
        self,
        agent_id: str,
        capability_type: str,
        confidence: float,
        resources_required: List[str],
        estimated_duration: int
    ):
        """Add a capability to an agent"""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not registered")
        
        capability = AgentCapability(
            agent_id=agent_id,
            capability_type=capability_type,
            confidence=confidence,
            resources_required=resources_required,
            estimated_duration=estimated_duration
        )
        
        self.agent_capabilities[agent_id].append(capability)
        logger.debug("Added capability %s to agent %s", capability_type, agent_id)
    
    async def coordinate_task(
        self,
        task_description: str,
        context: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL
    ) -> str:
        """
        Coordinate execution of a complex task across multiple agents
        
        Args:
            task_description: Description of the task to coordinate
            context: Additional context for the task
            priority: Task priority
            
        Returns:
            Coordination session ID
        """
        session_id = str(uuid.uuid4())
        
        async with self._coordination_lock:
            # Create coordination session
            self.coordination_sessions[session_id] = {
                "id": session_id,
                "task_description": task_description,
                "context": context,
                "status": CoordinationStatus.PENDING,
                "created_at": datetime.now().isoformat(),
                "assigned_tasks": [],
                "completed_tasks": [],
                "failed_tasks": [],
                "results": {}
            }
            
            # Analyze task and break it down
            task_breakdown = await self._analyze_and_breakdown_task(task_description, context)
            
            # Assign tasks to appropriate agents
            assignments = await self._assign_tasks_to_agents(task_breakdown, session_id)
            
            # Submit tasks to executor
            for assignment in assignments:
                task_id = await self.task_executor.submit_task(
                    f"agent_{assignment.agent_id}",
                    {
                        "description": assignment.task_data.get("description", ""),
                        "context": assignment.task_data.get("context", {}),
                        "session_id": session_id
                    },
                    assignment.priority
                )
                
                assignment.task_id = task_id
                self.task_assignments[task_id] = assignment
                self.coordination_sessions[session_id]["assigned_tasks"].append(task_id)
            
            # Update session status
            self.coordination_sessions[session_id]["status"] = CoordinationStatus.IN_PROGRESS
            
            # Start monitoring task completion
            asyncio.create_task(self._monitor_coordination_session(session_id))
            
            logger.info("Started coordination session: %s for task: %s", session_id, task_description)
            return session_id
    
    async def _analyze_and_breakdown_task(
        self,
        task_description: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Analyze task and break it down into subtasks"""
        # Use decision engine to plan the task
        goal_result = await self.decision_engine.set_goal(task_description, context=context)
        goal_id = goal_result["goal_id"]
        
        # Generate plan
        plan_result = await self.decision_engine.plan_actions(goal_id)
        plan = plan_result.get("plan", [])
        
        # Convert plan to task breakdown
        task_breakdown = []
        for i, step in enumerate(plan):
            task_breakdown.append({
                "id": f"subtask_{i}",
                "description": step.get("description", f"Step {i+1}"),
                "action": step.get("action", "generic"),
                "params": step.get("params", {}),
                "dependencies": step.get("dependencies", []),
                "estimated_duration": 60,  # Default 1 minute
                "resources_required": []
            })
        
        return task_breakdown
    
    async def _assign_tasks_to_agents(
        self,
        task_breakdown: List[Dict[str, Any]],
        session_id: str
    ) -> List[TaskAssignment]:
        """Assign tasks to appropriate agents based on capabilities"""
        assignments = []
        
        for task in task_breakdown:
            # Find best agent for this task
            best_agent = await self._find_best_agent_for_task(task)
            
            if best_agent:
                assignment = TaskAssignment(
                    task_id="",  # Will be set when submitted
                    agent_id=best_agent,
                    task_data=task,
                    priority=TaskPriority.NORMAL,
                    dependencies=task.get("dependencies", [])
                )
                assignments.append(assignment)
            else:
                logger.warning("No suitable agent found for task: %s", task["description"])
        
        return assignments
    
    async def _find_best_agent_for_task(self, task: Dict[str, Any]) -> Optional[str]:
        """Find the best agent for a given task"""
        task_type = task.get("action", "generic")
        task_description = task.get("description", "").lower()
        
        best_agent = None
        best_score = 0.0
        
        for agent_id, capabilities in self.agent_capabilities.items():
            if not self.agents[agent_id].is_enabled:
                continue
            
            # Calculate score based on capabilities
            score = 0.0
            
            for capability in capabilities:
                if capability.capability_type == task_type:
                    score += capability.confidence * 0.8
                elif task_type in task_description:
                    score += capability.confidence * 0.6
                else:
                    # Generic capability match
                    score += capability.confidence * 0.3
            
            if score > best_score:
                best_score = score
                best_agent = agent_id
        
        return best_agent if best_score > 0.3 else None
    
    async def _monitor_coordination_session(self, session_id: str):
        """Monitor a coordination session and update status"""
        session = self.coordination_sessions.get(session_id)
        if not session:
            return
        
        while session["status"] == CoordinationStatus.IN_PROGRESS:
            # Check task statuses
            completed_count = 0
            failed_count = 0
            
            for task_id in session["assigned_tasks"]:
                task_status = await self.task_executor.get_task_status(task_id)
                if task_status:
                    if task_status["status"] == "completed":
                        completed_count += 1
                        if task_id not in session["completed_tasks"]:
                            session["completed_tasks"].append(task_id)
                            # Store result
                            session["results"][task_id] = task_status.get("result", {})
                    elif task_status["status"] == "failed":
                        failed_count += 1
                        if task_id not in session["failed_tasks"]:
                            session["failed_tasks"].append(task_id)
            
            # Check if all tasks are done
            total_tasks = len(session["assigned_tasks"])
            if completed_count + failed_count >= total_tasks:
                if failed_count == 0:
                    session["status"] = CoordinationStatus.COMPLETED
                else:
                    session["status"] = CoordinationStatus.FAILED
                
                session["completed_at"] = datetime.now().isoformat()
                logger.info("Coordination session %s completed with status: %s", session_id, session["status"])
                break
            
            # Wait before checking again
            await asyncio.sleep(5)
    
    async def get_coordination_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a coordination session"""
        return self.coordination_sessions.get(session_id)
    
    async def cancel_coordination(self, session_id: str) -> bool:
        """Cancel a coordination session"""
        session = self.coordination_sessions.get(session_id)
        if not session:
            return False
        
        if session["status"] == CoordinationStatus.IN_PROGRESS:
            # Cancel all assigned tasks
            for task_id in session["assigned_tasks"]:
                await self.task_executor.cancel_task(task_id)
            
            session["status"] = CoordinationStatus.CANCELLED
            session["cancelled_at"] = datetime.now().isoformat()
            
            logger.info("Cancelled coordination session: %s", session_id)
            return True
        
        return False
    
    async def get_agent_load(self) -> Dict[str, Any]:
        """Get current load distribution across agents"""
        agent_load = {}
        
        for agent_id in self.agents:
            # Count running tasks for this agent
            running_tasks = 0
            for assignment in self.task_assignments.values():
                if assignment.agent_id == agent_id:
                    task_status = await self.task_executor.get_task_status(assignment.task_id)
                    if task_status and task_status["status"] == "running":
                        running_tasks += 1
            
            agent_load[agent_id] = {
                "running_tasks": running_tasks,
                "capabilities": len(self.agent_capabilities.get(agent_id, [])),
                "enabled": self.agents[agent_id].is_enabled
            }
        
        return agent_load
    
    async def health_check(self) -> Dict[str, Any]:
        """Get coordinator health status"""
        return {
            "coordinator_running": True,
            "registered_agents": len(self.agents),
            "active_coordination_sessions": sum(
                1 for s in self.coordination_sessions.values()
                if s["status"] == CoordinationStatus.IN_PROGRESS
            ),
            "total_coordination_sessions": len(self.coordination_sessions),
            "task_assignments": len(self.task_assignments)
        }
