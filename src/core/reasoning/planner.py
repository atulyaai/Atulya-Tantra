"""
Atulya Tantra - Planning Engine
Version: 2.5.0
Multi-step planning with dependency tracking and resource planning
"""

import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import uuid
import json
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class PlanStatus(Enum):
    """Plan status"""
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(Enum):
    """Task status"""
    PENDING = "pending"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class Priority(Enum):
    """Task priority"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Resource:
    """Resource definition"""
    resource_id: str
    name: str
    type: str
    capacity: int
    available: int
    cost_per_unit: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """Task definition"""
    task_id: str
    name: str
    description: str
    estimated_duration: int  # minutes
    required_resources: List[str]  # resource_ids
    dependencies: List[str]  # task_ids
    priority: Priority
    status: TaskStatus
    assigned_agent: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    actual_duration: Optional[int]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    """Plan definition"""
    plan_id: str
    name: str
    description: str
    goal: str
    tasks: List[Task]
    resources: List[Resource]
    status: PlanStatus
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    estimated_duration: int
    actual_duration: Optional[int]
    metadata: Dict[str, Any] = field(default_factory=dict)


class PlanningEngine:
    """Multi-step planning engine with dependency tracking"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.plans = {}  # plan_id -> Plan
        self.planning_strategies = self._initialize_planning_strategies()
        self.resource_pool = self._initialize_resource_pool()
        
        logger.info("PlanningEngine initialized")
    
    async def create_plan(
        self,
        name: str,
        description: str,
        goal: str,
        requirements: Dict[str, Any],
        strategy: Optional[str] = None
    ) -> str:
        """Create a new plan"""
        
        plan_id = str(uuid.uuid4())
        
        # Select planning strategy
        if not strategy:
            strategy = await self._select_planning_strategy(goal, requirements)
        
        # Generate tasks
        tasks = await self._generate_tasks(goal, requirements, strategy)
        
        # Estimate duration
        estimated_duration = sum(task.estimated_duration for task in tasks)
        
        # Create plan
        plan = Plan(
            plan_id=plan_id,
            name=name,
            description=description,
            goal=goal,
            tasks=tasks,
            resources=self.resource_pool,
            status=PlanStatus.DRAFT,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            estimated_duration=estimated_duration,
            actual_duration=None,
            metadata={
                "strategy": strategy,
                "requirements": requirements
            }
        )
        
        self.plans[plan_id] = plan
        
        logger.info(f"Created plan: {name} ({plan_id})")
        return plan_id
    
    async def optimize_plan(self, plan_id: str) -> Dict[str, Any]:
        """Optimize a plan for efficiency"""
        
        plan = self.plans.get(plan_id)
        if not plan:
            return {"error": "Plan not found"}
        
        # Perform optimization
        optimization_results = {
            "plan_id": plan_id,
            "optimizations_applied": [],
            "improvements": {},
            "recommendations": []
        }
        
        # Optimize task order
        task_order_optimization = await self._optimize_task_order(plan)
        if task_order_optimization["improved"]:
            optimization_results["optimizations_applied"].append("task_order")
            optimization_results["improvements"]["duration_reduction"] = task_order_optimization["duration_reduction"]
        
        # Optimize resource allocation
        resource_optimization = await self._optimize_resource_allocation(plan)
        if resource_optimization["improved"]:
            optimization_results["optimizations_applied"].append("resource_allocation")
            optimization_results["improvements"]["cost_reduction"] = resource_optimization["cost_reduction"]
        
        # Generate recommendations
        optimization_results["recommendations"] = await self._generate_optimization_recommendations(plan)
        
        return optimization_results
    
    async def execute_plan(self, plan_id: str) -> Dict[str, Any]:
        """Execute a plan"""
        
        plan = self.plans.get(plan_id)
        if not plan:
            return {"error": "Plan not found"}
        
        if plan.status != PlanStatus.DRAFT:
            return {"error": "Plan is not in draft status"}
        
        # Start plan execution
        plan.status = PlanStatus.ACTIVE
        plan.started_at = datetime.now()
        
        # Execute tasks in dependency order
        execution_results = await self._execute_tasks(plan)
        
        # Update plan status
        if execution_results["success"]:
            plan.status = PlanStatus.COMPLETED
            plan.completed_at = datetime.now()
            plan.actual_duration = (plan.completed_at - plan.started_at).total_seconds() / 60
        else:
            plan.status = PlanStatus.FAILED
        
        return {
            "plan_id": plan_id,
            "status": plan.status.value,
            "execution_results": execution_results,
            "completed_at": plan.completed_at.isoformat() if plan.completed_at else None,
            "actual_duration": plan.actual_duration
        }
    
    async def get_plan_status(self, plan_id: str) -> Dict[str, Any]:
        """Get plan status and progress"""
        
        plan = self.plans.get(plan_id)
        if not plan:
            return {"error": "Plan not found"}
        
        # Calculate progress
        total_tasks = len(plan.tasks)
        completed_tasks = len([t for t in plan.tasks if t.status == TaskStatus.COMPLETED])
        in_progress_tasks = len([t for t in plan.tasks if t.status == TaskStatus.IN_PROGRESS])
        failed_tasks = len([t for t in plan.tasks if t.status == TaskStatus.FAILED])
        
        progress_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Calculate critical path
        critical_path = await self._calculate_critical_path(plan)
        
        return {
            "plan_id": plan_id,
            "name": plan.name,
            "status": plan.status.value,
            "progress_percentage": progress_percentage,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "in_progress_tasks": in_progress_tasks,
            "failed_tasks": failed_tasks,
            "estimated_duration": plan.estimated_duration,
            "actual_duration": plan.actual_duration,
            "critical_path": critical_path,
            "created_at": plan.created_at.isoformat(),
            "started_at": plan.started_at.isoformat() if plan.started_at else None,
            "completed_at": plan.completed_at.isoformat() if plan.completed_at else None
        }
    
    async def get_plan_tasks(self, plan_id: str) -> List[Dict[str, Any]]:
        """Get all tasks in a plan"""
        
        plan = self.plans.get(plan_id)
        if not plan:
            return []
        
        return [
            {
                "task_id": task.task_id,
                "name": task.name,
                "description": task.description,
                "status": task.status.value,
                "priority": task.priority.value,
                "estimated_duration": task.estimated_duration,
                "actual_duration": task.actual_duration,
                "dependencies": task.dependencies,
                "required_resources": task.required_resources,
                "assigned_agent": task.assigned_agent,
                "created_at": task.created_at.isoformat(),
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None
            }
            for task in plan.tasks
        ]
    
    async def _generate_tasks(
        self,
        goal: str,
        requirements: Dict[str, Any],
        strategy: str
    ) -> List[Task]:
        """Generate tasks for a plan"""
        
        tasks = []
        
        if strategy == "systematic_breakdown":
            tasks = await self._systematic_breakdown_strategy(goal, requirements)
        elif strategy == "milestone_based":
            tasks = await self._milestone_based_strategy(goal, requirements)
        elif strategy == "agile_sprint":
            tasks = await self._agile_sprint_strategy(goal, requirements)
        else:
            tasks = await self._general_strategy(goal, requirements)
        
        return tasks
    
    async def _systematic_breakdown_strategy(
        self,
        goal: str,
        requirements: Dict[str, Any]
    ) -> List[Task]:
        """Systematic breakdown planning strategy"""
        
        tasks = []
        
        # Phase 1: Planning and preparation
        planning_task = Task(
            task_id=str(uuid.uuid4()),
            name="Planning and Preparation",
            description="Plan the approach and gather necessary resources",
            estimated_duration=60,
            required_resources=["planning_agent"],
            dependencies=[],
            priority=Priority.HIGH,
            status=TaskStatus.PENDING,
            assigned_agent=None,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            actual_duration=None
        )
        tasks.append(planning_task)
        
        # Phase 2: Execution
        execution_task = Task(
            task_id=str(uuid.uuid4()),
            name="Main Execution",
            description="Execute the main work",
            estimated_duration=120,
            required_resources=["execution_agent"],
            dependencies=[planning_task.task_id],
            priority=Priority.HIGH,
            status=TaskStatus.PENDING,
            assigned_agent=None,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            actual_duration=None
        )
        tasks.append(execution_task)
        
        # Phase 3: Review and refinement
        review_task = Task(
            task_id=str(uuid.uuid4()),
            name="Review and Refinement",
            description="Review results and make improvements",
            estimated_duration=30,
            required_resources=["review_agent"],
            dependencies=[execution_task.task_id],
            priority=Priority.MEDIUM,
            status=TaskStatus.PENDING,
            assigned_agent=None,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            actual_duration=None
        )
        tasks.append(review_task)
        
        return tasks
    
    async def _milestone_based_strategy(
        self,
        goal: str,
        requirements: Dict[str, Any]
    ) -> List[Task]:
        """Milestone-based planning strategy"""
        
        tasks = []
        
        # Milestone 1: Foundation
        foundation_task = Task(
            task_id=str(uuid.uuid4()),
            name="Foundation Setup",
            description="Establish foundation for the project",
            estimated_duration=90,
            required_resources=["foundation_agent"],
            dependencies=[],
            priority=Priority.HIGH,
            status=TaskStatus.PENDING,
            assigned_agent=None,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            actual_duration=None
        )
        tasks.append(foundation_task)
        
        # Milestone 2: Development
        development_task = Task(
            task_id=str(uuid.uuid4()),
            name="Development Phase",
            description="Develop the main components",
            estimated_duration=180,
            required_resources=["development_agent"],
            dependencies=[foundation_task.task_id],
            priority=Priority.HIGH,
            status=TaskStatus.PENDING,
            assigned_agent=None,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            actual_duration=None
        )
        tasks.append(development_task)
        
        # Milestone 3: Testing
        testing_task = Task(
            task_id=str(uuid.uuid4()),
            name="Testing Phase",
            description="Test and validate the solution",
            estimated_duration=60,
            required_resources=["testing_agent"],
            dependencies=[development_task.task_id],
            priority=Priority.HIGH,
            status=TaskStatus.PENDING,
            assigned_agent=None,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            actual_duration=None
        )
        tasks.append(testing_task)
        
        # Milestone 4: Deployment
        deployment_task = Task(
            task_id=str(uuid.uuid4()),
            name="Deployment Phase",
            description="Deploy the solution",
            estimated_duration=45,
            required_resources=["deployment_agent"],
            dependencies=[testing_task.task_id],
            priority=Priority.MEDIUM,
            status=TaskStatus.PENDING,
            assigned_agent=None,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            actual_duration=None
        )
        tasks.append(deployment_task)
        
        return tasks
    
    async def _agile_sprint_strategy(
        self,
        goal: str,
        requirements: Dict[str, Any]
    ) -> List[Task]:
        """Agile sprint planning strategy"""
        
        tasks = []
        
        # Sprint 1: Backlog refinement
        backlog_task = Task(
            task_id=str(uuid.uuid4()),
            name="Backlog Refinement",
            description="Refine and prioritize backlog items",
            estimated_duration=30,
            required_resources=["product_owner"],
            dependencies=[],
            priority=Priority.HIGH,
            status=TaskStatus.PENDING,
            assigned_agent=None,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            actual_duration=None
        )
        tasks.append(backlog_task)
        
        # Sprint 2: Development sprint
        sprint_task = Task(
            task_id=str(uuid.uuid4()),
            name="Development Sprint",
            description="Complete development work in sprint",
            estimated_duration=120,
            required_resources=["development_team"],
            dependencies=[backlog_task.task_id],
            priority=Priority.HIGH,
            status=TaskStatus.PENDING,
            assigned_agent=None,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            actual_duration=None
        )
        tasks.append(sprint_task)
        
        # Sprint 3: Review and retrospective
        review_task = Task(
            task_id=str(uuid.uuid4()),
            name="Sprint Review",
            description="Review sprint results and plan next sprint",
            estimated_duration=45,
            required_resources=["scrum_team"],
            dependencies=[sprint_task.task_id],
            priority=Priority.MEDIUM,
            status=TaskStatus.PENDING,
            assigned_agent=None,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            actual_duration=None
        )
        tasks.append(review_task)
        
        return tasks
    
    async def _general_strategy(
        self,
        goal: str,
        requirements: Dict[str, Any]
    ) -> List[Task]:
        """General planning strategy"""
        
        tasks = []
        
        # Task 1: Analysis
        analysis_task = Task(
            task_id=str(uuid.uuid4()),
            name="Analysis",
            description="Analyze requirements and constraints",
            estimated_duration=45,
            required_resources=["analysis_agent"],
            dependencies=[],
            priority=Priority.HIGH,
            status=TaskStatus.PENDING,
            assigned_agent=None,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            actual_duration=None
        )
        tasks.append(analysis_task)
        
        # Task 2: Implementation
        implementation_task = Task(
            task_id=str(uuid.uuid4()),
            name="Implementation",
            description="Implement the solution",
            estimated_duration=90,
            required_resources=["implementation_agent"],
            dependencies=[analysis_task.task_id],
            priority=Priority.HIGH,
            status=TaskStatus.PENDING,
            assigned_agent=None,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            actual_duration=None
        )
        tasks.append(implementation_task)
        
        # Task 3: Validation
        validation_task = Task(
            task_id=str(uuid.uuid4()),
            name="Validation",
            description="Validate the solution",
            estimated_duration=30,
            required_resources=["validation_agent"],
            dependencies=[implementation_task.task_id],
            priority=Priority.MEDIUM,
            status=TaskStatus.PENDING,
            assigned_agent=None,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            actual_duration=None
        )
        tasks.append(validation_task)
        
        return tasks
    
    async def _select_planning_strategy(self, goal: str, requirements: Dict[str, Any]) -> str:
        """Select appropriate planning strategy"""
        
        goal_lower = goal.lower()
        
        # Strategy selection based on goal type
        if any(keyword in goal_lower for keyword in ["systematic", "structured", "methodical"]):
            return "systematic_breakdown"
        elif any(keyword in goal_lower for keyword in ["milestone", "phase", "stage"]):
            return "milestone_based"
        elif any(keyword in goal_lower for keyword in ["sprint", "agile", "iterative"]):
            return "agile_sprint"
        else:
            return "general"
    
    async def _optimize_task_order(self, plan: Plan) -> Dict[str, Any]:
        """Optimize task execution order"""
        
        optimization = {
            "improved": False,
            "duration_reduction": 0,
            "changes": []
        }
        
        # Simple optimization: prioritize high-priority tasks
        high_priority_tasks = [t for t in plan.tasks if t.priority == Priority.HIGH]
        if len(high_priority_tasks) > 1:
            optimization["improved"] = True
            optimization["duration_reduction"] = 15  # Simulated 15-minute reduction
            optimization["changes"].append("Reordered high-priority tasks")
        
        return optimization
    
    async def _optimize_resource_allocation(self, plan: Plan) -> Dict[str, Any]:
        """Optimize resource allocation"""
        
        optimization = {
            "improved": False,
            "cost_reduction": 0,
            "changes": []
        }
        
        # Simple optimization: use cheaper resources where possible
        total_cost = sum(
            sum(self.resource_pool[rid].cost_per_unit for rid in task.required_resources)
            for task in plan.tasks
        )
        
        if total_cost > 100:  # Arbitrary threshold
            optimization["improved"] = True
            optimization["cost_reduction"] = total_cost * 0.1  # 10% reduction
            optimization["changes"].append("Optimized resource allocation")
        
        return optimization
    
    async def _generate_optimization_recommendations(self, plan: Plan) -> List[str]:
        """Generate optimization recommendations"""
        
        recommendations = []
        
        # Check for long-running tasks
        long_tasks = [t for t in plan.tasks if t.estimated_duration > 120]
        if long_tasks:
            recommendations.append("Consider breaking down long-running tasks")
        
        # Check for resource bottlenecks
        resource_usage = defaultdict(int)
        for task in plan.tasks:
            for resource_id in task.required_resources:
                resource_usage[resource_id] += 1
        
        bottlenecks = [rid for rid, count in resource_usage.items() if count > 3]
        if bottlenecks:
            recommendations.append("Consider addressing resource bottlenecks")
        
        # Check for critical path
        if len(plan.tasks) > 5:
            recommendations.append("Consider parallel execution for independent tasks")
        
        return recommendations
    
    async def _execute_tasks(self, plan: Plan) -> Dict[str, Any]:
        """Execute tasks in dependency order"""
        
        execution_results = {
            "success": True,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "execution_time": 0,
            "errors": []
        }
        
        start_time = datetime.now()
        
        # Execute tasks in dependency order
        completed_tasks = set()
        ready_tasks = [t for t in plan.tasks if not t.dependencies]
        
        while ready_tasks:
            task = ready_tasks.pop(0)
            
            # Execute task
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.now()
            
            # Simulate task execution
            await asyncio.sleep(0.1)  # Simulate work
            
            # Mark task as completed
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.actual_duration = (task.completed_at - task.started_at).total_seconds() / 60
            
            completed_tasks.add(task.task_id)
            execution_results["completed_tasks"] += 1
            
            # Add newly ready tasks
            for other_task in plan.tasks:
                if (other_task.status == TaskStatus.PENDING and
                    all(dep in completed_tasks for dep in other_task.dependencies)):
                    ready_tasks.append(other_task)
        
        execution_results["execution_time"] = (datetime.now() - start_time).total_seconds() / 60
        
        return execution_results
    
    async def _calculate_critical_path(self, plan: Plan) -> List[str]:
        """Calculate critical path for the plan"""
        
        # Simple critical path calculation
        # In production, this would use proper critical path method
        
        critical_path = []
        
        # Find longest path through dependencies
        task_durations = {task.task_id: task.estimated_duration for task in plan.tasks}
        task_dependencies = {task.task_id: task.dependencies for task in plan.tasks}
        
        # Calculate longest path for each task
        longest_paths = {}
        for task in plan.tasks:
            path_length = await self._calculate_path_length(task.task_id, task_durations, task_dependencies)
            longest_paths[task.task_id] = path_length
        
        # Find tasks on critical path
        max_length = max(longest_paths.values()) if longest_paths else 0
        for task_id, length in longest_paths.items():
            if length == max_length:
                critical_path.append(task_id)
        
        return critical_path
    
    async def _calculate_path_length(
        self,
        task_id: str,
        durations: Dict[str, int],
        dependencies: Dict[str, List[str]]
    ) -> int:
        """Calculate path length for a task"""
        
        if task_id not in durations:
            return 0
        
        duration = durations[task_id]
        if task_id not in dependencies or not dependencies[task_id]:
            return duration
        
        max_dependency_length = 0
        for dep_id in dependencies[task_id]:
            dep_length = await self._calculate_path_length(dep_id, durations, dependencies)
            max_dependency_length = max(max_dependency_length, dep_length)
        
        return duration + max_dependency_length
    
    def _initialize_planning_strategies(self) -> Dict[str, Any]:
        """Initialize planning strategies"""
        
        return {
            "systematic_breakdown": {
                "description": "Systematic breakdown of complex problems",
                "use_cases": ["complex projects", "structured analysis"],
                "characteristics": ["methodical", "comprehensive", "sequential"]
            },
            "milestone_based": {
                "description": "Plan based on major milestones",
                "use_cases": ["project management", "long-term planning"],
                "characteristics": ["goal-oriented", "milestone-driven", "phased"]
            },
            "agile_sprint": {
                "description": "Agile sprint-based planning",
                "use_cases": ["software development", "iterative projects"],
                "characteristics": ["iterative", "flexible", "time-boxed"]
            }
        }
    
    def _initialize_resource_pool(self) -> List[Resource]:
        """Initialize resource pool"""
        
        resources = [
            Resource(
                resource_id="planning_agent",
                name="Planning Agent",
                type="agent",
                capacity=1,
                available=1,
                cost_per_unit=10.0
            ),
            Resource(
                resource_id="execution_agent",
                name="Execution Agent",
                type="agent",
                capacity=2,
                available=2,
                cost_per_unit=15.0
            ),
            Resource(
                resource_id="review_agent",
                name="Review Agent",
                type="agent",
                capacity=1,
                available=1,
                cost_per_unit=12.0
            ),
            Resource(
                resource_id="development_agent",
                name="Development Agent",
                type="agent",
                capacity=3,
                available=3,
                cost_per_unit=20.0
            ),
            Resource(
                resource_id="testing_agent",
                name="Testing Agent",
                type="agent",
                capacity=2,
                available=2,
                cost_per_unit=18.0
            )
        ]
        
        return resources
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of planning engine"""
        return {
            "planning_engine": True,
            "total_plans": len(self.plans),
            "active_plans": len([p for p in self.plans.values() if p.status == PlanStatus.ACTIVE]),
            "completed_plans": len([p for p in self.plans.values() if p.status == PlanStatus.COMPLETED]),
            "strategies_available": len(self.planning_strategies),
            "resources_available": len(self.resource_pool)
        }
