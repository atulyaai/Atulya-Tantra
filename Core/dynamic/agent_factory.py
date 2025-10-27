"""
Dynamic Agent Factory
Creates new agents on demand based on requirements and capabilities
"""

import asyncio
import inspect
import importlib
import json
from typing import Dict, List, Any, Optional, Type, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading
import time

from ..config.logging import get_logger
from ..config.exceptions import AgentError

logger = get_logger(__name__)


class AgentCapability(str, Enum):
    """Agent capabilities"""
    TEXT_PROCESSING = "text_processing"
    CODE_GENERATION = "code_generation"
    DATA_ANALYSIS = "data_analysis"
    WEB_SEARCH = "web_search"
    FILE_OPERATIONS = "file_operations"
    SYSTEM_CONTROL = "system_control"
    IMAGE_PROCESSING = "image_processing"
    VOICE_PROCESSING = "voice_processing"
    DATABASE_OPERATIONS = "database_operations"
    API_INTEGRATION = "api_integration"
    MACHINE_LEARNING = "machine_learning"
    AUTOMATION = "automation"


class AgentType(str, Enum):
    """Agent types"""
    SPECIALIST = "specialist"  # Focused on specific domain
    GENERALIST = "generalist"  # Broad capabilities
    COORDINATOR = "coordinator"  # Manages other agents
    MONITOR = "monitor"  # Monitors system health
    LEARNER = "learner"  # Learns and adapts


@dataclass
class AgentSpecification:
    """Agent specification for dynamic creation"""
    name: str
    type: AgentType
    capabilities: List[AgentCapability]
    description: str
    tools: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    priority: int = 1
    max_concurrent_tasks: int = 5
    learning_enabled: bool = True


@dataclass
class AgentTemplate:
    """Template for creating agents"""
    name: str
    base_class: str
    capabilities: List[AgentCapability]
    tools: List[str]
    code_template: str
    config_schema: Dict[str, Any]


class DynamicAgent:
    """Dynamically created agent"""
    
    def __init__(self, spec: AgentSpecification, agent_class: Type, instance: Any):
        self.spec = spec
        self.agent_class = agent_class
        self.instance = instance
        self.created_at = datetime.utcnow()
        self.status = "idle"
        self.active_tasks = 0
        self.total_tasks = 0
        self.success_rate = 0.0
        self.last_activity = None
        
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task using this agent"""
        try:
            self.status = "busy"
            self.active_tasks += 1
            self.total_tasks += 1
            self.last_activity = datetime.utcnow()
            
            # Execute the task
            if hasattr(self.instance, 'execute_task'):
                result = await self.instance.execute_task(task)
            elif hasattr(self.instance, 'process'):
                result = await self.instance.process(task)
            else:
                result = {"success": False, "error": "No execution method found"}
            
            # Update success rate
            if result.get("success", False):
                self.success_rate = ((self.success_rate * (self.total_tasks - 1)) + 1) / self.total_tasks
            else:
                self.success_rate = (self.success_rate * (self.total_tasks - 1)) / self.total_tasks
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing task with agent {self.spec.name}: {e}")
            return {"success": False, "error": str(e)}
        finally:
            self.active_tasks -= 1
            if self.active_tasks == 0:
                self.status = "idle"
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status"""
        return {
            "name": self.spec.name,
            "type": self.spec.type.value,
            "capabilities": [cap.value for cap in self.spec.capabilities],
            "status": self.status,
            "active_tasks": self.active_tasks,
            "total_tasks": self.total_tasks,
            "success_rate": self.success_rate,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat() if self.last_activity else None
        }


class AgentFactory:
    """Factory for creating dynamic agents"""
    
    def __init__(self):
        self.agent_templates: Dict[str, AgentTemplate] = {}
        self.created_agents: Dict[str, DynamicAgent] = {}
        self.agent_registry: Dict[str, Type] = {}
        
        # Load base agent templates
        self._load_agent_templates()
        
        # Register base agent classes
        self._register_base_agents()
    
    def _load_agent_templates(self):
        """Load agent templates for different types"""
        
        # Generalist Agent Template
        generalist_template = AgentTemplate(
            name="generalist",
            base_class="BaseAgent",
            capabilities=[
                AgentCapability.TEXT_PROCESSING,
                AgentCapability.CODE_GENERATION,
                AgentCapability.DATA_ANALYSIS,
                AgentCapability.WEB_SEARCH,
                AgentCapability.FILE_OPERATIONS
            ],
            tools=["text_processor", "code_generator", "data_analyzer", "web_searcher", "file_manager"],
            code_template="""
class {agent_name}(BaseAgent):
    def __init__(self, config=None):
        super().__init__(config)
        self.capabilities = {capabilities}
        self.tools = {tools}
    
    async def execute_task(self, task):
        task_type = task.get('type', 'general')
        
        if task_type == 'text_processing':
            return await self._process_text(task)
        elif task_type == 'code_generation':
            return await self._generate_code(task)
        elif task_type == 'data_analysis':
            return await self._analyze_data(task)
        elif task_type == 'web_search':
            return await self._search_web(task)
        elif task_type == 'file_operations':
            return await self._handle_files(task)
        else:
            return await self._handle_general(task)
    
    async def _process_text(self, task):
        # Text processing implementation
        return {{"success": True, "result": "Text processed"}}
    
    async def _generate_code(self, task):
        # Code generation implementation
        return {{"success": True, "result": "Code generated"}}
    
    async def _analyze_data(self, task):
        # Data analysis implementation
        return {{"success": True, "result": "Data analyzed"}}
    
    async def _search_web(self, task):
        # Web search implementation
        return {{"success": True, "result": "Web search completed"}}
    
    async def _handle_files(self, task):
        # File operations implementation
        return {{"success": True, "result": "File operations completed"}}
    
    async def _handle_general(self, task):
        # General task handling
        return {{"success": True, "result": "General task completed"}}
""",
            config_schema={
                "type": "object",
                "properties": {
                    "max_tasks": {"type": "integer", "default": 5},
                    "timeout": {"type": "integer", "default": 30},
                    "learning_enabled": {"type": "boolean", "default": True}
                }
            }
        )
        
        # Specialist Agent Template
        specialist_template = AgentTemplate(
            name="specialist",
            base_class="BaseAgent",
            capabilities=[AgentCapability.TEXT_PROCESSING],  # Will be customized
            tools=["specialized_tool"],  # Will be customized
            code_template="""
class {agent_name}(BaseAgent):
    def __init__(self, config=None):
        super().__init__(config)
        self.capabilities = {capabilities}
        self.tools = {tools}
        self.specialization = "{specialization}"
    
    async def execute_task(self, task):
        # Specialized implementation
        return await self._specialized_processing(task)
    
    async def _specialized_processing(self, task):
        # Specialized processing logic
        return {{"success": True, "result": "Specialized processing completed"}}
""",
            config_schema={
                "type": "object",
                "properties": {
                    "specialization": {"type": "string", "required": True},
                    "expertise_level": {"type": "integer", "default": 5},
                    "max_tasks": {"type": "integer", "default": 3}
                }
            }
        )
        
        # Monitor Agent Template
        monitor_template = AgentTemplate(
            name="monitor",
            base_class="BaseAgent",
            capabilities=[AgentCapability.SYSTEM_CONTROL, AgentCapability.DATABASE_OPERATIONS],
            tools=["system_monitor", "health_checker", "alert_manager"],
            code_template="""
class {agent_name}(BaseAgent):
    def __init__(self, config=None):
        super().__init__(config)
        self.capabilities = {capabilities}
        self.tools = {tools}
        self.monitoring_interval = config.get('monitoring_interval', 30)
    
    async def execute_task(self, task):
        task_type = task.get('type', 'monitor')
        
        if task_type == 'health_check':
            return await self._check_health(task)
        elif task_type == 'system_metrics':
            return await self._collect_metrics(task)
        elif task_type == 'alert_check':
            return await self._check_alerts(task)
        else:
            return await self._monitor_system(task)
    
    async def _check_health(self, task):
        # Health checking implementation
        return {{"success": True, "result": "Health check completed"}}
    
    async def _collect_metrics(self, task):
        # Metrics collection implementation
        return {{"success": True, "result": "Metrics collected"}}
    
    async def _check_alerts(self, task):
        # Alert checking implementation
        return {{"success": True, "result": "Alerts checked"}}
    
    async def _monitor_system(self, task):
        # General system monitoring
        return {{"success": True, "result": "System monitoring completed"}}
""",
            config_schema={
                "type": "object",
                "properties": {
                    "monitoring_interval": {"type": "integer", "default": 30},
                    "alert_thresholds": {"type": "object"},
                    "metrics_retention": {"type": "integer", "default": 24}
                }
            }
        )
        
        # Learner Agent Template
        learner_template = AgentTemplate(
            name="learner",
            base_class="BaseAgent",
            capabilities=[AgentCapability.TEXT_PROCESSING, AgentCapability.MACHINE_LEARNING],
            tools=["learning_engine", "model_trainer", "data_processor"],
            code_template="""
class {agent_name}(BaseAgent):
    def __init__(self, config=None):
        super().__init__(config)
        self.capabilities = {capabilities}
        self.tools = {tools}
        self.learning_data = []
        self.model = None
    
    async def execute_task(self, task):
        task_type = task.get('type', 'learn')
        
        if task_type == 'train_model':
            return await self._train_model(task)
        elif task_type == 'predict':
            return await self._predict(task)
        elif task_type == 'learn_from_data':
            return await self._learn_from_data(task)
        else:
            return await self._general_learning(task)
    
    async def _train_model(self, task):
        # Model training implementation
        return {{"success": True, "result": "Model trained"}}
    
    async def _predict(self, task):
        # Prediction implementation
        return {{"success": True, "result": "Prediction completed"}}
    
    async def _learn_from_data(self, task):
        # Learning from data implementation
        return {{"success": True, "result": "Learning completed"}}
    
    async def _general_learning(self, task):
        # General learning implementation
        return {{"success": True, "result": "General learning completed"}}
""",
            config_schema={
                "type": "object",
                "properties": {
                    "learning_rate": {"type": "number", "default": 0.01},
                    "model_type": {"type": "string", "default": "neural_network"},
                    "training_data_limit": {"type": "integer", "default": 10000}
                }
            }
        )
        
        self.agent_templates = {
            "generalist": generalist_template,
            "specialist": specialist_template,
            "monitor": monitor_template,
            "learner": learner_template
        }
        
        logger.info(f"Loaded {len(self.agent_templates)} agent templates")
    
    def _register_base_agents(self):
        """Register base agent classes"""
        try:
            from ..agents.base_agent import BaseAgent
            self.agent_registry["BaseAgent"] = BaseAgent
        except ImportError:
            logger.warning("BaseAgent not available, using mock class")
            self.agent_registry["BaseAgent"] = object
    
    async def create_agent(self, spec: AgentSpecification) -> DynamicAgent:
        """Create a new agent based on specification"""
        try:
            logger.info(f"Creating agent: {spec.name} (type: {spec.type.value})")
            
            # Get template based on agent type
            template = self.agent_templates.get(spec.type.value)
            if not template:
                raise AgentError(f"No template found for agent type: {spec.type.value}")
            
            # Generate agent code
            agent_code = self._generate_agent_code(spec, template)
            
            # Create agent class dynamically
            agent_class = self._create_agent_class(spec.name, agent_code)
            
            # Create agent instance
            agent_instance = agent_class(spec.config)
            
            # Create dynamic agent wrapper
            dynamic_agent = DynamicAgent(spec, agent_class, agent_instance)
            
            # Register the agent
            self.created_agents[spec.name] = dynamic_agent
            
            logger.info(f"Successfully created agent: {spec.name}")
            return dynamic_agent
            
        except Exception as e:
            logger.error(f"Failed to create agent {spec.name}: {e}")
            raise AgentError(f"Agent creation failed: {e}")
    
    def _generate_agent_code(self, spec: AgentSpecification, template: AgentTemplate) -> str:
        """Generate agent code from template and specification"""
        # Prepare template variables
        template_vars = {
            "agent_name": spec.name.replace(" ", "_").replace("-", "_").title(),
            "capabilities": [cap.value for cap in spec.capabilities],
            "tools": spec.tools,
            "specialization": spec.config.get("specialization", "general")
        }
        
        # Format the template
        agent_code = template.code_template.format(**template_vars)
        
        return agent_code
    
    def _create_agent_class(self, name: str, code: str) -> Type:
        """Create agent class from generated code"""
        try:
            # Create a new module for the agent
            module_name = f"dynamic_agent_{name.lower()}"
            
            # Compile the code
            compiled_code = compile(code, f"<{module_name}>", "exec")
            
            # Create a new namespace
            namespace = {
                "__name__": module_name,
                "BaseAgent": self.agent_registry.get("BaseAgent", object)
            }
            
            # Execute the code in the namespace
            exec(compiled_code, namespace)
            
            # Get the agent class
            agent_class_name = name.replace(" ", "_").replace("-", "_").title()
            agent_class = namespace.get(agent_class_name)
            
            if not agent_class:
                raise AgentError(f"Agent class {agent_class_name} not found in generated code")
            
            return agent_class
            
        except Exception as e:
            logger.error(f"Failed to create agent class: {e}")
            raise AgentError(f"Agent class creation failed: {e}")
    
    def get_agent(self, name: str) -> Optional[DynamicAgent]:
        """Get created agent by name"""
        return self.created_agents.get(name)
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """List all created agents"""
        return [
            {
                "name": agent.spec.name,
                "type": agent.spec.type.value,
                "capabilities": [cap.value for cap in agent.spec.capabilities],
                "status": agent.status,
                "created_at": agent.created_at.isoformat(),
                "total_tasks": agent.total_tasks,
                "success_rate": agent.success_rate
            }
            for agent in self.created_agents.values()
        ]
    
    def remove_agent(self, name: str) -> bool:
        """Remove an agent"""
        if name in self.created_agents:
            del self.created_agents[name]
            logger.info(f"Removed agent: {name}")
            return True
        return False
    
    def get_agent_by_capability(self, capability: AgentCapability) -> List[DynamicAgent]:
        """Get agents that have a specific capability"""
        return [
            agent for agent in self.created_agents.values()
            if capability in agent.spec.capabilities
        ]
    
    def get_available_capabilities(self) -> List[AgentCapability]:
        """Get all available capabilities from created agents"""
        capabilities = set()
        for agent in self.created_agents.values():
            capabilities.update(agent.spec.capabilities)
        return list(capabilities)
    
    async def execute_task_with_best_agent(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task using the best available agent"""
        required_capabilities = task.get("required_capabilities", [])
        task_type = task.get("type", "general")
        
        # Find suitable agents
        suitable_agents = []
        for agent in self.created_agents.values():
            if agent.status == "idle" and agent.active_tasks < agent.spec.max_concurrent_tasks:
                # Check if agent has required capabilities
                if all(cap in agent.spec.capabilities for cap in required_capabilities):
                    suitable_agents.append(agent)
        
        if not suitable_agents:
            return {
                "success": False,
                "error": "No suitable agent available",
                "required_capabilities": [cap.value for cap in required_capabilities]
            }
        
        # Choose the best agent (highest success rate)
        best_agent = max(suitable_agents, key=lambda a: a.success_rate)
        
        # Execute the task
        result = await best_agent.execute_task(task)
        result["executed_by"] = best_agent.spec.name
        
        return result
    
    def get_agent_statistics(self) -> Dict[str, Any]:
        """Get statistics about created agents"""
        if not self.created_agents:
            return {"total_agents": 0}
        
        total_agents = len(self.created_agents)
        active_agents = len([a for a in self.created_agents.values() if a.status == "busy"])
        idle_agents = len([a for a in self.created_agents.values() if a.status == "idle"])
        
        total_tasks = sum(agent.total_tasks for agent in self.created_agents.values())
        avg_success_rate = sum(agent.success_rate for agent in self.created_agents.values()) / total_agents
        
        capability_counts = {}
        for agent in self.created_agents.values():
            for cap in agent.spec.capabilities:
                capability_counts[cap.value] = capability_counts.get(cap.value, 0) + 1
        
        return {
            "total_agents": total_agents,
            "active_agents": active_agents,
            "idle_agents": idle_agents,
            "total_tasks": total_tasks,
            "average_success_rate": avg_success_rate,
            "capability_distribution": capability_counts,
            "agents": [
                {
                    "name": agent.spec.name,
                    "type": agent.spec.type.value,
                    "status": agent.status,
                    "tasks": agent.total_tasks,
                    "success_rate": agent.success_rate
                }
                for agent in self.created_agents.values()
            ]
        }


# Global agent factory instance
_agent_factory: Optional[AgentFactory] = None


def get_agent_factory() -> AgentFactory:
    """Get global agent factory instance"""
    global _agent_factory
    if _agent_factory is None:
        _agent_factory = AgentFactory()
    return _agent_factory


async def create_agent(spec: AgentSpecification) -> DynamicAgent:
    """Create a new agent using the global factory"""
    factory = get_agent_factory()
    return await factory.create_agent(spec)