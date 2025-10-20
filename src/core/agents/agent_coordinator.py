"""
Atulya Tantra - Agent Coordinator
Version: 2.5.0
Coordinates multiple specialized agents for complex tasks
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import uuid
import asyncio
from collections import defaultdict
from src.core.agents.specialized.base_agent import BaseAgent, AgentTask, AgentResult, AgentStatus
from src.core.agents.specialized.code_agent import CodeAgent
from src.core.agents.specialized.research_agent import ResearchAgent
from src.core.agents.specialized.creative_agent import CreativeAgent
from src.core.agents.specialized.data_agent import DataAgent

logger = logging.getLogger(__name__)


@dataclass
class CoordinationTask:
    """Task that requires multiple agents"""
    task_id: str
    name: str
    description: str
    subtasks: List[Dict[str, Any]]
    dependencies: List[Tuple[str, str]]  # (task_id, depends_on_task_id)
    status: str
    results: Dict[str, Any]
    created_at: datetime
    completed_at: Optional[datetime]


@dataclass
class AgentCollaboration:
    """Collaboration between agents"""
    collaboration_id: str
    agents_involved: List[str]
    task_type: str
    coordination_strategy: str
    results: Dict[str, Any]
    efficiency_score: float
    timestamp: datetime


class AgentCoordinator:
    """Coordinates multiple specialized agents for complex tasks"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.agents = {}  # agent_id -> BaseAgent
        self.coordination_tasks = {}  # task_id -> CoordinationTask
        self.collaboration_history = []  # List of AgentCollaboration
        self.agent_capabilities = {}  # agent_id -> capabilities
        self.task_routing_rules = self._initialize_routing_rules()
        
        # Initialize agents
        self._initialize_agents()
        
        logger.info("AgentCoordinator initialized")
    
    def _initialize_agents(self):
        """Initialize all specialized agents"""
        
        # Create agent instances
        code_agent = CodeAgent(self.config)
        research_agent = ResearchAgent(self.config)
        creative_agent = CreativeAgent(self.config)
        data_agent = DataAgent(self.config)
        
        # Register agents
        self.agents[code_agent.agent_id] = code_agent
        self.agents[research_agent.agent_id] = research_agent
        self.agents[creative_agent.agent_id] = creative_agent
        self.agents[data_agent.agent_id] = data_agent
        
        # Store capabilities
        for agent in self.agents.values():
            self.agent_capabilities[agent.agent_id] = agent.capabilities
        
        logger.info(f"Initialized {len(self.agents)} agents")
    
    async def coordinate_complex_task(
        self,
        task_name: str,
        task_description: str,
        requirements: Dict[str, Any]
    ) -> str:
        """Coordinate a complex task across multiple agents"""
        
        task_id = str(uuid.uuid4())
        
        # Analyze task and create subtasks
        subtasks = await self._analyze_task_requirements(task_description, requirements)
        
        # Create coordination task
        coordination_task = CoordinationTask(
            task_id=task_id,
            name=task_name,
            description=task_description,
            subtasks=subtasks,
            dependencies=[],
            status="pending",
            results={},
            created_at=datetime.now(),
            completed_at=None
        )
        
        self.coordination_tasks[task_id] = coordination_task
        
        # Execute coordination
        await self._execute_coordination(coordination_task)
        
        logger.info(f"Coordinated complex task: {task_name} ({task_id})")
        return task_id
    
    async def get_coordination_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of coordination task"""
        
        if task_id not in self.coordination_tasks:
            return {"error": "Task not found"}
        
        task = self.coordination_tasks[task_id]
        
        return {
            "task_id": task_id,
            "name": task.name,
            "status": task.status,
            "subtasks": len(task.subtasks),
            "completed_subtasks": len(task.results),
            "created_at": task.created_at.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "progress": len(task.results) / len(task.subtasks) * 100 if task.subtasks else 0
        }
    
    async def get_agent_collaboration_history(self, limit: int = 100) -> List[AgentCollaboration]:
        """Get agent collaboration history"""
        
        return self.collaboration_history[-limit:]
    
    async def suggest_agent_combination(self, task_description: str) -> List[List[str]]:
        """Suggest optimal agent combinations for a task"""
        
        # Analyze task requirements
        task_keywords = task_description.lower().split()
        
        # Define agent combinations based on task types
        combinations = []
        
        # Research + Creative (for content creation with research)
        if any(keyword in task_keywords for keyword in ["research", "article", "content", "write"]):
            combinations.append(["research_agent", "creative_agent"])
        
        # Code + Data (for data analysis with code)
        if any(keyword in task_keywords for keyword in ["data", "analysis", "code", "programming"]):
            combinations.append(["data_agent", "code_agent"])
        
        # Research + Data (for data-driven research)
        if any(keyword in task_keywords for keyword in ["research", "data", "analysis", "statistics"]):
            combinations.append(["research_agent", "data_agent"])
        
        # All agents (for complex projects)
        if any(keyword in task_keywords for keyword in ["project", "comprehensive", "complete", "full"]):
            combinations.append(["research_agent", "creative_agent", "code_agent", "data_agent"])
        
        return combinations
    
    async def _analyze_task_requirements(
        self,
        task_description: str,
        requirements: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Analyze task requirements and create subtasks"""
        
        subtasks = []
        task_keywords = task_description.lower()
        
        # Research subtask
        if any(keyword in task_keywords for keyword in ["research", "information", "facts", "analysis"]):
            subtasks.append({
                "subtask_id": str(uuid.uuid4()),
                "agent_id": "research_agent",
                "task_type": "information_gathering",
                "description": f"Research information about: {task_description}",
                "input_data": {"topic": task_description},
                "requirements": {"domain": requirements.get("domain", "general")},
                "priority": 1
            })
        
        # Creative subtask
        if any(keyword in task_keywords for keyword in ["create", "write", "design", "content", "creative"]):
            subtasks.append({
                "subtask_id": str(uuid.uuid4()),
                "agent_id": "creative_agent",
                "task_type": "content_creation",
                "description": f"Create content for: {task_description}",
                "input_data": {"topic": task_description},
                "requirements": {
                    "content_type": requirements.get("content_type", "article"),
                    "style": requirements.get("style", "professional")
                },
                "priority": 2
            })
        
        # Code subtask
        if any(keyword in task_keywords for keyword in ["code", "program", "script", "software", "development"]):
            subtasks.append({
                "subtask_id": str(uuid.uuid4()),
                "agent_id": "code_agent",
                "task_type": "code_generation",
                "description": f"Generate code for: {task_description}",
                "input_data": {"specification": task_description},
                "requirements": {
                    "language": requirements.get("language", "python"),
                    "complexity": requirements.get("complexity", "moderate")
                },
                "priority": 2
            })
        
        # Data subtask
        if any(keyword in task_keywords for keyword in ["data", "analysis", "statistics", "visualization"]):
            subtasks.append({
                "subtask_id": str(uuid.uuid4()),
                "agent_id": "data_agent",
                "task_type": "data_analysis",
                "description": f"Analyze data for: {task_description}",
                "input_data": {"data": requirements.get("data", {})},
                "requirements": {
                    "analysis_type": requirements.get("analysis_type", "descriptive"),
                    "format": requirements.get("format", "json")
                },
                "priority": 2
            })
        
        # If no specific subtasks identified, create a general one
        if not subtasks:
            subtasks.append({
                "subtask_id": str(uuid.uuid4()),
                "agent_id": "research_agent",
                "task_type": "information_gathering",
                "description": f"General task: {task_description}",
                "input_data": {"topic": task_description},
                "requirements": {},
                "priority": 1
            })
        
        return subtasks
    
    async def _execute_coordination(self, coordination_task: CoordinationTask):
        """Execute coordination of subtasks"""
        
        coordination_task.status = "in_progress"
        
        try:
            # Execute subtasks in parallel where possible
            subtask_results = await self._execute_subtasks_parallel(coordination_task)
            
            # Combine results
            combined_results = await self._combine_results(subtask_results, coordination_task)
            
            # Store results
            coordination_task.results = combined_results
            coordination_task.status = "completed"
            coordination_task.completed_at = datetime.now()
            
            # Record collaboration
            await self._record_collaboration(coordination_task, subtask_results)
            
            logger.info(f"Completed coordination task: {coordination_task.name}")
            
        except Exception as e:
            logger.error(f"Coordination task failed: {e}")
            coordination_task.status = "failed"
            coordination_task.results = {"error": str(e)}
    
    async def _execute_subtasks_parallel(self, coordination_task: CoordinationTask) -> Dict[str, AgentResult]:
        """Execute subtasks in parallel where possible"""
        
        subtask_results = {}
        
        # Group subtasks by priority
        priority_groups = defaultdict(list)
        for subtask in coordination_task.subtasks:
            priority_groups[subtask["priority"]].append(subtask)
        
        # Execute subtasks by priority (higher priority first)
        for priority in sorted(priority_groups.keys()):
            subtasks = priority_groups[priority]
            
            # Execute subtasks in parallel within the same priority
            tasks = []
            for subtask in subtasks:
                agent = self.agents.get(subtask["agent_id"])
                if agent:
                    task = asyncio.create_task(self._execute_subtask(agent, subtask))
                    tasks.append((subtask["subtask_id"], task))
            
            # Wait for all tasks in this priority group
            for subtask_id, task in tasks:
                try:
                    result = await task
                    subtask_results[subtask_id] = result
                except Exception as e:
                    logger.error(f"Subtask {subtask_id} failed: {e}")
                    subtask_results[subtask_id] = AgentResult(
                        task_id=subtask_id,
                        agent_id="unknown",
                        success=False,
                        result=None,
                        metadata={"error": str(e)},
                        execution_time=0,
                        confidence=0,
                        timestamp=datetime.now()
                    )
        
        return subtask_results
    
    async def _execute_subtask(self, agent: BaseAgent, subtask: Dict[str, Any]) -> AgentResult:
        """Execute a single subtask"""
        
        # Create agent task
        agent_task = AgentTask(
            task_id=subtask["subtask_id"],
            agent_id=subtask["agent_id"],
            task_type=subtask["task_type"],
            input_data=subtask["input_data"],
            requirements=subtask["requirements"],
            priority=subtask["priority"],
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            status="pending",
            result=None,
            error_message=None
        )
        
        # Execute task
        return await agent.process_task(agent_task)
    
    async def _combine_results(
        self,
        subtask_results: Dict[str, AgentResult],
        coordination_task: CoordinationTask
    ) -> Dict[str, Any]:
        """Combine results from multiple agents"""
        
        combined_results = {
            "coordination_task_id": coordination_task.task_id,
            "subtask_results": {},
            "summary": {},
            "recommendations": [],
            "metadata": {
                "total_subtasks": len(coordination_task.subtasks),
                "successful_subtasks": len([r for r in subtask_results.values() if r.success]),
                "failed_subtasks": len([r for r in subtask_results.values() if not r.success]),
                "combined_at": datetime.now().isoformat()
            }
        }
        
        # Process each subtask result
        for subtask_id, result in subtask_results.items():
            combined_results["subtask_results"][subtask_id] = {
                "agent_id": result.agent_id,
                "success": result.success,
                "result": result.result,
                "execution_time": result.execution_time,
                "confidence": result.confidence,
                "metadata": result.metadata
            }
        
        # Generate summary
        combined_results["summary"] = await self._generate_summary(subtask_results, coordination_task)
        
        # Generate recommendations
        combined_results["recommendations"] = await self._generate_recommendations(subtask_results, coordination_task)
        
        return combined_results
    
    async def _generate_summary(
        self,
        subtask_results: Dict[str, AgentResult],
        coordination_task: CoordinationTask
    ) -> Dict[str, Any]:
        """Generate summary of coordination results"""
        
        successful_results = [r for r in subtask_results.values() if r.success]
        failed_results = [r for r in subtask_results.values() if not r.success]
        
        summary = {
            "task_name": coordination_task.name,
            "task_description": coordination_task.description,
            "total_subtasks": len(coordination_task.subtasks),
            "successful_subtasks": len(successful_results),
            "failed_subtasks": len(failed_results),
            "success_rate": len(successful_results) / len(coordination_task.subtasks) * 100,
            "total_execution_time": sum(r.execution_time for r in subtask_results.values()),
            "average_confidence": sum(r.confidence for r in successful_results) / len(successful_results) if successful_results else 0,
            "agents_used": list(set(r.agent_id for r in subtask_results.values())),
            "key_insights": []
        }
        
        # Extract key insights from successful results
        for result in successful_results:
            if result.result and hasattr(result.result, 'insights'):
                summary["key_insights"].extend(result.result.insights)
            elif isinstance(result.result, dict) and 'insights' in result.result:
                summary["key_insights"].extend(result.result['insights'])
        
        return summary
    
    async def _generate_recommendations(
        self,
        subtask_results: Dict[str, AgentResult],
        coordination_task: CoordinationTask
    ) -> List[str]:
        """Generate recommendations based on coordination results"""
        
        recommendations = []
        
        # Success-based recommendations
        successful_results = [r for r in subtask_results.values() if r.success]
        if len(successful_results) == len(coordination_task.subtasks):
            recommendations.append("All subtasks completed successfully. Consider this approach for similar tasks.")
        
        # Failure-based recommendations
        failed_results = [r for r in subtask_results.values() if not r.success]
        if failed_results:
            recommendations.append(f"{len(failed_results)} subtasks failed. Review and retry failed components.")
        
        # Performance-based recommendations
        total_time = sum(r.execution_time for r in subtask_results.values())
        if total_time > 300:  # 5 minutes
            recommendations.append("Task execution took longer than expected. Consider optimizing agent coordination.")
        
        # Quality-based recommendations
        avg_confidence = sum(r.confidence for r in successful_results) / len(successful_results) if successful_results else 0
        if avg_confidence < 0.7:
            recommendations.append("Overall confidence is low. Consider additional validation or alternative approaches.")
        
        return recommendations
    
    async def _record_collaboration(
        self,
        coordination_task: CoordinationTask,
        subtask_results: Dict[str, AgentResult]
    ):
        """Record agent collaboration"""
        
        agents_involved = list(set(r.agent_id for r in subtask_results.values()))
        
        collaboration = AgentCollaboration(
            collaboration_id=str(uuid.uuid4()),
            agents_involved=agents_involved,
            task_type=coordination_task.name,
            coordination_strategy="parallel_execution",
            results=coordination_task.results,
            efficiency_score=await self._calculate_efficiency_score(subtask_results),
            timestamp=datetime.now()
        )
        
        self.collaboration_history.append(collaboration)
    
    async def _calculate_efficiency_score(self, subtask_results: Dict[str, AgentResult]) -> float:
        """Calculate efficiency score for collaboration"""
        
        if not subtask_results:
            return 0.0
        
        # Base score from success rate
        success_rate = len([r for r in subtask_results.values() if r.success]) / len(subtask_results)
        
        # Adjust for execution time (lower is better)
        total_time = sum(r.execution_time for r in subtask_results.values())
        time_score = max(0, 1 - (total_time / 600))  # Penalty for time over 10 minutes
        
        # Adjust for confidence
        successful_results = [r for r in subtask_results.values() if r.success]
        avg_confidence = sum(r.confidence for r in successful_results) / len(successful_results) if successful_results else 0
        
        # Combine scores
        efficiency_score = (success_rate * 0.4) + (time_score * 0.3) + (avg_confidence * 0.3)
        
        return min(1.0, efficiency_score)
    
    def _initialize_routing_rules(self) -> Dict[str, Any]:
        """Initialize task routing rules"""
        
        return {
            "research_tasks": ["research_agent"],
            "creative_tasks": ["creative_agent"],
            "code_tasks": ["code_agent"],
            "data_tasks": ["data_agent"],
            "complex_tasks": ["research_agent", "creative_agent", "code_agent", "data_agent"]
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of agent coordinator"""
        
        agent_health = {}
        for agent_id, agent in self.agents.items():
            try:
                agent_health[agent_id] = await agent.health_check()
            except Exception as e:
                agent_health[agent_id] = {"error": str(e)}
        
        return {
            "agent_coordinator": True,
            "total_agents": len(self.agents),
            "coordination_tasks": len(self.coordination_tasks),
            "collaboration_history": len(self.collaboration_history),
            "agent_health": agent_health
        }
