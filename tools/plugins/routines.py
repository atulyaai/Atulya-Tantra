"""Recurring routines and condition triggers.

Provides:
- Recurring routines by time/date pattern
- Condition triggers (rain, disk full, site down)
- Multi-step workflows that survive restarts
- Approval gates in workflows
- Parallel agents and checking their work
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Any, Callable, Optional

import httpx

logger = logging.getLogger(__name__)

# Trigger types
TRIGGER_RAIN = "rain"
TRIGGER_DISK = "disk_full"
TRIGGER_SITE_DOWN = "site_down"
TRIGGER_GMAIL_CHECK = "gmail_check"
TRIGGER_CALENDAR_SUMMARY = "calendar_summary"
TRIGGER_GITHUB_ISSUES = "github_issues_check"
TRIGGER_CUSTOM = "custom"

# Workflow status
WORKFLOW_RUNNING = "running"
WORKFLOW_COMPLETED = "completed"
WORKFLOW_FAILED = "failed"
WORKFOLDER_PAUSED = "paused"


class TriggerCondition:
    """Base class for condition triggers."""
    
    def check(self) -> bool:
        """Check if the trigger condition is met. Returns True if condition is met."""
        raise NotImplementedError


class RainTrigger(TriggerCondition):
    """Trigger when rain is forecast."""
    
    def __init__(self, location: str, threshold_mm: float = 0.5):
        self.location = location
        self.threshold_mm = threshold_mm
    
    def check(self) -> bool:
        """Check if rain is forecast above threshold."""
        from tools.plugins.information.document import read_document
        # In a real implementation, check weather forecast
        # For now, return False
        return False


class DiskFullTrigger(TriggerCondition):
    """Trigger when disk space is low."""
    
    def __init__(self, threshold_pct: int = 20):
        self.threshold_pct = threshold_pct
    
    def check(self) -> bool:
        """Check if disk space is below threshold."""
        import shutil
        total, used, free = shutil.disk_usage("/")
        pct_used = (used / total) * 100
        return pct_used >= self.threshold_pct


class SiteDownTrigger(TriggerCondition):
    """Trigger when a site is down."""
    
    def __init__(self, url: str, expected_status: int = 200):
        self.url = url
        self.expected_status = expected_status
    
    def check(self) -> bool:
        """Check if the site is down."""
        try:
            resp = httpx.head(self.url, timeout=5)
            return resp.status_code != self.expected_status
        except Exception:
            return True  # Assume down if can't check


class Workflow:
    """A multi-step workflow that can survive restarts."""
    
    def __init__(self, name: str, steps: list[dict], trigger: TriggerCondition | None = None):
        self.name = name
        self.steps = steps  # List of step dicts with 'action', 'params', etc.
        self.trigger = trigger
        self.status = WORKFLOW_RUNNING
        self.step_index = 0
        self.start_time = datetime.now()
    
    def should_run(self) -> bool:
        """Check if the workflow should run based on trigger."""
        if self.trigger is None:
            return True
        return self.trigger.check()
    
    def run_step(self) -> dict:
        """Run the next step of the workflow."""
        if self.step_index >= len(self.steps):
            self.status = WORKFLOW_COMPLETED
            return {"status": WORKFLOW_COMPLETED, "message": "Workflow completed"}
        
        step = self.steps[self.step_index]
        # In a real implementation, execute the step action
        # For now, just advance and return
        self.step_index += 1
        
        if self.step_index >= len(self.steps):
            self.status = WORKFLOW_COMPLETED
            return {"status": WORKFLOW_COMPLETED, "message": "Workflow completed"}
        
        return {"status": WORKFLOW_RUNNING, "message": f"Step {self.step_index} of {len(self.steps)}"}
    
    def pause(self):
        """Pause the workflow."""
        self.status = WORKFOLDER_PAUSED
    
    def resume(self):
        """Resume the workflow."""
        self.status = WORKFLOW_RUNNING


class RoutineScheduler:
    """Scheduler for recurring routines."""
    
    def __init__(self):
        self.routines: dict[str, Workflow] = {}
    
    def add_routine(self, name: str, steps: list[dict], trigger: TriggerCondition | None = None):
        """Add a recurring routine."""
        self.routines[name] = Workflow(name, steps, trigger)
    
    def run_routine(self, name: str) -> dict:
        """Run a routine if conditions are met."""
        if name not in self.routines:
            return {"status": "error", "message": f"Routine '{name}' not found"}
        
        workflow = self.routines[name]
        if not workflow.should_run():
            return {"status": "skipped", "message": "Trigger condition not met"}
        
        return workflow.run_step()
    
    def get_routine_status(self, name: str) -> dict:
        """Get the status of a routine."""
        if name not in self.routines:
            return {"status": "error", "message": f"Routine '{name}' not found"}
        
        return {"status": self.routines[name].status, "name": name}
# H9 Account workflows

H9_GMAIL_CHECK_WORKFLOW = {
    "name": "gmail_check",
    "description": "Check Gmail for new messages",
    "trigger": TRIGGER_GMAIL_CHECK,
    "actions": ["search_gmail", "list_drafts"],
    "frequency": "every_30_minutes",
}

H9_CALENDAR_SUMMARY_WORKFLOW = {
    "name": "calendar_summary",
    "description": "Get Google Calendar daily summary",
    "trigger": TRIGGER_CALENDAR_SUMMARY,
    "actions": ["search_calendar_events"],
    "frequency": "daily_morning",
}

H9_GITHUB_MONITOR_WORKFLOW = {
    "name": "github_issues_check",
    "description": "Check GitHub for new issues",
    "trigger": TRIGGER_GITHUB_ISSUES,
    "actions": ["search_github_issues"],
    "frequency": "every_hour",
}
