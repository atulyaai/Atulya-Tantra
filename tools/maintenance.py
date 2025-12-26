import os
import time
import logging
from datetime import datetime, timedelta

class MaintenanceTool:
    """
    Phase F: Enhanced maintenance with automated cleanup.
    Runs log rotation, metric pruning, and memory optimization.
    """
    def __init__(self):
        self.logger = logging.getLogger("Maintenance")
        self.last_cleanup = None
        
    def perform(self):
        """Run all maintenance tasks."""
        self._rotate_logs()
        self._prune_metrics()
        self._cleanup_temp_files()
        self.last_cleanup = datetime.now()
        
    def _rotate_logs(self):
        """Rotate logs if they exceed size limit."""
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            return
            
        max_size_mb = 10
        for log_file in os.listdir(log_dir):
            if not log_file.endswith('.log'):
                continue
                
            path = os.path.join(log_dir, log_file)
            size_mb = os.path.getsize(path) / (1024 * 1024)
            
            if size_mb > max_size_mb:
                # Rotate: rename to .old and create new
                old_path = path + ".old"
                if os.path.exists(old_path):
                    os.remove(old_path)
                os.rename(path, old_path)
                self.logger.info(f"Rotated log: {log_file} ({size_mb:.1f}MB)")
    
    def _prune_metrics(self):
        """Prune old metric entries to prevent unbounded growth."""
        metrics_dir = "memory"
        if not os.path.exists(metrics_dir):
            return
            
        # Keep only last 1000 entries in strategy_stats
        strategy_file = os.path.join(metrics_dir, "strategy_stats.json")
        if os.path.exists(strategy_file):
            import json
            try:
                with open(strategy_file, 'r') as f:
                    data = json.load(f)
                
                # Prune if too large
                if isinstance(data, list) and len(data) > 1000:
                    data = data[-1000:]
                    with open(strategy_file, 'w') as f:
                        json.dump(data, f, indent=2)
                    self.logger.info(f"Pruned strategy_stats to 1000 entries")
            except Exception as e:
                self.logger.warning(f"Failed to prune metrics: {str(e)}")
    
    def _cleanup_temp_files(self):
        """Remove temporary test files."""
        temp_patterns = [
            "memory/test_*.json",
            "logs/*.old.old"  # Double-rotated logs
        ]
        
        for pattern in temp_patterns:
            import glob
            for file_path in glob.glob(pattern):
                try:
                    os.remove(file_path)
                    self.logger.info(f"Cleaned up: {file_path}")
                except Exception as e:
                    self.logger.warning(f"Failed to clean {file_path}: {str(e)}")
    
    def should_run_cleanup(self, interval_hours=24):
        """Check if cleanup should run based on interval."""
        if self.last_cleanup is None:
            return True
        
        elapsed = datetime.now() - self.last_cleanup
        return elapsed > timedelta(hours=interval_hours)
    
    def schedule_cleanup(self, interval_hours=24):
        """Run cleanup if interval has passed."""
        if self.should_run_cleanup(interval_hours):
            self.logger.info("[Maintenance] Running scheduled cleanup...")
            self.perform()
            return True
        return False
