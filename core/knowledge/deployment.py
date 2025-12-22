import os
import shutil
import logging

class WeightDeploymentManager:
    """
    Phase K3-D: Weight Promotion & Rollback.
    The sacred gate between offline training and the active kernel.
    """
    def __init__(self, active_weight_dir, archive_dir):
        self.active_dir = active_weight_dir
        self.archive_dir = archive_dir
        self.logger = logging.getLogger("DeploymentManager")
        
        os.makedirs(self.active_dir, exist_ok=True)
        os.makedirs(self.archive_dir, exist_ok=True)

    def promote_weights(self, new_weight_path, eval_report):
        """
        Final safety gate. Only promotes if thresholds are met.
        """
        # Thresholds defined in ADR-011
        fidelity_min = 0.8
        calibration_min = 0.7
        
        report_fidelity = eval_report.get('fidelity', 0.0)
        report_calibration = eval_report.get('calibration', 0.0)
        
        if report_fidelity < fidelity_min or report_calibration < calibration_min:
            self.logger.error("WEIGHT PROMOTION REJECTED: Eval thresholds not met.")
            return False
            
        # 1. Rollback Snapshot
        self._create_rollback_snapshot()
        
        # 2. Deploy
        target_path = os.path.join(self.active_dir, "core_lm.bin")
        shutil.copy(new_weight_path, target_path)
        self.logger.info(f"WEIGHT PROMOTION SUCCESS: Deployed to {target_path}")
        return True

    def rollback(self):
        """Emergency restoration of previous known-good state."""
        snapshot = os.path.join(self.archive_dir, "rollback_v_last.bin")
        if os.path.exists(snapshot):
            shutil.copy(snapshot, os.path.join(self.active_dir, "core_lm.bin"))
            self.logger.warning("ROLLBACK COMPLETE: Restored previous safe-point.")
        else:
            self.logger.error("ROLLBACK FAILED: No snapshot found.")

    def _create_rollback_snapshot(self):
        active = os.path.join(self.active_dir, "core_lm.bin")
        if os.path.exists(active):
            shutil.copy(active, os.path.join(self.archive_dir, "rollback_v_last.bin"))
