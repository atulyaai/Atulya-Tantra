"""
Phase J1: Context Engine
Tracks user activity, detects idle periods, and enables context-aware suggestions.

Architecture:
- ActivityLog: Persistent storage of user inputs with timestamps
- IdleDetector: Monitors time since last activity
- PatternLearner: Identifies frequent commands/topics
- PreferenceModel: Learns from user approvals
- ContextEngine: Orchestrates all components
"""

import time
import json
import os
from datetime import datetime
from typing import List, Dict, Optional


class ActivityLog:
    """
    Persistent activity logger with automatic rotation.
    Follows same pattern as GoalManager for reliability.
    """
    
    def __init__(self, log_path: str = "memory/activity_log.json", max_entries: int = 1000):
        self.log_path = log_path
        self.max_entries = max_entries
        self.entries: List[Dict] = []
        self._ensure_file_exists()
        self.load()
    
    def _ensure_file_exists(self):
        """Create log file if it doesn't exist"""
        if not os.path.exists(self.log_path):
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            self._save_to_disk({"version": "1.0", "activities": []})
    
    def load(self):
        """Load activity log from disk"""
        try:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.entries = data.get("activities", [])
        except (json.JSONDecodeError, FileNotFoundError):
            # Corruption recovery: start fresh
            self.entries = []
            self.save()
    
    def log(self, input_text: str, trace_id: str, intent: str, duration_ms: int = 0):
        """
        Record user activity.
        
        Args:
            input_text: User's input
            trace_id: Unique trace identifier
            intent: Classified intent (e.g., INFORMATION_SEARCH)
            duration_ms: Processing time in milliseconds
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "trace_id": trace_id,
            "input": input_text,
            "intent": intent,
            "duration_ms": duration_ms
        }
        self.entries.append(entry)
        
        # Auto-rotate if exceeds max
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]
        
        self.save()
    
    def save(self):
        """Atomic write to disk"""
        data = {
            "version": "1.0",
            "activities": self.entries
        }
        self._save_to_disk(data)
    
    def _save_to_disk(self, data: dict):
        """Atomic write with temp file"""
        temp_path = self.log_path + ".tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Atomic rename
        if os.path.exists(self.log_path):
            os.replace(temp_path, self.log_path)
        else:
            os.rename(temp_path, self.log_path)
    
    def get_recent(self, n: int = 10) -> List[Dict]:
        """Get N most recent activities"""
        return self.entries[-n:] if self.entries else []
    
    def get_by_timerange(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """Get activities within time range"""
        return [
            entry for entry in self.entries
            if start_time <= datetime.fromisoformat(entry["timestamp"]) <= end_time
        ]
    
    def count(self) -> int:
        """Total activity count"""
        return len(self.entries)


class IdleDetector:
    """
    Detects when user is idle (no activity for threshold seconds).
    Thread-safe, minimal overhead.
    """
    
    def __init__(self, threshold: int = 30):
        self.threshold = threshold
        self.last_activity = time.time()
    
    def reset(self):
        """Mark activity (user did something)"""
        self.last_activity = time.time()
    
    def is_idle(self) -> bool:
        """Check if user is currently idle"""
        return self.idle_duration() > self.threshold
    
    def idle_duration(self) -> float:
        """Seconds since last activity"""
        return time.time() - self.last_activity
    
    def time_until_idle(self) -> float:
        """Seconds remaining until idle threshold"""
        remaining = self.threshold - self.idle_duration()
        return max(0, remaining)


class PatternLearner:
    """
    Identifies patterns in user activity.
    Detects frequent commands, topics, and time-of-day preferences.
    """
    
    def __init__(self):
        self.command_counts: Dict[str, int] = {}
        self.topic_counts: Dict[str, int] = {}
    
    def learn_from_activity(self, activity_log: ActivityLog):
        """Analyze activity log for patterns"""
        self.command_counts.clear()
        self.topic_counts.clear()
        
        for entry in activity_log.entries:
            # Count intents (proxy for commands)
            intent = entry.get("intent", "UNKNOWN")
            self.command_counts[intent] = self.command_counts.get(intent, 0) + 1
            
            # Extract topics from input (simple keyword extraction)
            words = entry.get("input", "").lower().split()
            for word in words:
                if len(word) > 4:  # Only meaningful words
                    self.topic_counts[word] = self.topic_counts.get(word, 0) + 1
    
    def get_frequent_commands(self, top_n: int = 10) -> List[tuple]:
        """Get most frequent command types"""
        sorted_cmds = sorted(self.command_counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_cmds[:top_n]
    
    def get_frequent_topics(self, top_n: int = 10) -> List[tuple]:
        """Get most frequent topics"""
        sorted_topics = sorted(self.topic_counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_topics[:top_n]


class PreferenceModel:
    """
    Learns user preferences from approvals/rejections.
    Stores in memory/user_preferences.json
    """
    
    def __init__(self, pref_path: str = "memory/user_preferences.json"):
        self.pref_path = pref_path
        self.preferences = {
            "frequent_topics": [],
            "preferred_actions": {},
            "idle_threshold": 30,
            "active_hours": []
        }
        self._ensure_file_exists()
        self.load()
    
    def _ensure_file_exists(self):
        """Create preferences file if missing"""
        if not os.path.exists(self.pref_path):
            os.makedirs(os.path.dirname(self.pref_path), exist_ok=True)
            self.save()
    
    def load(self):
        """Load preferences from disk"""
        try:
            with open(self.pref_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.preferences = data.get("preferences", self.preferences)
        except (json.JSONDecodeError, FileNotFoundError):
            self.save()
    
    def save(self):
        """Save preferences to disk"""
        data = {
            "version": "1.0",
            "preferences": self.preferences
        }
        with open(self.pref_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def update_action_preference(self, action: str, approved: bool):
        """Update preference score for an action"""
        current = self.preferences["preferred_actions"].get(action, 0.5)
        
        # Simple learning rate
        if approved:
            new_score = min(1.0, current + 0.1)
        else:
            new_score = max(0.0, current - 0.1)
        
        self.preferences["preferred_actions"][action] = new_score
        self.save()
    
    def get_action_score(self, action: str) -> float:
        """Get preference score for action (0.0 - 1.0)"""
        return self.preferences["preferred_actions"].get(action, 0.5)


class ContextEngine:
    """
    Central context awareness system.
    Orchestrates activity logging, idle detection, and pattern learning.
    """
    
    def __init__(self, 
                 activity_log_path: str = "memory/activity_log.json",
                 pref_path: str = "memory/user_preferences.json"):
        self.activity_log = ActivityLog(activity_log_path)
        self.idle_detector = IdleDetector(threshold=30)
        self.pattern_learner = PatternLearner()
        self.preference_model = PreferenceModel(pref_path)
    
    def log_activity(self, input_text: str, trace_id: str, intent: str, duration_ms: int = 0):
        """
        Record user activity and reset idle timer.
        
        This should be called from Engine.run_task() for every user input.
        """
        self.activity_log.log(input_text, trace_id, intent, duration_ms)
        self.idle_detector.reset()
    
    def check_idle(self) -> bool:
        """Check if user is currently idle"""
        return self.idle_detector.is_idle()
    
    def get_context(self) -> Dict:
        """
        Get current user context for suggestion generation.
        
        Returns:
            Dict with recent activity, patterns, and preferences
        """
        # Update patterns from recent activity
        self.pattern_learner.learn_from_activity(self.activity_log)
        
        return {
            "recent_activities": self.activity_log.get_recent(5),
            "frequent_commands": self.pattern_learner.get_frequent_commands(5),
            "frequent_topics": self.pattern_learner.get_frequent_topics(5),
            "idle_duration": self.idle_detector.idle_duration(),
            "is_idle": self.idle_detector.is_idle(),
            "total_activities": self.activity_log.count()
        }
    
    def learn_from_approval(self, action: str, approved: bool):
        """Update preference model based on user approval"""
        self.preference_model.update_action_preference(action, approved)
