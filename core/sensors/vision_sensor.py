import time
import logging

class VisionSensor:
    """
    Phase 1.0D: Discrete Vision Driver.
    Captures on-demand snapshots and converts them into semantic text.
    """
    def __init__(self, manifest, governor=None):
        self.manifest = manifest
        self.governor = governor
        # Need a reference to governor for getting trace_id via adapter
        from core.governor import TraceIDAdapter
        self.presence_logger = TraceIDAdapter(logging.getLogger("PresenceAudit"), self.governor)
        self.is_active = False

    def capture_snapshot(self):
        """
        Triggers a discrete capture event.
        ADR-012: No streaming, on-demand only.
        """
        if not self.is_active:
            self.presence_logger.warning("Vision: Capture attempted while sensor is INACTIVE.")
            return None
            
        self.presence_logger.info("Vision: Capture Triggered (Discrete Snapshot)")
        
        # Simulation: Deterministic vision output for Tier A validation
        # In real-world, this runs a local VLM (e.g., Qwen-VL) snapshot.
        raw_description = "A desk with a computer monitor and a red notebook."
        
        # ADR-012: Normalization to text stimulus
        stimulus = self.manifest.normalize("VISION", raw_description, is_interrupt=True)
        return stimulus

    def set_state(self, active=True):
        """Opt-in per session."""
        self.is_active = active
        self.presence_logger.info(f"Vision: State set to {'ACTIVE' if active else 'INACTIVE'}")

    def capture(self):
        """Non-blocking poll (No-op for Vision as it is PULL based)."""
        return None
