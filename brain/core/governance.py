import logging
import os
import time
import uuid
import json
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("GovernanceOrgan")

class PolicyBrain:
    """Decision engine for autonomy and risk management."""
    def __init__(self):
        self.TIERS = {
            "OBSERVATION": {"risk": 0, "threshold": 0.0, "auto": True},
            "REVERSIBLE": {"risk": 1, "threshold": 0.6, "auto": True},
            "MUTATION": {"risk": 2, "threshold": 0.8, "auto": False},
            "IRREVERSIBLE": {"risk": 3, "threshold": 0.95, "auto": False}
        }

    def evaluate(self, action: str, context: Dict) -> Tuple[str, bool]:
        tier = self._classify_action(action)
        policy = self.TIERS[tier]
        confidence = context.get("confidence", 0.0)
        if confidence < policy["threshold"]: return "ASK", False
        return ("ALLOW", True) if policy["auto"] else ("ASK", False)

    def _classify_action(self, action: str) -> str:
        action = action.lower()
        if any(op in action for op in ["read", "list", "query"]): return "OBSERVATION"
        if any(op in action for op in ["delete", "remove", "overwrite"]): return "IRREVERSIBLE"
        if any(op in action for op in ["update", "modify", "edit"]): return "MUTATION"
        return "REVERSIBLE"

class Governor:
    """Safety and authorization layer."""
    def __init__(self):
        self.forbidden = ["rm -rf /", "format", "shutdown", "del /s /q C:\\"]
        self.protected_paths = ["core", "memory", "docs", "main.py"]
        self.policy_brain = PolicyBrain()
    def set_trace_id(self, trace_id):
        self.trace_id = trace_id

    def generate_trace_id(self):
        return f"T-{int(time.time()*1000)}"

    def authorize(self, action: str, context: Dict = None) -> bool:
        # 1. Broad Shell Prohibitions
        if any(f in action for f in self.forbidden): return False
        
        # 2. Path-Based Preservation (Constitutional Law)
        # Check if action targets a protected path
        action_lower = action.lower()
        if "delete" in action_lower or "remove" in action_lower or "write" in action_lower:
             if any(p in action_lower for p in self.protected_paths):
                 # Allow updates if explicitly authorized, but block destructive by default
                 if "delete" in action_lower or "remove" in action_lower:
                     return False # BLOCKED: Law of Preservation

        decision, is_auto = self.policy_brain.evaluate(action, context or {})
        return decision == "ALLOW"

    def check_permission(self, action: str) -> bool:
        return not any(f in action for f in self.forbidden)

class ActionLedger:
    """Persistent ledger of action outcomes."""
    def __init__(self, storage_path="memory/action_ledger.json"):
        self.storage_path = storage_path
        self.entries = self._load()

    def record_outcome(self, action_type: str, outcome: str, context: str = None, trace_id: str = "GLOBAL"):
        entry = {"id": str(uuid.uuid4())[:8], "type": action_type, "outcome": outcome, "context": context, "ts": time.time(), "trace": trace_id}
        self.entries.append(entry)
        self._save()

    def _save(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, 'w') as f: json.dump(self.entries, f, indent=2)

    def _load(self):
        if os.path.exists(self.storage_path):
            with open(self.storage_path, 'r') as f: return json.load(f)
        return []

    def get_success_rate(self, action_type: str) -> float:
        rel = [e for e in self.entries if e["type"] == action_type]
        if not rel: return 0.0
        return len([e for e in rel if e["outcome"] == "success"]) / len(rel)
