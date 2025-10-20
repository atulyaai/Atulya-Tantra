"""
Atulya Tantra - JARVIS Task Assistant
Version: 2.5.0
Task assistance system for decomposition, guidance, and problem solving
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import json
import uuid
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class TaskComplexity(Enum):
    """Task complexity levels"""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"


class TaskStatus(Enum):
    """Task status"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class TaskStep:
    """Individual step in a task"""
    step_id: str
    task_id: str
    step_number: int
    description: str
    instructions: List[str]
    estimated_time: Optional[int]  # minutes
    dependencies: List[str]  # step_ids
    status: TaskStatus
    completion_criteria: str
    resources: List[str]
    tips: List[str]


@dataclass
class Task:
    """Task breakdown structure"""
    task_id: str
    user_id: str
    conversation_id: str
    title: str
    description: str
    complexity: TaskComplexity
    category: str
    steps: List[TaskStep]
    status: TaskStatus
    priority: int  # 1-10
    estimated_total_time: Optional[int]  # minutes
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    metadata: Dict[str, Any]


@dataclass
class Recommendation:
    """Recommendation for user"""
    recommendation_id: str
    type: str  # "next_action", "best_practice", "efficiency_tip", "resource"
    title: str
    description: str
    priority: int  # 1-10
    context: str
    action_items: List[str]
    estimated_benefit: str


class TaskAssistant:
    """JARVIS Task Assistant for task breakdown and guidance"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.active_tasks = {}  # task_id -> Task
        self.user_tasks = defaultdict(list)  # user_id -> List[task_id]
        self.task_templates = self._initialize_task_templates()
        self.recommendations = defaultdict(list)  # user_id -> List[Recommendation]
        
        logger.info("TaskAssistant initialized")
    
    def _initialize_task_templates(self) -> Dict[str, Dict]:
        """Initialize common task templates"""
        return {
            "coding": {
                "steps": [
                    "Understand requirements",
                    "Design solution architecture",
                    "Implement core functionality",
                    "Add error handling",
                    "Write tests",
                    "Document code",
                    "Review and optimize"
                ],
                "estimated_time": 120,
                "complexity": TaskComplexity.MODERATE
            },
            "research": {
                "steps": [
                    "Define research question",
                    "Gather initial sources",
                    "Analyze and evaluate sources",
                    "Synthesize information",
                    "Draw conclusions",
                    "Create summary/report"
                ],
                "estimated_time": 90,
                "complexity": TaskComplexity.MODERATE
            },
            "creative_writing": {
                "steps": [
                    "Brainstorm ideas",
                    "Create outline",
                    "Write first draft",
                    "Revise content",
                    "Edit for clarity",
                    "Final review"
                ],
                "estimated_time": 150,
                "complexity": TaskComplexity.MODERATE
            },
            "problem_solving": {
                "steps": [
                    "Define the problem clearly",
                    "Gather relevant information",
                    "Generate potential solutions",
                    "Evaluate solutions",
                    "Select best solution",
                    "Implement solution",
                    "Monitor results"
                ],
                "estimated_time": 60,
                "complexity": TaskComplexity.MODERATE
            }
        }
    
    async def create_task_breakdown(
        self,
        user_id: str,
        conversation_id: str,
        task_description: str,
        category: str = "general"
    ) -> Task:
        """Create a detailed task breakdown"""
        
        task_id = str(uuid.uuid4())
        
        # Analyze task complexity
        complexity = await self._analyze_task_complexity(task_description)
        
        # Generate steps
        steps = await self._generate_task_steps(task_description, category, complexity)
        
        # Estimate total time
        estimated_time = sum(step.estimated_time or 0 for step in steps)
        
        # Create task
        task = Task(
            task_id=task_id,
            user_id=user_id,
            conversation_id=conversation_id,
            title=await self._generate_task_title(task_description),
            description=task_description,
            complexity=complexity,
            category=category,
            steps=steps,
            status=TaskStatus.NOT_STARTED,
            priority=5,  # Default priority
            estimated_total_time=estimated_time,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            completed_at=None,
            metadata={}
        )
        
        # Store task
        self.active_tasks[task_id] = task
        self.user_tasks[user_id].append(task_id)
        
        logger.info(f"Created task breakdown for user {user_id}: {task.title}")
        return task
    
    async def get_task_progress(self, task_id: str) -> Dict[str, Any]:
        """Get progress information for a task"""
        
        if task_id not in self.active_tasks:
            return {"error": "Task not found"}
        
        task = self.active_tasks[task_id]
        
        completed_steps = sum(1 for step in task.steps if step.status == TaskStatus.COMPLETED)
        total_steps = len(task.steps)
        progress_percentage = (completed_steps / total_steps) * 100 if total_steps > 0 else 0
        
        # Calculate time spent (simplified)
        time_spent = 0  # This would be tracked in a real implementation
        
        return {
            "task_id": task_id,
            "title": task.title,
            "status": task.status.value,
            "progress_percentage": progress_percentage,
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "time_spent": time_spent,
            "estimated_remaining": task.estimated_total_time - time_spent,
            "current_step": self._get_current_step(task),
            "next_steps": [step for step in task.steps if step.status == TaskStatus.NOT_STARTED][:3]
        }
    
    async def provide_step_guidance(
        self,
        task_id: str,
        step_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Provide detailed guidance for a specific step"""
        
        if task_id not in self.active_tasks:
            return {"error": "Task not found"}
        
        task = self.active_tasks[task_id]
        
        if step_id:
            # Find specific step
            step = next((s for s in task.steps if s.step_id == step_id), None)
            if not step:
                return {"error": "Step not found"}
        else:
            # Get current step
            step = self._get_current_step(task)
            if not step:
                return {"error": "No current step"}
        
        # Generate detailed guidance
        guidance = await self._generate_step_guidance(step, task)
        
        return {
            "step_id": step.step_id,
            "step_number": step.step_number,
            "description": step.description,
            "instructions": step.instructions,
            "guidance": guidance,
            "tips": step.tips,
            "resources": step.resources,
            "completion_criteria": step.completion_criteria,
            "estimated_time": step.estimated_time
        }
    
    async def suggest_next_actions(
        self,
        user_id: str,
        context: Dict[str, Any]
    ) -> List[Recommendation]:
        """Suggest next actions based on user context"""
        
        recommendations = []
        
        # Check active tasks
        user_task_ids = self.user_tasks.get(user_id, [])
        active_tasks = [self.active_tasks[tid] for tid in user_task_ids if tid in self.active_tasks]
        
        # Recommend continuing active tasks
        for task in active_tasks:
            if task.status == TaskStatus.IN_PROGRESS:
                current_step = self._get_current_step(task)
                if current_step:
                    recommendation = Recommendation(
                        recommendation_id=str(uuid.uuid4()),
                        type="next_action",
                        title=f"Continue working on: {task.title}",
                        description=f"Complete step {current_step.step_number}: {current_step.description}",
                        priority=8,
                        context=f"Active task: {task.task_id}",
                        action_items=[
                            f"Review step instructions: {current_step.description}",
                            f"Follow completion criteria: {current_step.completion_criteria}"
                        ],
                        estimated_benefit=f"Progress on {task.title} task"
                    )
                    recommendations.append(recommendation)
        
        # Recommend starting new tasks if none active
        if not active_tasks:
            recommendation = Recommendation(
                recommendation_id=str(uuid.uuid4()),
                type="next_action",
                title="Start a new task",
                description="You don't have any active tasks. Consider starting a new project or task.",
                priority=5,
                context="No active tasks",
                action_items=[
                    "Think about what you want to accomplish",
                    "Break down the task into smaller steps",
                    "Set a timeline for completion"
                ],
                estimated_benefit="Productivity and goal achievement"
            )
            recommendations.append(recommendation)
        
        # Add best practices based on context
        if context.get("time_of_day") == "morning":
            recommendation = Recommendation(
                recommendation_id=str(uuid.uuid4()),
                type="best_practice",
                title="Plan your day",
                description="Start your day by reviewing and prioritizing your tasks.",
                priority=7,
                context="Morning routine",
                action_items=[
                    "Review your task list",
                    "Set priorities for the day",
                    "Schedule focused work time"
                ],
                estimated_benefit="Better productivity and focus"
            )
            recommendations.append(recommendation)
        
        # Store recommendations
        self.recommendations[user_id].extend(recommendations)
        
        # Keep only recent recommendations
        if len(self.recommendations[user_id]) > 20:
            self.recommendations[user_id] = self.recommendations[user_id][-20:]
        
        # Sort by priority
        recommendations.sort(key=lambda x: x.priority, reverse=True)
        
        return recommendations[:5]  # Return top 5 recommendations
    
    async def update_task_status(
        self,
        task_id: str,
        step_id: Optional[str],
        new_status: TaskStatus,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update task or step status"""
        
        if task_id not in self.active_tasks:
            return {"error": "Task not found"}
        
        task = self.active_tasks[task_id]
        
        if step_id:
            # Update specific step
            step = next((s for s in task.steps if s.step_id == step_id), None)
            if not step:
                return {"error": "Step not found"}
            
            step.status = new_status
            
            # Update task status based on step completion
            if new_status == TaskStatus.COMPLETED:
                all_steps_completed = all(
                    s.status == TaskStatus.COMPLETED for s in task.steps
                )
                if all_steps_completed:
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = datetime.now()
                else:
                    task.status = TaskStatus.IN_PROGRESS
            
        else:
            # Update entire task
            task.status = new_status
            if new_status == TaskStatus.COMPLETED:
                task.completed_at = datetime.now()
                # Mark all steps as completed
                for step in task.steps:
                    step.status = TaskStatus.COMPLETED
        
        task.updated_at = datetime.now()
        
        return {
            "task_id": task_id,
            "status": task.status.value,
            "updated_at": task.updated_at.isoformat(),
            "progress": await self.get_task_progress(task_id)
        }
    
    async def _analyze_task_complexity(self, task_description: str) -> TaskComplexity:
        """Analyze task complexity based on description"""
        
        description_lower = task_description.lower()
        
        # Simple heuristics for complexity analysis
        complex_indicators = [
            "complex", "advanced", "multiple", "several", "various", "comprehensive",
            "detailed", "thorough", "extensive", "sophisticated", "intricate"
        ]
        
        very_complex_indicators = [
            "very complex", "extremely", "highly sophisticated", "multi-step",
            "requires expertise", "advanced knowledge", "specialized"
        ]
        
        simple_indicators = [
            "simple", "basic", "quick", "easy", "straightforward", "single"
        ]
        
        # Count indicators
        very_complex_count = sum(1 for indicator in very_complex_indicators if indicator in description_lower)
        complex_count = sum(1 for indicator in complex_indicators if indicator in description_lower)
        simple_count = sum(1 for indicator in simple_indicators if indicator in description_lower)
        
        # Word count as complexity indicator
        word_count = len(task_description.split())
        
        # Determine complexity
        if very_complex_count > 0 or word_count > 100:
            return TaskComplexity.VERY_COMPLEX
        elif complex_count > 1 or word_count > 50:
            return TaskComplexity.COMPLEX
        elif simple_count > 0 or word_count < 20:
            return TaskComplexity.SIMPLE
        else:
            return TaskComplexity.MODERATE
    
    async def _generate_task_steps(
        self,
        task_description: str,
        category: str,
        complexity: TaskComplexity
    ) -> List[TaskStep]:
        """Generate task steps based on description and category"""
        
        steps = []
        
        # Use template if available
        if category in self.task_templates:
            template = self.task_templates[category]
            template_steps = template["steps"]
            base_time = template["estimated_time"] // len(template_steps)
        else:
            # Generic steps based on complexity
            if complexity == TaskComplexity.SIMPLE:
                template_steps = ["Plan approach", "Execute task", "Review results"]
                base_time = 15
            elif complexity == TaskComplexity.MODERATE:
                template_steps = ["Analyze requirements", "Plan solution", "Implement", "Test", "Review"]
                base_time = 30
            elif complexity == TaskComplexity.COMPLEX:
                template_steps = [
                    "Research and analyze", "Design solution", "Plan implementation",
                    "Implement core features", "Add advanced features", "Test thoroughly",
                    "Optimize and refine", "Document and review"
                ]
                base_time = 45
            else:  # VERY_COMPLEX
                template_steps = [
                    "Research and analysis", "Requirements gathering", "Solution design",
                    "Architecture planning", "Implementation planning", "Core development",
                    "Feature development", "Integration", "Testing and validation",
                    "Optimization", "Documentation", "Final review"
                ]
                base_time = 60
        
        # Create steps
        for i, step_desc in enumerate(template_steps):
            step_id = str(uuid.uuid4())
            
            # Generate detailed instructions
            instructions = await self._generate_step_instructions(step_desc, category, complexity)
            
            # Estimate time (base time with complexity multiplier)
            complexity_multiplier = {
                TaskComplexity.SIMPLE: 0.5,
                TaskComplexity.MODERATE: 1.0,
                TaskComplexity.COMPLEX: 1.5,
                TaskComplexity.VERY_COMPLEX: 2.0
            }
            estimated_time = int(base_time * complexity_multiplier[complexity])
            
            step = TaskStep(
                step_id=step_id,
                task_id="",  # Will be set when task is created
                step_number=i + 1,
                description=step_desc,
                instructions=instructions,
                estimated_time=estimated_time,
                dependencies=[],  # Could be enhanced to detect dependencies
                status=TaskStatus.NOT_STARTED,
                completion_criteria=await self._generate_completion_criteria(step_desc, category),
                resources=await self._suggest_resources(step_desc, category),
                tips=await self._generate_tips(step_desc, category)
            )
            
            steps.append(step)
        
        return steps
    
    async def _generate_task_title(self, task_description: str) -> str:
        """Generate a concise task title from description"""
        
        # Simple title generation - take first few words
        words = task_description.split()[:8]
        title = " ".join(words)
        
        if len(title) > 60:
            title = title[:57] + "..."
        
        return title
    
    async def _generate_step_instructions(
        self,
        step_description: str,
        category: str,
        complexity: TaskComplexity
    ) -> List[str]:
        """Generate detailed instructions for a step"""
        
        instructions = []
        
        # Base instructions based on step type
        if "research" in step_description.lower() or "analyze" in step_description.lower():
            instructions = [
                "Gather relevant information from reliable sources",
                "Organize information systematically",
                "Identify key points and patterns",
                "Document findings clearly"
            ]
        elif "plan" in step_description.lower() or "design" in step_description.lower():
            instructions = [
                "Define objectives and requirements",
                "Consider different approaches",
                "Create a structured plan",
                "Identify potential challenges"
            ]
        elif "implement" in step_description.lower() or "execute" in step_description.lower():
            instructions = [
                "Follow the established plan",
                "Work systematically through each component",
                "Test functionality as you go",
                "Document any issues or changes"
            ]
        elif "test" in step_description.lower() or "review" in step_description.lower():
            instructions = [
                "Test all functionality thoroughly",
                "Check for errors and edge cases",
                "Verify requirements are met",
                "Document results and findings"
            ]
        else:
            instructions = [
                "Approach this step methodically",
                "Take your time to do it well",
                "Ask for help if needed",
                "Document your progress"
            ]
        
        # Add complexity-specific instructions
        if complexity in [TaskComplexity.COMPLEX, TaskComplexity.VERY_COMPLEX]:
            instructions.append("Break down into smaller sub-tasks if needed")
            instructions.append("Consider seeking expert advice for complex aspects")
        
        return instructions
    
    async def _generate_completion_criteria(
        self,
        step_description: str,
        category: str
    ) -> str:
        """Generate completion criteria for a step"""
        
        if "research" in step_description.lower():
            return "Comprehensive information gathered and organized"
        elif "plan" in step_description.lower():
            return "Clear plan documented with specific steps"
        elif "implement" in step_description.lower():
            return "Functionality implemented and working correctly"
        elif "test" in step_description.lower():
            return "All tests passed and functionality verified"
        elif "review" in step_description.lower():
            return "Thorough review completed with recommendations"
        else:
            return "Step objectives achieved and documented"
    
    async def _suggest_resources(
        self,
        step_description: str,
        category: str
    ) -> List[str]:
        """Suggest resources for a step"""
        
        resources = []
        
        if category == "coding":
            resources.extend([
                "Programming documentation",
                "Code examples and tutorials",
                "Development environment setup",
                "Testing frameworks"
            ])
        elif category == "research":
            resources.extend([
                "Academic databases",
                "Reliable online sources",
                "Expert interviews",
                "Reference materials"
            ])
        elif category == "creative_writing":
            resources.extend([
                "Writing guides and style books",
                "Inspiration sources",
                "Editing tools",
                "Feedback from others"
            ])
        
        return resources
    
    async def _generate_tips(
        self,
        step_description: str,
        category: str
    ) -> List[str]:
        """Generate helpful tips for a step"""
        
        tips = []
        
        if "research" in step_description.lower():
            tips.extend([
                "Use multiple sources to verify information",
                "Take notes as you research",
                "Keep track of your sources"
            ])
        elif "plan" in step_description.lower():
            tips.extend([
                "Start with the end goal in mind",
                "Consider potential obstacles",
                "Be flexible with your plan"
            ])
        elif "implement" in step_description.lower():
            tips.extend([
                "Test frequently as you work",
                "Keep your code organized",
                "Document your progress"
            ])
        
        return tips
    
    def _get_current_step(self, task: Task) -> Optional[TaskStep]:
        """Get the current step for a task"""
        
        # Find the first step that's not completed
        for step in task.steps:
            if step.status in [TaskStatus.NOT_STARTED, TaskStatus.IN_PROGRESS]:
                return step
        
        return None
    
    async def _generate_step_guidance(self, step: TaskStep, task: Task) -> str:
        """Generate detailed guidance for a step"""
        
        guidance_parts = [
            f"This is step {step.step_number} of {len(task.steps)} in your task: {task.title}",
            f"Description: {step.description}",
            "",
            "Instructions:",
        ]
        
        for i, instruction in enumerate(step.instructions, 1):
            guidance_parts.append(f"{i}. {instruction}")
        
        if step.tips:
            guidance_parts.extend([
                "",
                "Tips:",
            ])
            for tip in step.tips:
                guidance_parts.append(f"• {tip}")
        
        if step.resources:
            guidance_parts.extend([
                "",
                "Helpful Resources:",
            ])
            for resource in step.resources:
                guidance_parts.append(f"• {resource}")
        
        guidance_parts.extend([
            "",
            f"Completion Criteria: {step.completion_criteria}",
            f"Estimated Time: {step.estimated_time} minutes"
        ])
        
        return "\n".join(guidance_parts)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of task assistant"""
        return {
            "task_assistant": True,
            "active_tasks": len(self.active_tasks),
            "total_users": len(self.user_tasks),
            "task_templates": len(self.task_templates),
            "total_recommendations": sum(len(recs) for recs in self.recommendations.values())
        }
