"""
Base Agent for Atulya Tantra AGI
Base class for all specialized agents
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Any, Optional

class BaseAgent(ABC):
    """Base class for all AI agents"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self.status = "initialized"
        self.capabilities = []
        self.memory = {}
        
    @abstractmethod
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task - must be implemented by subclasses"""
        pass
    
    async def initialize(self) -> bool:
        """Initialize the agent"""
        try:
            self.status = "ready"
            return True
        except Exception as e:
            self.status = "error"
            print(f"Agent {self.name} initialization error: {e}")
            return False
    
    async def get_status(self) -> Dict[str, Any]:
        """Get agent status"""
        return {
            'name': self.name,
            'status': self.status,
            'capabilities': self.capabilities,
            'timestamp': datetime.now().isoformat()
        }
    
    def add_capability(self, capability: str):
        """Add a capability to the agent"""
        if capability not in self.capabilities:
            self.capabilities.append(capability)
    
    def set_memory(self, key: str, value: Any):
        """Set memory value"""
        self.memory[key] = value
    
    def get_memory(self, key: str, default: Any = None) -> Any:
        """Get memory value"""
        return self.memory.get(key, default)