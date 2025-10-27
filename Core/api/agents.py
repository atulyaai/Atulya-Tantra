"""
Agent Management API for Atulya Tantra AGI
Agent operations, status, and management endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from ..agents.base_agent import BaseAgent, AgentStatus, AgentCapability
from ..agents.agent_factory import AgentFactory
from ..auth.jwt import verify_token, TokenData
from ..config.logging import get_logger
from ..config.exceptions import AgentError, ValidationError

logger = get_logger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentResponse(BaseModel):
    """Agent response model"""
    agent_id: str
    name: str
    status: str
    capabilities: List[str]
    created_at: str
    last_active: str
    metadata: Dict[str, Any] = {}


class AgentTaskRequest(BaseModel):
    """Agent task request model"""
    task_type: str
    description: str
    priority: int = 1
    parameters: Dict[str, Any] = {}
    timeout: Optional[int] = None


class AgentTaskResponse(BaseModel):
    """Agent task response model"""
    task_id: str
    agent_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


def get_current_user(token: str = Depends(verify_token)) -> TokenData:
    """Get current user from token"""
    return token


@router.get("/", response_model=List[AgentResponse])
async def list_agents(current_user: TokenData = Depends(get_current_user)):
    """List all available agents"""
    try:
        agent_factory = AgentFactory()
        agents = agent_factory.get_all_agents()
        
        agent_responses = []
        for agent in agents:
            agent_responses.append(AgentResponse(
                agent_id=agent.agent_id,
                name=agent.name,
                status=agent.status.value,
                capabilities=[cap.value for cap in agent.capabilities],
                created_at=agent.created_at.isoformat(),
                last_active=agent.last_active.isoformat(),
                metadata=agent.metadata
            ))
        
        return agent_responses
        
    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        raise HTTPException(status_code=500, detail="Failed to list agents")


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, current_user: TokenData = Depends(get_current_user)):
    """Get specific agent details"""
    try:
        agent_factory = AgentFactory()
        agent = agent_factory.get_agent(agent_id)
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        return AgentResponse(
            agent_id=agent.agent_id,
            name=agent.name,
            status=agent.status.value,
            capabilities=[cap.value for cap in agent.capabilities],
            created_at=agent.created_at.isoformat(),
            last_active=agent.last_active.isoformat(),
            metadata=agent.metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to get agent")


@router.post("/{agent_id}/start")
async def start_agent(agent_id: str, current_user: TokenData = Depends(get_current_user)):
    """Start an agent"""
    try:
        agent_factory = AgentFactory()
        agent = agent_factory.get_agent(agent_id)
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        if agent.status == AgentStatus.RUNNING:
            raise HTTPException(status_code=400, detail="Agent is already running")
        
        success = agent.start()
        if not success:
            raise HTTPException(status_code=500, detail="Failed to start agent")
        
        return {"message": f"Agent {agent_id} started successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to start agent")


@router.post("/{agent_id}/stop")
async def stop_agent(agent_id: str, current_user: TokenData = Depends(get_current_user)):
    """Stop an agent"""
    try:
        agent_factory = AgentFactory()
        agent = agent_factory.get_agent(agent_id)
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        if agent.status == AgentStatus.STOPPED:
            raise HTTPException(status_code=400, detail="Agent is already stopped")
        
        success = agent.stop()
        if not success:
            raise HTTPException(status_code=500, detail="Failed to stop agent")
        
        return {"message": f"Agent {agent_id} stopped successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop agent")


@router.post("/{agent_id}/restart")
async def restart_agent(agent_id: str, current_user: TokenData = Depends(get_current_user)):
    """Restart an agent"""
    try:
        agent_factory = AgentFactory()
        agent = agent_factory.get_agent(agent_id)
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Stop agent
        agent.stop()
        
        # Start agent
        success = agent.start()
        if not success:
            raise HTTPException(status_code=500, detail="Failed to restart agent")
        
        return {"message": f"Agent {agent_id} restarted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restarting agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to restart agent")


@router.post("/{agent_id}/tasks", response_model=AgentTaskResponse)
async def create_task(
    agent_id: str,
    task_request: AgentTaskRequest,
    background_tasks: BackgroundTasks,
    current_user: TokenData = Depends(get_current_user)
):
    """Create a new task for an agent"""
    try:
        agent_factory = AgentFactory()
        agent = agent_factory.get_agent(agent_id)
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        if agent.status != AgentStatus.RUNNING:
            raise HTTPException(status_code=400, detail="Agent is not running")
        
        # Create task
        task = agent.create_task(
            task_type=task_request.task_type,
            description=task_request.description,
            priority=task_request.priority,
            parameters=task_request.parameters,
            timeout=task_request.timeout
        )
        
        # Execute task in background
        background_tasks.add_task(agent.execute_task, task.task_id)
        
        return AgentTaskResponse(
            task_id=task.task_id,
            agent_id=agent_id,
            status=task.status.value,
            created_at=task.created_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail="Failed to create task")


@router.get("/{agent_id}/tasks", response_model=List[AgentTaskResponse])
async def list_agent_tasks(agent_id: str, current_user: TokenData = Depends(get_current_user)):
    """List tasks for an agent"""
    try:
        agent_factory = AgentFactory()
        agent = agent_factory.get_agent(agent_id)
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        tasks = agent.get_tasks()
        task_responses = []
        
        for task in tasks:
            task_responses.append(AgentTaskResponse(
                task_id=task.task_id,
                agent_id=agent_id,
                status=task.status.value,
                result=task.result,
                error=task.error,
                created_at=task.created_at.isoformat(),
                completed_at=task.completed_at.isoformat() if task.completed_at else None
            ))
        
        return task_responses
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing agent tasks: {e}")
        raise HTTPException(status_code=500, detail="Failed to list agent tasks")


@router.get("/{agent_id}/tasks/{task_id}", response_model=AgentTaskResponse)
async def get_task(
    agent_id: str,
    task_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Get specific task details"""
    try:
        agent_factory = AgentFactory()
        agent = agent_factory.get_agent(agent_id)
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        task = agent.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return AgentTaskResponse(
            task_id=task.task_id,
            agent_id=agent_id,
            status=task.status.value,
            result=task.result,
            error=task.error,
            created_at=task.created_at.isoformat(),
            completed_at=task.completed_at.isoformat() if task.completed_at else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task: {e}")
        raise HTTPException(status_code=500, detail="Failed to get task")


@router.delete("/{agent_id}/tasks/{task_id}")
async def cancel_task(
    agent_id: str,
    task_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Cancel a task"""
    try:
        agent_factory = AgentFactory()
        agent = agent_factory.get_agent(agent_id)
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        success = agent.cancel_task(task_id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to cancel task")
        
        return {"message": f"Task {task_id} cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling task: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel task")


@router.get("/{agent_id}/status")
async def get_agent_status(agent_id: str, current_user: TokenData = Depends(get_current_user)):
    """Get agent status and health"""
    try:
        agent_factory = AgentFactory()
        agent = agent_factory.get_agent(agent_id)
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        return {
            "agent_id": agent_id,
            "status": agent.status.value,
            "health": agent.get_health_status(),
            "uptime": agent.get_uptime(),
            "task_count": len(agent.get_tasks()),
            "active_tasks": len([t for t in agent.get_tasks() if t.status.value == "running"])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get agent status")


@router.post("/{agent_id}/configure")
async def configure_agent(
    agent_id: str,
    configuration: Dict[str, Any],
    current_user: TokenData = Depends(get_current_user)
):
    """Configure agent settings"""
    try:
        agent_factory = AgentFactory()
        agent = agent_factory.get_agent(agent_id)
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        success = agent.configure(configuration)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to configure agent")
        
        return {"message": f"Agent {agent_id} configured successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error configuring agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to configure agent")