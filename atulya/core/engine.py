"""
Main Atulya Engine - Core AI Assistant System
Handles task execution, learning, and evolution
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging
import yaml

from atulya.memory.memory_manager import MemoryManager
from atulya.evolution.evolution_engine import EvolutionEngine
from atulya.agents.task_agent import TaskAgent
from atulya.skills.skill_manager import SkillManager
from atulya.core.nlp_engine import NLPEngine
from atulya.automation.task_scheduler import TaskScheduler
from atulya.integrations.integration_manager import IntegrationManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Atulya:
    """
    Main Atulya AI Assistant Class
    Integrates all subsystems for autonomous AI operation
    """

    def __init__(self, name: str = "Atulya", config_path: Optional[str] = None):
        """
        Initialize Atulya AI Assistant
        
        Args:
            name: Name of the assistant
            config_path: Path to configuration file
        """
        self.name = name
        self.created_at = datetime.now()
        self.version = "0.1.0"

        # Load configuration
        cfg_path = config_path or os.getenv("ATULYA_CONFIG", "config/atulya_config.yaml")
        self.config = self._load_config(cfg_path)

        # Initialize subsystems
        self.memory = MemoryManager()
        self.evolution = EvolutionEngine()
        self.task_agent = TaskAgent()
        self.skill_manager = SkillManager()
        self.nlp_engine = NLPEngine()
        self.automation = TaskScheduler()
        self.integrations = IntegrationManager()

        # Apply config parameters to subsystems
        self._apply_config()

        # Statistics
        self.stats = {
            "tasks_executed": 0,
            "learning_iterations": 0,
            "skills_learned": 0,
            "evolution_score": 0.0,
            "accuracy": 0.0
        }
        
        logger.info(f"{self.name} initialized successfully")

        # Run startup tasks from config (non-blocking simple execution)
        self._run_startup_tasks()

        # Register simple automation rules from config
        self._register_automation_rules()

    def execute_task(self, task_description: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute a task autonomously
        
        Args:
            task_description: Natural language task description
            context: Optional context information
            
        Returns:
            Task execution result
        """
        logger.info(f"Executing task: {task_description}")
        
        # Parse task using NLP
        parsed_task = self.nlp_engine.parse_task(task_description)
        
        # Check memory for similar tasks
        similar_tasks = self.memory.search_similar(task_description)
        
        # Execute task
        result = self.task_agent.execute(parsed_task, context or {})
        
        # Store result in memory
        self.memory.store_task_result(task_description, result)
        
        # Learn from execution
        self.learn_from_task(task_description, result)
        
        # Update statistics
        self.stats["tasks_executed"] += 1
        
        return result

    def _load_config(self, path: str) -> Dict[str, Any]:
        """Load YAML config from path, return dict."""
        try:
            with open(path, "r") as f:
                cfg = yaml.safe_load(f) or {}
            logger.info(f"Loaded config from {path}")
            return cfg
        except FileNotFoundError:
            logger.warning(f"Config file not found at {path}, using defaults")
            return {}

    def _apply_config(self) -> None:
        """Apply selected configuration entries to subsystems."""
        # Memory settings
        mem_cfg = self.config.get("memory", {})
        # (MemoryManager currently has no setters; kept for future extension)

        # Evolution settings
        evo_cfg = self.config.get("evolution", {})
        if evo_cfg:
            for k, v in evo_cfg.items():
                if k in self.evolution.parameters:
                    self.evolution.parameters[k.replace("initial_", "")] = v

        # Load initial skills from config
        initial_skills = self.config.get("initial_skills", [])
        for s in initial_skills:
            name = s.get("name")
            data = s.get("data", {})
            if name:
                self.acquire_skill(name, data)

    def _run_startup_tasks(self) -> None:
        tasks = self.config.get("automation", {}).get("startup_tasks", [])
        for t in tasks:
            task_desc = t.get("task") or t.get("description")
            if task_desc:
                try:
                    self.execute_task(task_desc)
                except Exception:
                    logger.exception("Startup task failed")

    def _register_automation_rules(self) -> None:
        rules = self.config.get("automation", {}).get("rules", [])
        for rule in rules:
            rtype = rule.get("type")
            rid = rule.get("id")
            action_task = rule.get("action_task")
            if not rid or not action_task:
                continue

            if rtype == "on_start":
                # execute once now
                try:
                    self.execute_task(action_task)
                    logger.info(f"Executed on_start rule {rid}")
                except Exception:
                    logger.exception(f"Failed on_start rule {rid}")

            elif rtype == "interval_seconds":
                every = int(rule.get("every", 0))
                if every > 0:
                    # create a simple scheduled task that wraps execute_task
                    def make_task(desc):
                        return lambda: self.execute_task(desc)

                    task_id = f"rule_{rid}"
                    self.automation.schedule_task(task_id, make_task(action_task), datetime.now(), repeat=None)
                    logger.info(f"Registered interval rule {rid} (every {every}s) as scheduled task {task_id}")

    def learn_from_task(self, task: str, result: Dict) -> None:
        """
        Learn from task execution and improve performance
        
        Args:
            task: Task description
            result: Task execution result
        """
        # Extract insights
        insights = self._extract_insights(result)
        
        # Promote evolution
        self.evolution.evolve(task, result, insights)
        
        self.stats["learning_iterations"] += 1
        logger.info(f"Learning iteration {self.stats['learning_iterations']} completed")

    def acquire_skill(self, skill_name: str, skill_data: Dict) -> bool:
        """
        Acquire a new skill
        
        Args:
            skill_name: Name of the skill
            skill_data: Skill training data
            
        Returns:
            Success status
        """
        success = self.skill_manager.add_skill(skill_name, skill_data)
        if success:
            self.stats["skills_learned"] += 1
            logger.info(f"Skill '{skill_name}' acquired")
        return success

    def get_evolution_status(self) -> Dict[str, Any]:
        """
        Get current evolution and learning status
        
        Returns:
            Evolution status details
        """
        status = {
            "name": self.name,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "stats": self.stats,
            "memory_size": self.memory.get_size(),
            "skills_count": self.skill_manager.count_skills(),
            "evolution_metrics": self.evolution.get_metrics()
        }
        return status

    def _extract_insights(self, result: Dict) -> Dict:
        """
        Extract learning insights from task result
        
        Args:
            result: Task execution result
            
        Returns:
            Extracted insights
        """
        insights = {
            "success": result.get("success", False),
            "confidence": result.get("confidence", 0.0),
            "execution_time": result.get("execution_time", 0),
            "complexity": result.get("complexity", "medium")
        }
        return insights

    def optimize_performance(self) -> Dict:
        """
        Optimize system performance based on collected data
        
        Returns:
            Optimization results
        """
        optimizations = {
            "memory_optimization": self.memory.optimize(),
            "skill_refinement": self.skill_manager.refine_skills(),
            "evolution_boost": self.evolution.boost_learning()
        }
        logger.info("System optimization completed")
        return optimizations

    def __repr__(self):
        return f"<Atulya name='{self.name}' version='{self.version}'>"
