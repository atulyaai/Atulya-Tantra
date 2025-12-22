import os
import shutil
from datetime import datetime

class MaintenanceTool:
    def __init__(self, base_path="."):
        self.base_path = base_path

    def perform(self):
        """Executes all maintenance tasks."""
        self.rotate_logs()
        self.prune_metrics()

    def rotate_logs(self, log_file="logs/system.log", archive_dir="logs/archived", max_size_mb=1):
        log_path = os.path.join(self.base_path, log_file)
        archive_path = os.path.join(self.base_path, archive_dir)
        
        if os.path.exists(log_path) and os.path.getsize(log_path) > max_size_mb * 1024 * 1024:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.move(log_path, os.path.join(archive_path, f"system_{timestamp}.log"))
            print(f"[MAINTENANCE] Log rotated to {archive_dir}")

    def prune_metrics(self, metrics_dir="metrics", archive_dir="metrics/archived", keep_last=10):
        metrics_path = os.path.join(self.base_path, metrics_dir)
        archive_path = os.path.join(self.base_path, archive_dir)
        
        if not os.path.exists(metrics_path):
            return

        files = [f for f in os.listdir(metrics_path) if f.startswith("run_") and f.endswith(".json")]
        # Sort by run number
        try:
            files.sort(key=lambda x: int(x.split('_')[1].split('.')[0]))
        except (IndexError, ValueError):
            files.sort()

        if len(files) > keep_last:
            to_archive = files[:-keep_last]
            for f in to_archive:
                shutil.move(os.path.join(metrics_path, f), os.path.join(archive_path, f))
            print(f"[MAINTENANCE] Archived {len(to_archive)} old metrics.")
