"""
Atulya Tantra - Base Classes
Shared base classes for all components
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
from .logger import get_logger


class BaseProtocol(ABC):
    """Base class for all protocols (JARVIS, SKYNET, etc.)"""
    
    def __init__(self, name: str):
        self.name = name
        self.is_active = False
        self.created_at = datetime.now()
        self.logger = get_logger(f'protocols.{name.lower()}')
    
    @abstractmethod
    async def activate(self) -> Dict[str, Any]:
        """Activate protocol"""
        pass
    
    @abstractmethod
    async def deactivate(self) -> Dict[str, Any]:
        """Deactivate protocol"""
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get protocol status"""
        pass


class BaseAgent(ABC):
    """Base class for all agents"""
    
    def __init__(self, agent_type: str, name: str):
        self.agent_type = agent_type
        self.name = name
        self.tasks_completed = 0
        self.created_at = datetime.now()
        self.logger = get_logger(f'agents.{name.lower()}')
    
    @abstractmethod
    async def execute(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute agent task"""
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status"""
        uptime = (datetime.now() - self.created_at).total_seconds()
        return {
            'name': self.name,
            'type': self.agent_type,
            'tasks_completed': self.tasks_completed,
            'uptime_seconds': uptime
        }


class BaseManager(ABC):
    """Base class for all managers (conversation, memory, etc.)"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger(f'managers.{name.lower()}')
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get manager status"""
        pass


__all__ = ['BaseProtocol', 'BaseAgent', 'BaseManager']

