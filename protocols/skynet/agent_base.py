"""
SKYNET Protocol - Base Agent Class
Foundation for all specialized agents in SKYNET Protocol
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime
from core.logger import get_logger

logger = get_logger('protocols.skynet.agents')


class AgentType(Enum):
    """Types of specialized agents"""
    CONVERSATION = "conversation"
    CODE = "code"
    RESEARCH = "research"
    TASK_PLANNER = "task_planner"
    SYSTEM_CONTROL = "system_control"
    MEMORY = "memory"
    COORDINATOR = "coordinator"


class AgentStatus(Enum):
    """Agent operational status"""
    IDLE = "idle"
    ACTIVE = "active"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"


class BaseAgent(ABC):
    """
    Base class for all SKYNET agents
    
    All specialized agents inherit from this class
    Provides common functionality and interface
    """
    
    def __init__(self, agent_type: AgentType, name: str, config: Optional[Dict] = None):
        """
        Initialize base agent
        
        Args:
            agent_type: Type of agent
            name: Agent name
            config: Optional configuration dictionary
        """
        self.agent_type = agent_type
        self.name = name
        self.config = config or {}
        self.status = AgentStatus.IDLE
        self.tasks_completed = 0
        self.created_at = datetime.now()
        
        logger.info(f"Agent initialized: {self.name} ({self.agent_type.value})")
    
    @abstractmethod
    async def execute(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute agent-specific task
        
        Args:
            task: Task description
            context: Optional context dictionary
            
        Returns:
            Execution result
        """
        pass
    
    async def activate(self):
        """Activate agent"""
        self.status = AgentStatus.ACTIVE
        logger.info(f"Agent activated: {self.name}")
    
    async def deactivate(self):
        """Deactivate agent"""
        self.status = AgentStatus.OFFLINE
        logger.info(f"Agent deactivated: {self.name}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status"""
        uptime = datetime.now() - self.created_at
        
        return {
            'name': self.name,
            'type': self.agent_type.value,
            'status': self.status.value,
            'tasks_completed': self.tasks_completed,
            'uptime_seconds': uptime.total_seconds(),
            'config': self.config
        }
    
    def _mark_task_complete(self):
        """Mark task as completed (internal)"""
        self.tasks_completed += 1
        self.status = AgentStatus.IDLE
        logger.debug(f"Task completed by {self.name} (Total: {self.tasks_completed})")


class ConversationAgent(BaseAgent):
    """Agent specialized in natural conversation"""
    
    def __init__(self, name: str = "ConversationAgent", config: Optional[Dict] = None):
        super().__init__(AgentType.CONVERSATION, name, config)
        self.model = config.get('model', 'phi3:mini') if config else 'phi3:mini'
    
    async def execute(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute conversation task"""
        self.status = AgentStatus.BUSY
        
        try:
            import ollama
            import asyncio
            from configuration.prompts import get_prompt
            
            # Get conversation prompt
            system_prompt = get_prompt('conversation')
            
            messages = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': task}
            ]
            
            # Add context if provided
            if context:
                context_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
                messages.insert(1, {'role': 'system', 'content': f"Context:\n{context_str}"})
            
            # Generate response
            response = await asyncio.to_thread(
                ollama.chat,
                model=self.model,
                messages=messages,
                options={'num_predict': 150}
            )
            
            result = {
                'agent': self.name,
                'type': self.agent_type.value,
                'response': response['message']['content'],
                'success': True,
                'model': self.model
            }
            
            self._mark_task_complete()
            return result
            
        except Exception as e:
            logger.error(f"Conversation agent error: {e}")
            self.status = AgentStatus.ERROR
            return {
                'agent': self.name,
                'type': self.agent_type.value,
                'response': f'Error: {str(e)}',
                'success': False
            }


class CodeAgent(BaseAgent):
    """Agent specialized in code generation and analysis"""
    
    def __init__(self, name: str = "CodeAgent", config: Optional[Dict] = None):
        super().__init__(AgentType.CODE, name, config)
        self.model = config.get('model', 'phi3:mini') if config else 'phi3:mini'
    
    async def execute(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute code-related task"""
        self.status = AgentStatus.BUSY
        
        try:
            import ollama
            import asyncio
            from configuration.prompts import get_prompt
            
            # Get code prompt
            system_prompt = get_prompt('code')
            
            messages = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': task}
            ]
            
            # Add context if provided
            if context:
                context_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
                messages.insert(1, {'role': 'system', 'content': f"Context:\n{context_str}"})
            
            # Generate response
            response = await asyncio.to_thread(
                ollama.chat,
                model=self.model,
                messages=messages,
                options={'num_predict': 200}  # More tokens for code
            )
            
            result = {
                'agent': self.name,
                'type': self.agent_type.value,
                'response': response['message']['content'],
                'success': True,
                'model': self.model
            }
            
            self._mark_task_complete()
            return result
            
        except Exception as e:
            logger.error(f"Code agent error: {e}")
            self.status = AgentStatus.ERROR
            return {
                'agent': self.name,
                'type': self.agent_type.value,
                'response': f'Error: {str(e)}',
                'success': False
            }


__all__ = [
    'BaseAgent',
    'AgentType',
    'AgentStatus',
    'ConversationAgent',
    'CodeAgent',
]

