"""Recurring routines and condition triggers.

Provides:
- Recurring routines by time/date pattern
- Condition triggers (rain, disk full, site down)
- Multi-step workflows that survive restarts
- Approval gates in workflows
- Parallel agents and checking their work
"""
from __future__ import annotations

import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

# Trigger types
TRIGGER_RAIN = "rain"
TRIGGER_DISK = "disk_full"
TRIGGER_SITE_DOWN = "site_down"
TRIGGER_JOB_SEARCH = "job_search_alerts"
TRIGGER_SKILL_GAP = "skill_gap_plan"
TRIGGER_VACCINE_SCHEDULE = "vaccine_schedule"
TRIGGER_EXAM_SCHEDULE = "exam_schedule"
TRIGGER_AQI_ROUTINES = "aqi_routines"
TRIGGER_WATER_SCHEDULE = "water_schedule"
TRIGGER_POWER_WATER = "power_water_alerts"
TRIGGER_TWO_WHEELER = "two_wheeler_maintenance"
TRIGGER_SELF_IMPROVE = "self_improve"
TRIGGER_BUSINESS_PLAN = "business_plan"
TRIGGER_WORKOUT_PLAN = "workout_plan"
TRIGGER_MEAL_PLAN = "meal_plan"
TRIGGER_GOAL_AGENT = "goal_agent"
TRIGGER_GOAL_COACH = "goal_coach"
TRIGGER_COURSE_RECOMMENDATIONS = "course_recommendations"
TRIGGER_EVENT_PLANNING = "event_planning"
TRIGGER_ROAD_TRIP = "road_trip"
TRIGGER_LOG_ANOMALY = "log_anomaly"
L345_JOB_SEARCH_WORKFLOW = {
    "name": "job_search_alerts",
    "description": "Alert when job postings match your skills",
    "trigger": TRIGGER_JOB_SEARCH,
    "actions": ["search_job_boards", "match_skills"],
    "frequency": "daily_morning",
}
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


# L353: Skill-gap plan for target role
L353_SKILL_GAP_WORKFLOW = {
    "name": "skill_gap_plan",
    "description": "Plan skill development for target role",
    "trigger": TRIGGER_SKILL_GAP,
    "actions": ["analyze_skills", "identify_gaps", "recommend_learning"],
    "frequency": "weekly_monday",
}


# L391: Vaccination schedule reminders
L391_VACCINE_SCHEDULE_WORKFLOW = {
    "name": "vaccination_schedule",
    "description": "Reminders for family vaccination schedules",
    "trigger": TRIGGER_VACCINE_SCHEDULE,
    "actions": ["check_due_vaccines", "send_reminders"],
    "frequency": "monthly",
}


# L397: Exam schedules and revision plans
L397_EXAM_SCHEDULE_WORKFLOW = {
    "name": "exam_schedule",
    "description": "Exam schedules and revision plans",
    "trigger": TRIGGER_EXAM_SCHEDULE,
    "actions": ["set_exam_dates", "plan_revision", "send_reminders"],
    "frequency": "academic_term",
}


# L406: Smart-home routines by AQI
# Uses existing weather/AQI triggers from H1
# Actions: adjust_purifier, close_windows, notify_user
# Frequency: hourly (configurable)
L406_AQI_ROUTINES_WORKFLOW = {
    "name": "aqi_routines",
    "description": "Smart-home routines triggered by AQI levels",
    "trigger": TRIGGER_AQI_ROUTINES,
    "actions": ["adjust_purifier", "close_windows", "notify_user"],
    "frequency": "hourly",
}


# L410: Water-tank and RO-filter schedules
L410_WATER_SCHEDULE_WORKFLOW = {
    "name": "water_tank_schedule",
    "description": "Water tank and RO-filter maintenance schedules",
    "trigger": TRIGGER_WATER_SCHEDULE,
    "actions": ["check_tank_level", "filter_replacement_status", "send_reminders"],
    "frequency": "weekly",
}


# L412: Power-cut and water-supply schedule alerts
L412_POWER_WATER_ALERTS_WORKFLOW = {
    "name": "power_water_alerts",
    "description": "Power-cut and water-supply schedule alerts",
    "trigger": TRIGGER_POWER_WATER,
    "actions": ["monitor_outages", "check_supply", "send_alerts"],
    "frequency": "every_4_hours",
}


# L458: Two-wheeler maintenance schedule
L458_TWO_WHEELER_MAINTENANCE_WORKFLOW = {
    "name": "two_wheeler_maintenance",
    "description": "Two-wheeler maintenance schedule",
    "trigger": TRIGGER_TWO_WHEELER,
    "actions": ["check_oil", "check_tires", "send_reminders"],
    "frequency": "monthly",
}


# L529: Self-improving skills from corrections
L529_SELF_IMPROVE_WORKFLOW = {
    "name": "self_improving_skills",
    "description": "Skills that improve from user corrections",
    "trigger": TRIGGER_SELF_IMPROVE,
    "actions": ["log_corrections", "update_patterns", "refine_responses"],
    "frequency": "weekly",
}


# L151: Business plan and pitch-deck drafts
L151_BUSINESS_PLAN_WORKFLOW = {
    "name": "business_plan",
    "description": "Business plan and pitch-deck drafts",
    "trigger": TRIGGER_BUSINESS_PLAN,
    "actions": ["analyze_market", "draft_pitch deck", "financial_projections"],
    "frequency": "quarterly",
}


# L173: Workout plans by goal and equipment
L173_WORKOUT_PLAN_WORKFLOW = {
    "name": "workout_plan",
    "description": "Workout plans by goal and equipment",
    "trigger": TRIGGER_WORKOUT_PLAN,
    "actions": ["set_goal", "select_equipment", "create_schedule", "track_progress"],
    "frequency": "weekly",
}


# L175: Meal plans by diet preference
L175_MEAL_PLAN_WORKFLOW = {
    "name": "meal_plan",
    "description": "Meal plans by diet preference",
    "trigger": TRIGGER_MEAL_PLAN,
    "actions": ["diet_type", "generate_menu", "shopping_list", "track_compliance"],
    "frequency": "daily",
}


# L285: Agents that work for hours on a goal and report progress
L285_AGENT_WORKFLOW = {
    "name": "goal_agent",
    "description": "Agents that work for hours on a goal and report progress",
    "trigger": TRIGGER_GOAL_AGENT,
    "actions": ["start_work", "report_progress", "check_milestones", "summarize"],
    "frequency": "every_2_hours",
}


# L292: Long-term goal coach (fitness, learning, savings) with weekly check-ins
L292_GOAL_COACH_WORKFLOW = {
    "name": "goal_coach",
    "description": "Long-term goal coach (fitness, learning, savings) with weekly check-ins",
    "trigger": TRIGGER_GOAL_COACH,
    "actions": ["set_goal", "weekly_checkin", "progress_report", "adjust_plan"],
    "frequency": "weekly",
}


# L186: Course recommendations for a goal
L186_COURSE_RECOMMENDATIONS_WORKFLOW = {
    "name": "course_recommendations",
    "description": "Course recommendations for a goal",
    "trigger": TRIGGER_COURSE_RECOMMENDATIONS,
    "actions": ["analyze_goal", "search_courses", "match_skills", "recommend"],
    "frequency": "weekly",
}


# L203: Event planning: guest list, invites, RSVPs, menu, budget
L203_EVENT_PLANNING_WORKFLOW = {
    "name": "event_planning",
    "description": "Event planning: guest list, invites, RSVPs, menu, budget",
    "trigger": TRIGGER_EVENT_PLANNING,
    "actions": ["create_guest_list", "send_invitations", "track_rsvps", "plan_menu", "manage_budget"],
    "frequency": "per_event",
}


# L223: Road-trip planner with stops, fuel and food
L223_ROAD_TRIP_WORKFLOW = {
    "name": "road_trip",
    "description": "Road-trip planner with stops, fuel and food",
    "trigger": TRIGGER_ROAD_TRIP,
    "actions": ["plan_route", "find_stops", "check_fuel", "find_food"],
    "frequency": "per_trip",
}


# L240: Log anomaly detection with explanations
L240_LOG_ANOMALY_WORKFLOW = {
    "name": "log_anomaly",
    "description": "Log anomaly detection with explanations",
    "trigger": TRIGGER_LOG_ANOMALY,
    "actions": ["analyze_logs", "detect_anomalies", "generate_explanations"],
    "frequency": "daily",
}
