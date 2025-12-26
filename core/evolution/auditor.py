import json
import time
import os
import logging

class DriftAuditor:
    """
    Phase E1: Long-Run Stability & Drift Audit.
    Tracks system behavior over time without changing core logic.
    Identifies if the system is drifting from its baseline performance.
    """
    def __init__(self, storage_path="memory/stability_metrics.json"):
        self.storage_path = storage_path
        self.logger = logging.getLogger("DriftAuditor")
        self.metrics = self._load_metrics()

    def _load_metrics(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    return json.load(f)
            except Exception:
                return self._get_default_metrics()
        return self._get_default_metrics()

    def _get_default_metrics(self):
        return {
            "confidence_history": [], # [(timestamp, calib_score)]
            "strategy_stats": {
                "SIMPLE": 0,
                "ANALYTICAL": 0,
                "CRITICAL": 0
            },
            "knowledge_staleness": {
                "total_facts": 0,
                "stale_facts": 0
            },
            "last_audit": time.time()
        }

    def record_confidence_event(self, calib_score):
        """Audit Tracker: Tracks drift in self-awareness."""
        self.metrics["confidence_history"].append((time.time(), calib_score))
        # Keep last 100 events
        if len(self.metrics["confidence_history"]) > 100:
            self.metrics["confidence_history"].pop(0)

    def record_strategy_use(self, strategy_name):
        """Audit Tracker: Tracks shifts in effort-allocation bias."""
        if strategy_name in self.metrics["strategy_stats"]:
            self.metrics["strategy_stats"][strategy_name] += 1

    def audit_knowledge_base(self, knowledge_brain):
        """Audit Tracker: Identifies knowledge staleness without auto-updating."""
        all_topics = knowledge_brain.get_all_topics()
        total = 0
        stale = 0
        now = time.time()
        
        for topic in all_topics:
            facts = knowledge_brain.get_topic_facts(topic)
            total += len(facts)
            for fact in facts:
                # Assuming fact has a 'timestamp' and 'ttl'
                if now - fact.get('timestamp', 0) > fact.get('ttl', 3600*24):
                    stale += 1
                    
        self.metrics["knowledge_staleness"] = {
            "total_facts": total,
            "stale_facts": stale
        }

    def save(self):
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.metrics, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save metrics: {str(e)}")

    def get_summary(self):
        """Provides the baseline reality check."""
        total_strategies = sum(self.metrics["strategy_stats"].values()) or 1
        return {
            "stability_score": self._calculate_stability(),
            "dominance": {k: v/total_strategies for k, v in self.metrics["strategy_stats"].items()},
            "staleness_ratio": self.metrics["knowledge_staleness"]["stale_facts"] / (self.metrics["knowledge_staleness"]["total_facts"] or 1)
        }

    def _calculate_stability(self):
        # Placeholder for complex stability math
        # If confidence events oscillate too much, stability is low.
        if not self.metrics["confidence_history"]:
            return 1.0
        return 1.0 # Baseline for now
    
    def audit_knowledge_staleness(self, knowledge_brain=None):
        """
        Phase E: Audit knowledge staleness and log metrics.
        Can be called with or without knowledge_brain reference.
        """
        if knowledge_brain:
            self.audit_knowledge_base(knowledge_brain)
        
        staleness_ratio = self.metrics["knowledge_staleness"]["stale_facts"] / (self.metrics["knowledge_staleness"]["total_facts"] or 1)
        
        self.logger.info(
            f"[Staleness Audit] Total: {self.metrics['knowledge_staleness']['total_facts']}, "
            f"Stale: {self.metrics['knowledge_staleness']['stale_facts']}, "
            f"Ratio: {staleness_ratio:.2%}"
        )
        
        self.save()
        return staleness_ratio
