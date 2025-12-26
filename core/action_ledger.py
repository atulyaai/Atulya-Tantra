import json
import logging
import os
import time
import uuid
import shutil
from pathlib import Path
from core.governor import Governor # Access TraceID via logging adapter context if needed, but we pass trace_id explicitly.

logger = logging.getLogger("ActionLedger")

class ActionLedger:
    """
    Persistent, append-only ledger of action outcomes.
    Serves as a trust anchor for planning.
    Passive: Records only, never triggers actions.
    """
    def __init__(self, storage_path="memory/action_ledger.json"):
        self.storage_path = storage_path
        self.entries = []
        self._load()

    def record_outcome(self, action_type: str, outcome: str, context: str = None, confidence: float = None, trace_id: str = "GLOBAL"):
        """
        Records an action outcome.
        Args:
            action_type: Type of action (e.g. "search", "write_file")
            outcome: "success" | "failure" | "partial"
            context: Short description (max 256 chars)
            confidence: Float 0-1 (optional)
            trace_id: Trace ID for correlation
        """
        entry = {
            "action_id": str(uuid.uuid4()),
            "action_type": action_type,
            "outcome": outcome,
            "context": context[:256] if context else None,
            "confidence": confidence,
            "timestamp": time.time(),
            "trace_id": trace_id
        }
        
        self.entries.append(entry)
        
        # Log visible confirmation
        log_msg = f"[LEDGER][{trace_id}] Recorded {action_type} -> {outcome}"
        logger.info(log_msg)
        print(log_msg) # Visible console feedback
        
        self._save()

    def get_success_rate(self, action_type: str) -> float:
        """
        Calculates success rate for a given action type.
        Returns 0.0 if no history.
        """
        relevant = [e for e in self.entries if e["action_type"] == action_type]
        if not relevant:
            return 0.0
        
        successes = len([e for e in relevant if e["outcome"] == "success"])
        return float(successes) / len(relevant)

    def _save(self):
        """Atomic write to storage."""
        data = {
            "version": "1.0",
            "entries": self.entries
        }
        
        try:
            # Atomic write: Write to temp -> Rename
            temp_path = self.storage_path + ".tmp"
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            os.replace(temp_path, self.storage_path)
        except Exception as e:
            logger.error(f"Failed to save ledger: {e}")

    def _load(self):
        """Loads ledger from storage with corruption recovery."""
        if not os.path.exists(self.storage_path):
            self.entries = []
            return

        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                
            if "entries" not in data or "version" not in data:
                raise ValueError("Invalid ledger schema")
                
            self.entries = data["entries"]
            logger.info(f"Loaded {len(self.entries)} ledger entries")
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Corrupted ledger detected ({e}). Backing up and resetting.")
            
            # Backup corrupted file
            if os.path.exists(self.storage_path):
                backup_path = self.storage_path + ".corrupted"
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                os.rename(self.storage_path, backup_path)
                logger.info(f"Corrupted ledger backed up to {backup_path}")
            
            self.entries = []
