"""Automation framework for task scheduling and execution"""

from typing import Dict, List, Callable, Any, Optional
import logging
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class AutomationRule:
    """Represents an automation rule"""

    def __init__(self, rule_id: str, trigger: Callable, action: Callable, enabled: bool = True):
        """
        Initialize automation rule
        
        Args:
            rule_id: Unique rule identifier
            trigger: Function that returns True when rule should execute
            action: Function to execute when triggered
            enabled: Whether rule is active
        """
        self.rule_id = rule_id
        self.trigger = trigger
        self.action = action
        self.enabled = enabled
        self.last_executed = None
        self.execution_count = 0


class TaskScheduler:
    """
    Automated task scheduling and execution
    """

    def __init__(self):
        """Initialize Task Scheduler"""
        self.scheduled_tasks = {}
        self.automation_rules = {}
        self.execution_log = []
        logger.info("Task Scheduler initialized")

    def schedule_task(self, task_id: str, task_func: Callable,
                     schedule_time: datetime, repeat: Optional[str] = None) -> bool:
        """
        Schedule a task for execution
        
        Args:
            task_id: Unique task identifier
            task_func: Function to execute
            schedule_time: When to execute
            repeat: Repeat pattern (hourly, daily, weekly, etc.)
            
        Returns:
            Success status
        """
        task = {
            "id": task_id,
            "function": task_func,
            "scheduled_time": schedule_time,
            "repeat": repeat,
            "created_at": datetime.now(),
            "status": "scheduled",
            "execution_count": 0
        }
        
        self.scheduled_tasks[task_id] = task
        logger.info(f"Task '{task_id}' scheduled for {schedule_time}")
        
        return True

    def add_automation_rule(self, rule_id: str, trigger: Callable,
                          action: Callable, enabled: bool = True) -> bool:
        """
        Add automation rule
        
        Args:
            rule_id: Unique rule identifier
            trigger: Trigger condition function
            action: Action to perform
            enabled: Whether rule is active
            
        Returns:
            Success status
        """
        rule = AutomationRule(rule_id, trigger, action, enabled)
        self.automation_rules[rule_id] = rule
        
        logger.info(f"Automation rule '{rule_id}' added")
        return True

    def execute_pending_tasks(self) -> Dict[str, Any]:
        """
        Execute all pending scheduled tasks
        
        Returns:
            Execution summary
        """
        current_time = datetime.now()
        executed = []
        failed = []
        
        for task_id, task in list(self.scheduled_tasks.items()):
            if task["status"] != "scheduled":
                continue
            
            if current_time >= task["scheduled_time"]:
                try:
                    result = task["function"]()
                    task["status"] = "completed"
                    task["execution_count"] += 1
                    executed.append(task_id)
                    
                    self.execution_log.append({
                        "task_id": task_id,
                        "execution_time": current_time.isoformat(),
                        "status": "completed",
                        "result": result
                    })
                    
                    # Reschedule if repeating
                    if task["repeat"]:
                        self._reschedule_task(task)
                    
                except Exception as e:
                    failed.append({
                        "task_id": task_id,
                        "error": str(e)
                    })
                    logger.error(f"Task '{task_id}' execution failed: {str(e)}")
        
        return {
            "executed": executed,
            "failed": failed,
            "total_executed": len(executed)
        }

    def evaluate_automation_rules(self) -> Dict[str, Any]:
        """
        Evaluate and execute triggered automation rules
        
        Returns:
            Rules execution summary
        """
        triggered = []
        executed = []
        
        for rule_id, rule in self.automation_rules.items():
            if not rule.enabled:
                continue
            
            try:
                if rule.trigger():
                    triggered.append(rule_id)
                    rule.action()
                    rule.last_executed = datetime.now()
                    rule.execution_count += 1
                    executed.append(rule_id)
                    
                    logger.info(f"Automation rule '{rule_id}' triggered and executed")
                    
            except Exception as e:
                logger.error(f"Rule '{rule_id}' execution failed: {str(e)}")
        
        return {
            "triggered": triggered,
            "executed": executed,
            "total_triggered": len(triggered)
        }

    def _reschedule_task(self, task: Dict) -> None:
        """
        Reschedule repeating task
        
        Args:
            task: Task to reschedule
        """
        repeat = task["repeat"]
        current_time = task["scheduled_time"]
        
        if repeat == "hourly":
            task["scheduled_time"] = current_time + timedelta(hours=1)
        elif repeat == "daily":
            task["scheduled_time"] = current_time + timedelta(days=1)
        elif repeat == "weekly":
            task["scheduled_time"] = current_time + timedelta(weeks=1)
        
        task["status"] = "scheduled"

    def get_scheduled_tasks(self) -> List[Dict]:
        """
        Get all scheduled tasks
        
        Returns:
            List of scheduled tasks
        """
        return [
            {
                "id": task["id"],
                "scheduled_time": task["scheduled_time"].isoformat(),
                "status": task["status"],
                "execution_count": task["execution_count"]
            }
            for task in self.scheduled_tasks.values()
        ]

    def disable_rule(self, rule_id: str) -> bool:
        """
        Disable automation rule
        
        Args:
            rule_id: Rule identifier
            
        Returns:
            Success status
        """
        if rule_id in self.automation_rules:
            self.automation_rules[rule_id].enabled = False
            return True
        return False

    def enable_rule(self, rule_id: str) -> bool:
        """
        Enable automation rule
        
        Args:
            rule_id: Rule identifier
            
        Returns:
            Success status
        """
        if rule_id in self.automation_rules:
            self.automation_rules[rule_id].enabled = True
            return True
        return False
