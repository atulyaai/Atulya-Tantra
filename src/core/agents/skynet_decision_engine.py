"""
Atulya Tantra - Skynet Decision Engine
Version: 2.5.0
Goal-oriented planning and autonomous decision making
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import json
import uuid
import asyncio
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class DecisionType(Enum):
    """Types of decisions"""
    TACTICAL = "tactical"  # Short-term, immediate actions
    STRATEGIC = "strategic"  # Long-term planning
    OPERATIONAL = "operational"  # Day-to-day operations
    EMERGENCY = "emergency"  # Crisis response


class GoalStatus(Enum):
    """Goal status"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ActionStatus(Enum):
    """Action status"""
    PENDING = "pending"
    READY = "ready"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Goal:
    """Goal definition"""
    goal_id: str
    name: str
    description: str
    priority: int  # 1-10
    deadline: Optional[datetime]
    status: GoalStatus
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    success_criteria: List[str]
    constraints: Dict[str, Any]
    dependencies: List[str]  # goal_ids
    metadata: Dict[str, Any]


@dataclass
class Action:
    """Action definition"""
    action_id: str
    goal_id: str
    name: str
    description: str
    action_type: str
    parameters: Dict[str, Any]
    estimated_duration: int  # minutes
    required_resources: List[str]
    dependencies: List[str]  # action_ids
    status: ActionStatus
    priority: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    result: Any
    error_message: Optional[str]


@dataclass
class Decision:
    """Decision record"""
    decision_id: str
    decision_type: DecisionType
    goal_id: str
    context: Dict[str, Any]
    options: List[Dict[str, Any]]
    selected_option: Dict[str, Any]
    reasoning: str
    confidence: float
    timestamp: datetime
    consequences: List[str]
    metadata: Dict[str, Any]


class DecisionEngine:
    """Goal-oriented planning and autonomous decision making"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.autonomy_enabled = config.get("autonomy_enabled", False)
        self.safety_mode = config.get("safety_mode", True)
        self.goals = {}  # goal_id -> Goal
        self.actions = {}  # action_id -> Action
        self.decisions = deque(maxlen=1000)  # Keep last 1000 decisions
        self.decision_history = defaultdict(list)  # goal_id -> List[Decision]
        self.resource_pool = {}  # resource -> availability
        self.constraints = config.get("constraints", {})
        
        logger.info("DecisionEngine initialized")
    
    async def create_goal(
        self,
        name: str,
        description: str,
        priority: int = 5,
        deadline: Optional[datetime] = None,
        success_criteria: List[str] = None,
        constraints: Dict[str, Any] = None,
        dependencies: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Create a new goal"""
        
        goal_id = str(uuid.uuid4())
        now = datetime.now()
        
        goal = Goal(
            goal_id=goal_id,
            name=name,
            description=description,
            priority=priority,
            deadline=deadline,
            status=GoalStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            completed_at=None,
            success_criteria=success_criteria or [],
            constraints=constraints or {},
            dependencies=dependencies or [],
            metadata=metadata or {}
        )
        
        self.goals[goal_id] = goal
        
        # Generate action plan
        await self._generate_action_plan(goal)
        
        logger.info(f"Created goal: {name} ({goal_id})")
        return goal_id
    
    async def update_goal_status(self, goal_id: str, status: GoalStatus) -> Dict[str, Any]:
        """Update goal status"""
        
        if goal_id not in self.goals:
            return {"error": "Goal not found"}
        
        goal = self.goals[goal_id]
        goal.status = status
        goal.updated_at = datetime.now()
        
        if status == GoalStatus.COMPLETED:
            goal.completed_at = datetime.now()
        
        logger.info(f"Updated goal status: {goal_id} -> {status.value}")
        return {"success": True, "goal_id": goal_id, "status": status.value}
    
    async def make_decision(
        self,
        goal_id: str,
        context: Dict[str, Any],
        decision_type: DecisionType = DecisionType.OPERATIONAL
    ) -> Decision:
        """Make a decision for a goal"""
        
        if goal_id not in self.goals:
            raise ValueError(f"Goal not found: {goal_id}")
        
        goal = self.goals[goal_id]
        
        # Generate decision options
        options = await self._generate_options(goal, context)
        
        # Evaluate options
        selected_option = await self._evaluate_options(options, context)
        
        # Create decision record
        decision_id = str(uuid.uuid4())
        decision = Decision(
            decision_id=decision_id,
            decision_type=decision_type,
            goal_id=goal_id,
            context=context,
            options=options,
            selected_option=selected_option,
            reasoning=await self._generate_reasoning(goal, selected_option, context),
            confidence=await self._calculate_confidence(selected_option, context),
            timestamp=datetime.now(),
            consequences=await self._predict_consequences(selected_option, context),
            metadata={}
        )
        
        # Store decision
        self.decisions.append(decision)
        self.decision_history[goal_id].append(decision)
        
        # Execute decision if autonomy is enabled
        if self.autonomy_enabled and decision_type != DecisionType.EMERGENCY:
            await self._execute_decision(decision)
        
        logger.info(f"Made decision: {decision_id} for goal {goal_id}")
        return decision
    
    async def get_goal_progress(self, goal_id: str) -> Dict[str, Any]:
        """Get progress information for a goal"""
        
        if goal_id not in self.goals:
            return {"error": "Goal not found"}
        
        goal = self.goals[goal_id]
        
        # Get actions for this goal
        goal_actions = [action for action in self.actions.values() if action.goal_id == goal_id]
        
        # Calculate progress
        total_actions = len(goal_actions)
        completed_actions = len([a for a in goal_actions if a.status == ActionStatus.COMPLETED])
        progress_percentage = (completed_actions / total_actions * 100) if total_actions > 0 else 0
        
        # Check success criteria
        criteria_met = await self._check_success_criteria(goal)
        
        return {
            "goal_id": goal_id,
            "name": goal.name,
            "status": goal.status.value,
            "progress_percentage": progress_percentage,
            "completed_actions": completed_actions,
            "total_actions": total_actions,
            "success_criteria_met": criteria_met,
            "created_at": goal.created_at.isoformat(),
            "deadline": goal.deadline.isoformat() if goal.deadline else None,
            "priority": goal.priority
        }
    
    async def get_active_goals(self) -> List[Goal]:
        """Get all active goals"""
        
        return [
            goal for goal in self.goals.values()
            if goal.status == GoalStatus.ACTIVE
        ]
    
    async def get_decision_history(
        self,
        goal_id: Optional[str] = None,
        decision_type: Optional[DecisionType] = None,
        limit: int = 100
    ) -> List[Decision]:
        """Get decision history with filters"""
        
        if goal_id:
            decisions = self.decision_history.get(goal_id, [])
        else:
            decisions = list(self.decisions)
        
        # Apply filters
        if decision_type:
            decisions = [d for d in decisions if d.decision_type == decision_type]
        
        # Sort by timestamp (newest first)
        decisions.sort(key=lambda x: x.timestamp, reverse=True)
        
        return decisions[:limit]
    
    async def autonomous_planning(self) -> List[str]:
        """Perform autonomous planning for all active goals"""
        
        if not self.autonomy_enabled:
            return []
        
        planned_actions = []
        active_goals = await self.get_active_goals()
        
        for goal in active_goals:
            # Check if goal needs planning
            if await self._needs_planning(goal):
                # Generate new actions
                new_actions = await self._plan_for_goal(goal)
                planned_actions.extend(new_actions)
        
        return planned_actions
    
    async def _generate_action_plan(self, goal: Goal):
        """Generate initial action plan for a goal"""
        
        # Simple action plan generation based on goal type
        actions = []
        
        if "optimize" in goal.name.lower():
            actions = [
                ("analyze_current_state", "Analyze current system state", 30),
                ("identify_bottlenecks", "Identify performance bottlenecks", 20),
                ("implement_optimizations", "Implement optimizations", 60),
                ("test_improvements", "Test performance improvements", 30),
                ("monitor_results", "Monitor optimization results", 15)
            ]
        elif "monitor" in goal.name.lower():
            actions = [
                ("setup_monitoring", "Set up monitoring systems", 45),
                ("configure_alerts", "Configure alert thresholds", 30),
                ("test_monitoring", "Test monitoring functionality", 20),
                ("start_monitoring", "Start continuous monitoring", 10)
            ]
        elif "maintain" in goal.name.lower():
            actions = [
                ("assess_system", "Assess system health", 25),
                ("schedule_maintenance", "Schedule maintenance tasks", 15),
                ("perform_maintenance", "Perform maintenance actions", 45),
                ("verify_health", "Verify system health after maintenance", 20)
            ]
        else:
            # Generic action plan
            actions = [
                ("plan_approach", "Plan approach to goal", 20),
                ("execute_plan", "Execute planned actions", 60),
                ("monitor_progress", "Monitor progress", 15),
                ("complete_goal", "Complete goal", 10)
            ]
        
        # Create action objects
        for i, (action_type, description, duration) in enumerate(actions):
            action_id = str(uuid.uuid4())
            
            action = Action(
                action_id=action_id,
                goal_id=goal.goal_id,
                name=f"{goal.name} - Step {i+1}",
                description=description,
                action_type=action_type,
                parameters={},
                estimated_duration=duration,
                required_resources=[],
                dependencies=[],
                status=ActionStatus.PENDING,
                priority=goal.priority,
                created_at=datetime.now(),
                started_at=None,
                completed_at=None,
                result=None,
                error_message=None
            )
            
            self.actions[action_id] = action
    
    async def _generate_options(self, goal: Goal, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate decision options for a goal"""
        
        options = []
        
        # Option 1: Continue current approach
        options.append({
            "id": "continue",
            "name": "Continue Current Approach",
            "description": "Continue with the current action plan",
            "estimated_success": 0.7,
            "resource_cost": "low",
            "time_required": "medium",
            "risk_level": "low"
        })
        
        # Option 2: Accelerate approach
        options.append({
            "id": "accelerate",
            "name": "Accelerate Approach",
            "description": "Increase resources to complete goal faster",
            "estimated_success": 0.8,
            "resource_cost": "high",
            "time_required": "low",
            "risk_level": "medium"
        })
        
        # Option 3: Conservative approach
        options.append({
            "id": "conservative",
            "name": "Conservative Approach",
            "description": "Take a more careful, step-by-step approach",
            "estimated_success": 0.9,
            "resource_cost": "low",
            "time_required": "high",
            "risk_level": "low"
        })
        
        # Option 4: Alternative approach
        options.append({
            "id": "alternative",
            "name": "Alternative Approach",
            "description": "Try a different strategy to achieve the goal",
            "estimated_success": 0.6,
            "resource_cost": "medium",
            "time_required": "medium",
            "risk_level": "high"
        })
        
        return options
    
    async def _evaluate_options(
        self,
        options: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate and select the best option"""
        
        # Simple scoring system
        best_option = None
        best_score = -1
        
        for option in options:
            score = 0
            
            # Success probability (40% weight)
            score += option["estimated_success"] * 40
            
            # Resource efficiency (30% weight)
            resource_scores = {"low": 30, "medium": 20, "high": 10}
            score += resource_scores.get(option["resource_cost"], 15)
            
            # Time efficiency (20% weight)
            time_scores = {"low": 20, "medium": 15, "high": 10}
            score += time_scores.get(option["time_required"], 15)
            
            # Risk assessment (10% weight)
            risk_scores = {"low": 10, "medium": 5, "high": 0}
            score += risk_scores.get(option["risk_level"], 5)
            
            if score > best_score:
                best_score = score
                best_option = option
        
        return best_option or options[0]
    
    async def _generate_reasoning(
        self,
        goal: Goal,
        selected_option: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """Generate reasoning for the selected option"""
        
        reasoning_parts = [
            f"Selected '{selected_option['name']}' for goal '{goal.name}'",
            f"Estimated success probability: {selected_option['estimated_success']:.1%}",
            f"Resource cost: {selected_option['resource_cost']}",
            f"Time required: {selected_option['time_required']}",
            f"Risk level: {selected_option['risk_level']}"
        ]
        
        # Add context-specific reasoning
        if context.get("urgency", "normal") == "high":
            reasoning_parts.append("High urgency situation - prioritizing speed")
        
        if context.get("resources", "normal") == "limited":
            reasoning_parts.append("Limited resources - prioritizing efficiency")
        
        return ". ".join(reasoning_parts)
    
    async def _calculate_confidence(
        self,
        selected_option: Dict[str, Any],
        context: Dict[str, Any]
    ) -> float:
        """Calculate confidence in the selected option"""
        
        base_confidence = selected_option["estimated_success"]
        
        # Adjust based on context
        if context.get("urgency", "normal") == "high":
            base_confidence *= 0.9  # Slightly lower confidence under pressure
        
        if context.get("resources", "normal") == "abundant":
            base_confidence *= 1.1  # Higher confidence with more resources
        
        return min(1.0, base_confidence)
    
    async def _predict_consequences(
        self,
        selected_option: Dict[str, Any],
        context: Dict[str, Any]
    ) -> List[str]:
        """Predict consequences of the selected option"""
        
        consequences = []
        
        if selected_option["resource_cost"] == "high":
            consequences.append("Will consume significant system resources")
        
        if selected_option["time_required"] == "high":
            consequences.append("Will take extended time to complete")
        
        if selected_option["risk_level"] == "high":
            consequences.append("Carries higher risk of failure or side effects")
        
        if selected_option["estimated_success"] > 0.8:
            consequences.append("High probability of successful completion")
        
        return consequences
    
    async def _execute_decision(self, decision: Decision):
        """Execute the selected decision"""
        
        if not self.autonomy_enabled:
            return
        
        # This would trigger the actual execution of actions
        # For now, just log the decision
        logger.info(f"Executing decision: {decision.selected_option['name']}")
    
    async def _check_success_criteria(self, goal: Goal) -> bool:
        """Check if goal success criteria are met"""
        
        # Simple criteria checking
        # In production, this would evaluate actual system state
        
        if not goal.success_criteria:
            return False
        
        # Check if all criteria are met (simplified)
        return len(goal.success_criteria) > 0
    
    async def _needs_planning(self, goal: Goal) -> bool:
        """Check if a goal needs planning"""
        
        # Check if goal has pending actions
        goal_actions = [action for action in self.actions.values() if action.goal_id == goal.goal_id]
        pending_actions = [action for action in goal_actions if action.status == ActionStatus.PENDING]
        
        return len(pending_actions) == 0 and goal.status == GoalStatus.ACTIVE
    
    async def _plan_for_goal(self, goal: Goal) -> List[str]:
        """Generate new actions for a goal"""
        
        # Generate additional actions if needed
        new_action_ids = []
        
        # This would implement more sophisticated planning logic
        # For now, just return empty list
        
        return new_action_ids
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of decision engine"""
        return {
            "decision_engine": True,
            "autonomy_enabled": self.autonomy_enabled,
            "safety_mode": self.safety_mode,
            "total_goals": len(self.goals),
            "active_goals": len([g for g in self.goals.values() if g.status == GoalStatus.ACTIVE]),
            "total_actions": len(self.actions),
            "total_decisions": len(self.decisions)
        }
