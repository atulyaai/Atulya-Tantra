import json
import os
import time
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger("MemoryOrgan")

class Identity:
    """Unified Self-Model of JARVIS."""
    def __init__(self, storage_path: str = "memory/identity.json"):
        self.storage_path = storage_path
        self.name = "JARVIS (Atulya Tantra)"
        self.version = "1.2.0"
        self.capabilities = ["text_sensing", "voice_sensing", "vision_sensing", "governed_web_search", "persistent_memory", "safety_governance"]
        self.operating_mode = "STANDBY"
        self.current_responsibility = "Waiting for user input"
        self._load()

    def set_mode(self, mode: str):
        self.operating_mode = mode
        self._save()

    def set_responsibility(self, task: str):
        self.current_responsibility = task
        self._save()

    def get_self_description(self) -> str:
        return f"I am {self.name} v{self.version}. Mode: {self.operating_mode}. Active Task: {self.current_responsibility}. Capabilities: {', '.join(self.capabilities)}."

    def _save(self):
        data = {"name": self.name, "version": self.version, "capabilities": self.capabilities, "mode": self.operating_mode, "task": self.current_responsibility}
        with open(self.storage_path, 'w') as f: json.dump(data, f, indent=2)

    def _load(self):
        if os.path.exists(self.storage_path):
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                self.operating_mode = data.get("mode", "STANDBY")
                self.current_responsibility = data.get("task", "Waiting for user input")

class GoalManager:
    """Persistent hierarchical goal tracking."""
    def __init__(self, storage_path: str = "memory/goals.json"):
        self.storage_path = storage_path
        self.goals_data = self._load()

    def _load(self):
        if os.path.exists(self.storage_path):
            with open(self.storage_path, 'r') as f: return json.load(f)
        return {"goals": [], "version": "1.1"}

    def _save(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, 'w') as f: json.dump(self.goals_data, f, indent=2)

    def add_goal(self, description: str, source: str = "user", priority: int = 3, parent_id: str = None) -> str:
        if source not in ["user", "system"]: raise PermissionError("Invalid source")
        goal_id = str(uuid.uuid4())
        goal = {"goal_id": goal_id, "parent_id": parent_id, "description": description, "source": source, "priority": priority, "status": "pending", "created_at": time.time(), "sub_goals": []}
        if parent_id:
            for p in self.goals_data["goals"]:
                if p["goal_id"] == parent_id: p["sub_goals"].append(goal_id); break
        self.goals_data["goals"].append(goal)
        self._save()
        return goal_id

    def load_goals(self):
        return self.get_all_goals()

    def get_active_goals(self):
        return [g.copy() for g in self.goals_data["goals"] if g["status"] == "active"]

    def get_all_goals(self):
        return [g.copy() for g in self.goals_data["goals"]]

class ContextEngine:
    """User activity, idle detection, and pattern learning."""
    def __init__(self, log_path="memory/activity_log.json"):
        self.log_path = log_path
        self.last_activity = time.time()
        self.entries = self._load()

    def _load(self):
        if os.path.exists(self.log_path):
            with open(self.log_path, 'r') as f: return json.load(f)
        return []

    def log_activity(self, input_text: str, trace_id: str, intent: str):
        self.entries.append({"timestamp": datetime.now().isoformat(), "trace": trace_id, "input": input_text, "intent": intent})
        if len(self.entries) > 1000: self.entries = self.entries[-1000:]
        self.last_activity = time.time()
        with open(self.log_path, 'w') as f: json.dump(self.entries, f, indent=2)

    def check_idle(self, threshold=30): return (time.time() - self.last_activity) > threshold

    def get_context(self): return {"recent": self.entries[-5:], "is_idle": self.check_idle()}

class ConversationManager:
    """Episodic memory for chat turns."""
    def __init__(self, storage_path="memory/episodic.json"):
        self.storage_path = storage_path
        self.history = self._load()

    def _load(self):
        if os.path.exists(self.storage_path):
            with open(self.storage_path, 'r') as f: return json.load(f)
        return []

    def add_turn(self, user_msg: str, bot_msg: str, llm_ref=None):
        self.history.append({"ts": time.time(), "user": user_msg, "bot": bot_msg})
        with open(self.storage_path, 'w') as f: json.dump(self.history, f, indent=2)

    def get_recent_context(self) -> str:
        if not self.history: return ""
        recent = self.history[-3:]
        return "\n".join([f"User: {t['user']}\nJARVIS: {t['bot']}" for t in recent])
