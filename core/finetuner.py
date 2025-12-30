import logging
import time
import os
import json
from typing import Dict

class OfflineEvolution:
    """
    Phase 4: Offline Evolution (Staging).
    Handles non-blocking model updates, weight fine-tuning simulations,
    and uncertainty calibration.
    """
    def __init__(self, brain_ref, storage_path="memory/stability_metrics.json"):
        self.brain = brain_ref
        self.storage_path = storage_path
        self.logger = logging.getLogger("OfflineEvolution")
        self.is_running = False
        self.metrics = self._load_metrics()

    def _load_metrics(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    return json.load(f)
            except Exception:
                return {"strategy_stats": {}, "confidence_history": []}
        return {"strategy_stats": {}, "confidence_history": []}

    def record_confidence(self, score):
        self.metrics["confidence_history"].append((time.time(), score))
        if len(self.metrics["confidence_history"]) > 100:
            self.metrics["confidence_history"].pop(0)

    def record_strategy(self, name):
        self.metrics["strategy_stats"][name] = self.metrics["strategy_stats"].get(name, 0) + 1

    def pulse(self, ledger_entries: list):
        """
        Phase 4: Feedback-Driven Self-Improvement.
        Analyzes Action Ledger for clusters of failures and distills lessons.
        """
        if self.is_running: return
        self.is_running = True
        
        self.logger.info("[Evolution] Commencing cognitive postmortem...")
        
        # 1. Success Rate Analysis
        if not ledger_entries:
            self.is_running = False
            return
            
        recent_entries = ledger_entries[-20:] # Analyze last 20 actions
        failures = [e for e in recent_entries if e["outcome"] == "failure"]
        
        failure_rate = len(failures) / len(recent_entries)
        self.metrics["failure_rate_trend"] = failure_rate
        
        # 2. Pattern Matching (Simplistic)
        failed_tasks = [e.get("context", "") for e in failures]
        
        # 3. Lesson Distillation
        if failure_rate > 0.3:
            self.logger.warning(f"[Evolution] High failure rate detected ({failure_rate:.2f}). Adjusting confidence threshold.")
            # Action: Save a lesson to memory
            lesson = {
                "timestamp": time.time(),
                "observation": f"Recent failure rate is {failure_rate:.2f}",
                "lesson": "Increase caution for similar tasks. Require higher confidence.",
                "affected_tasks": list(set(failed_tasks[:5]))
            }
            self._save_lesson(lesson)
            
        self.is_running = False
        self._save()

    def _save_lesson(self, lesson: dict):
        path = "memory/lessons_learned.json"
        lessons = []
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    lessons = json.load(f)
            except: pass
        
        lessons.append(lesson)
        with open(path, 'w') as f:
            json.dump(lessons, f, indent=2)

    def _save(self):
        with open(self.storage_path, 'w') as f:
            json.dump(self.metrics, f, indent=2)
