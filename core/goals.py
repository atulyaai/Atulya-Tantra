"""
Persistent Goals Module
Memory continuity for goal tracking across restarts.

CRITICAL CONSTRAINTS:
- Goals are created ONLY by explicit user instruction
- Goals are NEVER auto-executed
- GoalManager is the sole writer of goals
- Other components may read but must not modify goal state

This is memory continuity, NOT autonomy.
"""

import json
import os
import time
import uuid
import logging
from typing import List, Dict, Optional

logger = logging.getLogger("GoalManager")


class GoalManager:
    """
    Manages persistent goals across system restarts.
    
    IMPORTANT:
    - GoalManager is the sole writer of goals.
    - Other components may read but must not modify goal state.
    - Goals are created ONLY via explicit user instruction.
    """
    
    def __init__(self, storage_path: str = "memory/goals.json"):
        self.storage_path = storage_path
        self.goals_data = self._load()
        
    def _generate_trace_id(self) -> str:
        """Generate 8-char TraceID for auditability."""
        return uuid.uuid4().hex[:8]
    
    def _load(self) -> Dict:
        """
        Load goals from storage with corruption recovery.
        Returns empty state if file is missing or corrupted.
        """
        trace_id = self._generate_trace_id()
        
        if not os.path.exists(self.storage_path):
            logger.info(f"[{trace_id}] No existing goals file, starting fresh")
            return {"goals": [], "version": "1.0"}
        
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
            
            # Validate schema
            if "goals" not in data or "version" not in data:
                raise ValueError("Invalid goals schema")
            
            logger.info(f"[{trace_id}] Loaded {len(data['goals'])} goals from storage")
            return data
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"[{trace_id}] Corrupted goals.json ({str(e)}), resetting to empty")
            # Backup corrupted file
            if os.path.exists(self.storage_path):
                backup_path = self.storage_path + ".corrupted"
                # Remove existing backup if present
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                os.rename(self.storage_path, backup_path)
                logger.info(f"[{trace_id}] Backed up corrupted file to {backup_path}")
            
            return {"goals": [], "version": "1.0"}
    
    def _save(self) -> bool:
        """
        Save goals atomically (temp file + rename).
        Returns True on success, False on failure.
        """
        trace_id = self._generate_trace_id()
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            # Write to temp file first
            temp_path = self.storage_path + ".tmp"
            with open(temp_path, 'w') as f:
                json.dump(self.goals_data, f, indent=2)
            
            # Atomic rename
            os.replace(temp_path, self.storage_path)
            
            logger.info(f"[{trace_id}] Saved {len(self.goals_data['goals'])} goals to storage")
            return True
            
        except Exception as e:
            logger.error(f"[{trace_id}] Failed to save goals: {str(e)}")
            return False
    
    def add_goal(self, description: str, source: str = "user") -> str:
        """
        Create a new goal.
        
        TIGHTENING #1: Explicit source guard.
        Goals may ONLY be created by explicit user instruction.
        
        Args:
            description: Human-written goal description
            source: Must be "user" (enforced)
            
        Returns:
            goal_id (UUID string)
            
        Raises:
            PermissionError: If source is not "user"
        """
        if source != "user":
            raise PermissionError("Goals may only be created by explicit user instruction")
        
        trace_id = self._generate_trace_id()
        goal_id = str(uuid.uuid4())
        
        goal = {
            "goal_id": goal_id,
            "description": description,
            "status": "pending",
            "created_at": time.time(),
            "last_updated": time.time(),
            "last_action": None,
            "blocker": None
        }
        
        self.goals_data["goals"].append(goal)
        self._save()
        
        logger.info(f"[{trace_id}] Goal created: {goal_id} - '{description[:50]}...'")
        return goal_id
    
    def update_goal(
        self,
        goal_id: str,
        status: Optional[str] = None,
        last_action: Optional[str] = None,
        blocker: Optional[str] = None
    ) -> bool:
        """
        Update an existing goal.
        
        Args:
            goal_id: UUID of goal to update
            status: New status (pending|active|blocked|completed)
            last_action: Description of last action taken
            blocker: Description of blocker (if status=blocked)
            
        Returns:
            True if updated, False if goal not found
        """
        trace_id = self._generate_trace_id()
        
        for goal in self.goals_data["goals"]:
            if goal["goal_id"] == goal_id:
                if status:
                    goal["status"] = status
                if last_action is not None:
                    goal["last_action"] = last_action
                if blocker is not None:
                    goal["blocker"] = blocker
                
                goal["last_updated"] = time.time()
                self._save()
                
                logger.info(f"[{trace_id}] Goal updated: {goal_id} -> status={status}")
                return True
        
        logger.warning(f"[{trace_id}] Goal not found: {goal_id}")
        return False
    
    def get_active_goals(self) -> List[Dict]:
        """
        Get all goals with status='active'.
        
        TIGHTENING #2: Read-only access.
        Returns copies to prevent external modification.
        """
        return [
            goal.copy()
            for goal in self.goals_data["goals"]
            if goal["status"] == "active"
        ]
    
    def get_all_goals(self) -> List[Dict]:
        """
        Get all goals.
        
        TIGHTENING #2: Read-only access.
        Returns copies to prevent external modification.
        """
        return [goal.copy() for goal in self.goals_data["goals"]]
    
    def get_goal_by_id(self, goal_id: str) -> Optional[Dict]:
        """
        Get a specific goal by ID.
        
        TIGHTENING #2: Read-only access.
        Returns copy to prevent external modification.
        """
        for goal in self.goals_data["goals"]:
            if goal["goal_id"] == goal_id:
                return goal.copy()
        return None
    
    def load_goals(self) -> List[Dict]:
        """
        Reload goals from storage and return all goals.
        Used on system startup.
        
        Returns:
            List of all goals (read-only copies)
        """
        trace_id = self._generate_trace_id()
        self.goals_data = self._load()
        
        goals = self.get_all_goals()
        if goals:
            logger.info(f"[{trace_id}] Restored {len(goals)} goals from memory")
            for goal in goals:
                logger.info(
                    f"[{trace_id}] Goal loaded: {goal['goal_id'][:8]} - "
                    f"'{goal['description'][:50]}...' ({goal['status']})"
                )
        
        return goals
