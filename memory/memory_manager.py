import json
import os
import logging
from datetime import datetime

class MemoryManager:
    def __init__(self, base_path="memory"):
        self.base_path = base_path
        self.ensure_dirs()
        self.working = {}
        self.episodic_path = os.path.join(base_path, "episodic.json")
        self.procedural_path = os.path.join(base_path, "procedural.json")
        self.principle_path = os.path.join(base_path, "principles.json")
        self.strategy_path = os.path.join(base_path, "strategy_stats.json")
        self.trace_id = "INIT"
        self.logger = logging.getLogger("AtulyaMemory")
        
        # Initialize file-based memory if not exists
        for path in [self.episodic_path, self.procedural_path, self.strategy_path]:
            if not os.path.exists(path):
                default_data = [] if "stats" not in path else {
                    "SIMPLE": {"wins": 0, "runs": 0, "avg_score": 0.0},
                    "ANALYTICAL": {"wins": 0, "runs": 0, "avg_score": 0.0},
                    "THOROUGH": {"wins": 0, "runs": 0, "avg_score": 0.0},
                    "history": []
                }
                self.save_json(path, default_data)
        
        if not os.path.exists(self.principle_path):
            self.save_json(self.principle_path, {
                "rules": [
                    "Do not modify core code",
                    "No unauthorized file deletions",
                    "Verify results before finishing"
                ]
            })

    def set_trace_id(self, trace_id):
        self.trace_id = trace_id

    def log_transition(self, memory_type, action, details):
        extra = {'trace_id': self.trace_id}
        self.logger.info(f"MemoryTransition: [{memory_type}] {action} - {details}", extra=extra)

    def ensure_dirs(self):
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)

    def save_json(self, path, data):
        with open(path, 'w') as f:
            json.dump(data, f, indent=4)
        self.log_transition("FILE", "SAVE", f"Persisted to {path}")

    def load_json(self, path):
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
        return None

    def update_working(self, key, value):
        self.working[key] = value
        self.log_transition("WORKING", "UPDATE", f"{key} = {value}")

    def add_episodic(self, task, actions, result):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "task": task,
            "actions": actions,
            "result": result
        }
        history = self.load_json(self.episodic_path)
        history.append(entry)
        self.save_json(self.episodic_path, history)
        self.log_transition("EPISODIC", "ADD", f"New entry for task: {task[:50]}...")

    def add_procedural(self, intent, signature, actions, success, trace_id):
        # v1 Learning: Record what works and what doesn't
        entry = {
            "intent": intent,
            "signature": signature.lower().strip(),
            "actions": actions,
            "outcome": "success" if success else "failure",
            "trace_id": trace_id,
            "timestamp": datetime.now().isoformat()
        }
        procedures = self.load_json(self.procedural_path)
        # Avoid exact duplicates, overwrite with latest outcome
        updated = False
        for i, p in enumerate(procedures):
            if p["signature"] == entry["signature"] and p["intent"] == entry["intent"]:
                procedures[i] = entry
                updated = True
                break
        if not updated:
            procedures.append(entry)
        
        self.save_json(self.procedural_path, procedures)
        self.log_transition("PROCEDURAL", "LEARN", f"Recorded {entry['outcome']} for {signature[:30]}...")

    def get_procedural_guidance(self, intent, signature):
        # v1 Learning: Retrieve known patterns
        procedures = self.load_json(self.procedural_path)
        sig = signature.lower().strip()
        
        # Priority: Success patterns
        for p in procedures:
            if p["signature"] == sig and p["intent"] == intent and p["outcome"] == "success":
                return p["actions"], "SUCCESS_RECALL"
        
        # Avoid patterns
        for p in procedures:
            if p["signature"] == sig and p["intent"] == intent and p["outcome"] == "failure":
                return p["actions"], "FAILURE_AVOID"
                
        return None, "NO_PATTERN"

    def get_principles(self):
        return self.load_json(self.principle_path).get("rules", [])

    def get_strategy_stats(self):
        return self.load_json(self.strategy_path)

    def update_strategy_stats(self, strategy_name, score, won):
        stats = self.get_strategy_stats()
        if strategy_name in stats:
            s = stats[strategy_name]
            s["runs"] += 1
            if won:
                s["wins"] += 1
            # Rolling average
            s["avg_score"] = (s["avg_score"] * (s["runs"] - 1) + score) / s["runs"]
            
            # Record run history for plateau detection
            stats["history"].append({
                "run_at": datetime.now().isoformat(),
                "strategy": strategy_name,
                "score": score,
                "won": won
            })
            # Keep history manageable
            if len(stats["history"]) > 50:
                stats["history"].pop(0)
                
            self.save_json(self.strategy_path, stats)
            self.log_transition("STRATEGY", "UPDATE", f"{strategy_name} score={score:.2f} won={won}")
