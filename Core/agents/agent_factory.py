"""
Agent Factory for Atulya Tantra AGI
Factory for creating and managing agent instances
"""

from typing import Dict, List, Optional, Type
from datetime import datetime

from .base_agent import BaseAgent
from .code_agent import CodeAgent
from .creative_agent import CreativeAgent
from .data_agent import DataAgent
from .research_agent import ResearchAgent
from .system_agent import SystemAgent
from ..config.logging import get_logger
from ..config.exceptions import AgentError, ValidationError

logger = get_logger(__name__)


class AgentFactory:
    """Factory for creating and managing agents"""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.agent_types: Dict[str, Type[BaseAgent]] = {
            "code": CodeAgent,
            "creative": CreativeAgent,
            "data": DataAgent,
            "research": ResearchAgent,
            "system": SystemAgent
        }
        self._initialize_default_agents()
    
    def _initialize_default_agents(self):
        """Initialize default agent instances"""
        try:
            for agent_type, agent_class in self.agent_types.items():
                agent = agent_class()
                self.agents[agent.agent_id] = agent
                logger.info(f"Initialized {agent_type} agent: {agent.agent_id}")
        except Exception as e:
            logger.error(f"Error initializing default agents: {e}")
            raise AgentError(f"Failed to initialize default agents: {e}")
    
    def create_agent(self, agent_type: str, agent_id: Optional[str] = None, **kwargs) -> BaseAgent:
        """Create a new agent instance"""
        try:
            if agent_type not in self.agent_types:
                raise ValidationError(f"Unknown agent type: {agent_type}")
            
            agent_class = self.agent_types[agent_type]
            agent = agent_class()
            
            if agent_id:
                agent.agent_id = agent_id
            
            # Apply any additional configuration
            for key, value in kwargs.items():
                if hasattr(agent, key):
                    setattr(agent, key, value)
            
            self.agents[agent.agent_id] = agent
            logger.info(f"Created {agent_type} agent: {agent.agent_id}")
            
            return agent
            
        except Exception as e:
            logger.error(f"Error creating agent: {e}")
            raise AgentError(f"Failed to create agent: {e}")
    
    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get agent by ID"""
        return self.agents.get(agent_id)
    
    def get_agents_by_type(self, agent_type: str) -> List[BaseAgent]:
        """Get all agents of a specific type"""
        return [
            agent for agent in self.agents.values()
            if agent.__class__.__name__.lower().replace("agent", "") == agent_type.lower()
        ]
    
    def get_all_agents(self) -> List[BaseAgent]:
        """Get all agent instances"""
        return list(self.agents.values())
    
    def get_available_agents(self) -> List[BaseAgent]:
        """Get all available (not busy) agents"""
        return [
            agent for agent in self.agents.values()
            if agent.status.value == "idle"
        ]
    
    def get_agents_by_capability(self, capability: str) -> List[BaseAgent]:
        """Get agents with specific capability"""
        return [
            agent for agent in self.agents.values()
            if capability in [cap.value for cap in agent.capabilities]
        ]
    
    def start_agent(self, agent_id: str) -> bool:
        """Start an agent"""
        try:
            agent = self.get_agent(agent_id)
            if not agent:
                raise ValidationError(f"Agent not found: {agent_id}")
            
            success = agent.start()
            if success:
                logger.info(f"Started agent: {agent_id}")
            else:
                logger.warning(f"Failed to start agent: {agent_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error starting agent: {e}")
            return False
    
    def stop_agent(self, agent_id: str) -> bool:
        """Stop an agent"""
        try:
            agent = self.get_agent(agent_id)
            if not agent:
                raise ValidationError(f"Agent not found: {agent_id}")
            
            success = agent.stop()
            if success:
                logger.info(f"Stopped agent: {agent_id}")
            else:
                logger.warning(f"Failed to stop agent: {agent_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error stopping agent: {e}")
            return False
    
    def restart_agent(self, agent_id: str) -> bool:
        """Restart an agent"""
        try:
            # Stop agent
            stop_success = self.stop_agent(agent_id)
            if not stop_success:
                return False
            
            # Start agent
            start_success = self.start_agent(agent_id)
            if start_success:
                logger.info(f"Restarted agent: {agent_id}")
            
            return start_success
            
        except Exception as e:
            logger.error(f"Error restarting agent: {e}")
            return False
    
    def remove_agent(self, agent_id: str) -> bool:
        """Remove an agent from the factory"""
        try:
            agent = self.get_agent(agent_id)
            if not agent:
                return False
            
            # Stop agent if running
            if agent.status.value == "running":
                agent.stop()
            
            # Remove from factory
            del self.agents[agent_id]
            logger.info(f"Removed agent: {agent_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error removing agent: {e}")
            return False
    
    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, any]]:
        """Get agent status information"""
        try:
            agent = self.get_agent(agent_id)
            if not agent:
                return None
            
            return {
                "agent_id": agent.agent_id,
                "name": agent.name,
                "status": agent.status.value,
                "capabilities": [cap.value for cap in agent.capabilities],
                "priority": agent.priority.value,
                "created_at": agent.created_at.isoformat(),
                "last_active": agent.last_active.isoformat(),
                "metadata": agent.metadata
            }
            
        except Exception as e:
            logger.error(f"Error getting agent status: {e}")
            return None
    
    def get_factory_status(self) -> Dict[str, any]:
        """Get factory status information"""
        try:
            total_agents = len(self.agents)
            running_agents = len([a for a in self.agents.values() if a.status.value == "running"])
            idle_agents = len([a for a in self.agents.values() if a.status.value == "idle"])
            stopped_agents = len([a for a in self.agents.values() if a.status.value == "stopped"])
            
            return {
                "total_agents": total_agents,
                "running_agents": running_agents,
                "idle_agents": idle_agents,
                "stopped_agents": stopped_agents,
                "agent_types": list(self.agent_types.keys()),
                "factory_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting factory status: {e}")
            return {}
    
    def find_best_agent(self, task_type: str, required_capabilities: List[str]) -> Optional[BaseAgent]:
        """Find the best agent for a task"""
        try:
            # Get agents with required capabilities
            capable_agents = []
            for agent in self.agents.values():
                agent_capabilities = [cap.value for cap in agent.capabilities]
                if all(cap in agent_capabilities for cap in required_capabilities):
                    capable_agents.append(agent)
            
            if not capable_agents:
                return None
            
            # Filter by availability
            available_agents = [agent for agent in capable_agents if agent.status.value == "idle"]
            
            if not available_agents:
                return None
            
            # Sort by priority and return the best one
            available_agents.sort(key=lambda x: x.priority.value, reverse=True)
            return available_agents[0]
            
        except Exception as e:
            logger.error(f"Error finding best agent: {e}")
            return None
    
    def get_agent_statistics(self) -> Dict[str, any]:
        """Get agent statistics"""
        try:
            stats = {
                "total_agents": len(self.agents),
                "agents_by_type": {},
                "agents_by_status": {},
                "agents_by_priority": {},
                "capability_distribution": {}
            }
            
            # Count by type
            for agent in self.agents.values():
                agent_type = agent.__class__.__name__.lower().replace("agent", "")
                stats["agents_by_type"][agent_type] = stats["agents_by_type"].get(agent_type, 0) + 1
            
            # Count by status
            for agent in self.agents.values():
                status = agent.status.value
                stats["agents_by_status"][status] = stats["agents_by_status"].get(status, 0) + 1
            
            # Count by priority
            for agent in self.agents.values():
                priority = agent.priority.value
                stats["agents_by_priority"][priority] = stats["agents_by_priority"].get(priority, 0) + 1
            
            # Count capabilities
            for agent in self.agents.values():
                for capability in agent.capabilities:
                    cap_name = capability.value
                    stats["capability_distribution"][cap_name] = stats["capability_distribution"].get(cap_name, 0) + 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting agent statistics: {e}")
            return {}
    
    def configure_agent(self, agent_id: str, configuration: Dict[str, any]) -> bool:
        """Configure an agent"""
        try:
            agent = self.get_agent(agent_id)
            if not agent:
                raise ValidationError(f"Agent not found: {agent_id}")
            
            # Apply configuration
            for key, value in configuration.items():
                if hasattr(agent, key):
                    setattr(agent, key, value)
                else:
                    logger.warning(f"Unknown configuration key: {key}")
            
            logger.info(f"Configured agent: {agent_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error configuring agent: {e}")
            return False
    
    def get_agent_health(self, agent_id: str) -> Optional[Dict[str, any]]:
        """Get agent health information"""
        try:
            agent = self.get_agent(agent_id)
            if not agent:
                return None
            
            return {
                "agent_id": agent_id,
                "health_status": "healthy",
                "uptime": agent.get_uptime(),
                "task_count": len(agent.get_tasks()),
                "error_count": 0,  # Mock error count
                "last_health_check": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting agent health: {e}")
            return None
    
    def cleanup_inactive_agents(self, max_inactive_hours: int = 24) -> int:
        """Clean up inactive agents"""
        try:
            current_time = datetime.now()
            cleaned_count = 0
            
            agents_to_remove = []
            for agent_id, agent in self.agents.items():
                # Check if agent has been inactive for too long
                inactive_hours = (current_time - agent.last_active).total_seconds() / 3600
                if inactive_hours > max_inactive_hours and agent.status.value == "stopped":
                    agents_to_remove.append(agent_id)
            
            # Remove inactive agents
            for agent_id in agents_to_remove:
                if self.remove_agent(agent_id):
                    cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} inactive agents")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error cleaning up inactive agents: {e}")
            return 0


# Global agent factory instance
_agent_factory = None


def get_agent_factory() -> AgentFactory:
    """Get global agent factory instance"""
    global _agent_factory
    if _agent_factory is None:
        _agent_factory = AgentFactory()
    return _agent_factory


# Export public API
__all__ = [
    "AgentFactory",
    "get_agent_factory"
]