"""
Agent Factory for Atulya Tantra AGI
Dynamic agent creation and management
"""

import uuid
import asyncio
from typing import Dict, Any, List, Optional, Type, Callable
from datetime import datetime
from dataclasses import dataclass

from ..config.logging import get_logger
from ..config.exceptions import SystemError, ValidationError
from ..agents.base_agent import BaseAgent
from ..agents.code_agent import CodeAgent
from ..agents.creative_agent import CreativeAgent
from ..agents.data_agent import DataAgent
from ..agents.research_agent import ResearchAgent
from ..agents.system_agent import SystemAgent

logger = get_logger(__name__)


@dataclass
class AgentConfig:
    """Agent configuration"""
    id: str
    name: str
    agent_type: str
    capabilities: List[str]
    config: Dict[str, Any]
    created_at: str
    updated_at: str
    status: str


@dataclass
class AgentInstance:
    """Agent instance"""
    id: str
    config: AgentConfig
    agent: BaseAgent
    created_at: str
    status: str
    stats: Dict[str, Any]


class AgentFactory:
    """Dynamic agent factory"""
    
    def __init__(self):
        self.agent_types: Dict[str, Type[BaseAgent]] = {
            "code": CodeAgent,
            "creative": CreativeAgent,
            "data": DataAgent,
            "research": ResearchAgent,
            "system": SystemAgent
        }
        
        self.agent_instances: Dict[str, AgentInstance] = {}
        self.agent_configs: Dict[str, AgentConfig] = {}
        
        # Agent capabilities registry
        self.capability_registry: Dict[str, List[str]] = {
            "code": [
                "code_generation", "code_analysis", "debugging", "refactoring",
                "testing", "optimization", "documentation", "code_review"
            ],
            "creative": [
                "content_generation", "storytelling", "poetry", "music",
                "art", "design", "brainstorming", "editing"
            ],
            "data": [
                "data_analysis", "data_processing", "visualization",
                "prediction", "cleaning", "transformation", "statistics"
            ],
            "research": [
                "information_search", "analysis", "summarization",
                "fact_checking", "synthesis", "citation", "verification"
            ],
            "system": [
                "monitoring", "optimization", "maintenance", "diagnosis",
                "backup", "security", "performance", "health_check"
            ]
        }
        
        # Initialize default agents
        self._initialize_default_agents()
        
        logger.info("Initialized Agent Factory")
    
    def _initialize_default_agents(self):
        """Initialize default agent configurations"""
        try:
            # Code Agent
            self.add_agent_config(
                id="default_code_agent",
                name="Code Assistant",
                agent_type="code",
                capabilities=["code_generation", "code_analysis", "debugging"],
                config={
                    "max_tokens": 2000,
                    "temperature": 0.7,
                    "languages": ["python", "javascript", "typescript", "java", "go"]
                }
            )
            
            # Creative Agent
            self.add_agent_config(
                id="default_creative_agent",
                name="Creative Assistant",
                agent_type="creative",
                capabilities=["content_generation", "storytelling", "brainstorming"],
                config={
                    "max_tokens": 1500,
                    "temperature": 0.8,
                    "styles": ["professional", "casual", "creative", "technical"]
                }
            )
            
            # Data Agent
            self.add_agent_config(
                id="default_data_agent",
                name="Data Analyst",
                agent_type="data",
                capabilities=["data_analysis", "visualization", "statistics"],
                config={
                    "max_tokens": 1000,
                    "temperature": 0.3,
                    "chart_types": ["line", "bar", "pie", "scatter", "histogram"]
                }
            )
            
            # Research Agent
            self.add_agent_config(
                id="default_research_agent",
                name="Research Assistant",
                agent_type="research",
                capabilities=["information_search", "analysis", "summarization"],
                config={
                    "max_tokens": 2500,
                    "temperature": 0.4,
                    "sources": ["web", "academic", "news", "technical"]
                }
            )
            
            # System Agent
            self.add_agent_config(
                id="default_system_agent",
                name="System Monitor",
                agent_type="system",
                capabilities=["monitoring", "optimization", "maintenance"],
                config={
                    "max_tokens": 500,
                    "temperature": 0.2,
                    "monitoring_interval": 30,
                    "alert_thresholds": {
                        "cpu": 80,
                        "memory": 85,
                        "disk": 90
                    }
                }
            )
            
            logger.info("Initialized default agent configurations")
            
        except Exception as e:
            logger.error(f"Error initializing default agents: {e}")
    
    def add_agent_config(
        self,
        id: str,
        name: str,
        agent_type: str,
        capabilities: List[str],
        config: Dict[str, Any] = None
    ) -> bool:
        """Add an agent configuration"""
        try:
            if agent_type not in self.agent_types:
                raise ValidationError(f"Unknown agent type: {agent_type}")
            
            # Validate capabilities
            valid_capabilities = self.capability_registry.get(agent_type, [])
            for capability in capabilities:
                if capability not in valid_capabilities:
                    logger.warning(f"Unknown capability for {agent_type}: {capability}")
            
            agent_config = AgentConfig(
                id=id,
                name=name,
                agent_type=agent_type,
                capabilities=capabilities,
                config=config or {},
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                status="inactive"
            )
            
            self.agent_configs[id] = agent_config
            logger.info(f"Added agent configuration: {id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding agent configuration: {e}")
            return False
    
    def update_agent_config(
        self,
        id: str,
        **kwargs
    ) -> bool:
        """Update an agent configuration"""
        try:
            if id not in self.agent_configs:
                return False
            
            agent_config = self.agent_configs[id]
            
            # Update allowed fields
            allowed_fields = ["name", "capabilities", "config"]
            for field, value in kwargs.items():
                if field in allowed_fields:
                    setattr(agent_config, field, value)
            
            agent_config.updated_at = datetime.now().isoformat()
            
            logger.info(f"Updated agent configuration: {id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating agent configuration: {e}")
            return False
    
    def remove_agent_config(self, id: str) -> bool:
        """Remove an agent configuration"""
        try:
            if id in self.agent_configs:
                del self.agent_configs[id]
                logger.info(f"Removed agent configuration: {id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error removing agent configuration: {e}")
            return False
    
    async def create_agent(
        self,
        config_id: str,
        instance_id: str = None
    ) -> Optional[str]:
        """Create an agent instance"""
        try:
            if config_id not in self.agent_configs:
                raise ValidationError(f"Agent configuration not found: {config_id}")
            
            agent_config = self.agent_configs[config_id]
            
            if instance_id is None:
                instance_id = f"{config_id}_{uuid.uuid4().hex[:8]}"
            
            # Check if instance already exists
            if instance_id in self.agent_instances:
                raise ValidationError(f"Agent instance already exists: {instance_id}")
            
            # Get agent class
            agent_class = self.agent_types[agent_config.agent_type]
            
            # Create agent instance
            agent = agent_class(
                agent_id=instance_id,
                name=agent_config.name,
                capabilities=agent_config.capabilities,
                config=agent_config.config
            )
            
            # Create agent instance record
            agent_instance = AgentInstance(
                id=instance_id,
                config=agent_config,
                agent=agent,
                created_at=datetime.now().isoformat(),
                status="created",
                stats={
                    "tasks_completed": 0,
                    "tasks_failed": 0,
                    "total_runtime": 0,
                    "last_activity": None
                }
            )
            
            self.agent_instances[instance_id] = agent_instance
            
            logger.info(f"Created agent instance: {instance_id}")
            return instance_id
            
        except Exception as e:
            logger.error(f"Error creating agent instance: {e}")
            return None
    
    async def start_agent(self, instance_id: str) -> bool:
        """Start an agent instance"""
        try:
            if instance_id not in self.agent_instances:
                return False
            
            agent_instance = self.agent_instances[instance_id]
            
            # Start the agent
            await agent_instance.agent.start()
            
            # Update status
            agent_instance.status = "running"
            agent_instance.stats["last_activity"] = datetime.now().isoformat()
            
            logger.info(f"Started agent instance: {instance_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting agent instance: {e}")
            return False
    
    async def stop_agent(self, instance_id: str) -> bool:
        """Stop an agent instance"""
        try:
            if instance_id not in self.agent_instances:
                return False
            
            agent_instance = self.agent_instances[instance_id]
            
            # Stop the agent
            await agent_instance.agent.stop()
            
            # Update status
            agent_instance.status = "stopped"
            agent_instance.stats["last_activity"] = datetime.now().isoformat()
            
            logger.info(f"Stopped agent instance: {instance_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping agent instance: {e}")
            return False
    
    async def restart_agent(self, instance_id: str) -> bool:
        """Restart an agent instance"""
        try:
            await self.stop_agent(instance_id)
            await asyncio.sleep(1)  # Brief pause
            return await self.start_agent(instance_id)
            
        except Exception as e:
            logger.error(f"Error restarting agent instance: {e}")
            return False
    
    async def remove_agent(self, instance_id: str) -> bool:
        """Remove an agent instance"""
        try:
            if instance_id not in self.agent_instances:
                return False
            
            agent_instance = self.agent_instances[instance_id]
            
            # Stop the agent if running
            if agent_instance.status == "running":
                await self.stop_agent(instance_id)
            
            # Remove instance
            del self.agent_instances[instance_id]
            
            logger.info(f"Removed agent instance: {instance_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error removing agent instance: {e}")
            return False
    
    def get_agent(self, instance_id: str) -> Optional[AgentInstance]:
        """Get an agent instance"""
        return self.agent_instances.get(instance_id)
    
    def get_all_agents(self) -> List[AgentInstance]:
        """Get all agent instances"""
        return list(self.agent_instances.values())
    
    def get_agents_by_type(self, agent_type: str) -> List[AgentInstance]:
        """Get agents by type"""
        return [
            instance for instance in self.agent_instances.values()
            if instance.config.agent_type == agent_type
        ]
    
    def get_agents_by_capability(self, capability: str) -> List[AgentInstance]:
        """Get agents by capability"""
        return [
            instance for instance in self.agent_instances.values()
            if capability in instance.config.capabilities
        ]
    
    async def execute_task(
        self,
        instance_id: str,
        task: str,
        parameters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute a task on an agent"""
        try:
            if instance_id not in self.agent_instances:
                raise ValidationError(f"Agent instance not found: {instance_id}")
            
            agent_instance = self.agent_instances[instance_id]
            
            if agent_instance.status != "running":
                raise SystemError(f"Agent is not running: {instance_id}")
            
            # Execute task
            start_time = datetime.now()
            result = await agent_instance.agent.execute_task(task, parameters or {})
            end_time = datetime.now()
            
            # Update stats
            agent_instance.stats["tasks_completed"] += 1
            agent_instance.stats["total_runtime"] += (end_time - start_time).total_seconds()
            agent_instance.stats["last_activity"] = end_time.isoformat()
            
            logger.info(f"Executed task on agent {instance_id}: {task}")
            return result
            
        except Exception as e:
            logger.error(f"Error executing task on agent: {e}")
            
            # Update failure stats
            if instance_id in self.agent_instances:
                agent_instance = self.agent_instances[instance_id]
                agent_instance.stats["tasks_failed"] += 1
                agent_instance.stats["last_activity"] = datetime.now().isoformat()
            
            raise
    
    async def get_agent_status(self, instance_id: str) -> Dict[str, Any]:
        """Get agent status"""
        try:
            if instance_id not in self.agent_instances:
                return {}
            
            agent_instance = self.agent_instances[instance_id]
            
            return {
                "id": agent_instance.id,
                "name": agent_instance.config.name,
                "type": agent_instance.config.agent_type,
                "status": agent_instance.status,
                "capabilities": agent_instance.config.capabilities,
                "stats": agent_instance.stats,
                "created_at": agent_instance.created_at,
                "config": agent_instance.config.config
            }
            
        except Exception as e:
            logger.error(f"Error getting agent status: {e}")
            return {}
    
    async def get_factory_stats(self) -> Dict[str, Any]:
        """Get factory statistics"""
        try:
            total_agents = len(self.agent_instances)
            running_agents = len([a for a in self.agent_instances.values() if a.status == "running"])
            stopped_agents = len([a for a in self.agent_instances.values() if a.status == "stopped"])
            
            # Count by type
            type_counts = {}
            for instance in self.agent_instances.values():
                agent_type = instance.config.agent_type
                type_counts[agent_type] = type_counts.get(agent_type, 0) + 1
            
            # Total tasks
            total_tasks = sum(instance.stats["tasks_completed"] for instance in self.agent_instances.values())
            total_failures = sum(instance.stats["tasks_failed"] for instance in self.agent_instances.values())
            
            return {
                "total_agents": total_agents,
                "running_agents": running_agents,
                "stopped_agents": stopped_agents,
                "type_counts": type_counts,
                "total_tasks": total_tasks,
                "total_failures": total_failures,
                "success_rate": total_tasks / (total_tasks + total_failures) if (total_tasks + total_failures) > 0 else 0,
                "configurations": len(self.agent_configs),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting factory stats: {e}")
            return {}
    
    def register_agent_type(
        self,
        agent_type: str,
        agent_class: Type[BaseAgent],
        capabilities: List[str]
    ) -> bool:
        """Register a new agent type"""
        try:
            self.agent_types[agent_type] = agent_class
            self.capability_registry[agent_type] = capabilities
            
            logger.info(f"Registered agent type: {agent_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error registering agent type: {e}")
            return False
    
    def get_available_capabilities(self) -> Dict[str, List[str]]:
        """Get available capabilities by agent type"""
        return self.capability_registry.copy()
    
    def get_agent_types(self) -> List[str]:
        """Get available agent types"""
        return list(self.agent_types.keys())


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
    "AgentConfig",
    "AgentInstance",
    "AgentFactory",
    "get_agent_factory"
]