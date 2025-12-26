import time
import logging
from core.sensors.vision_interface import VisionInterface

class VisionSensor:
    """
    Phase 1.0D: Discrete Vision Driver.
    PRODUCTION MODE: Real vision model (CLIP) for image understanding.
    Captures on-demand snapshots and converts them into semantic text.
    """
    def __init__(self, manifest, governor=None):
        self.manifest = manifest
        self.governor = governor
        # Need a reference to governor for getting trace_id via adapter
        from core.governor import TraceIDAdapter
        self.presence_logger = TraceIDAdapter(logging.getLogger("PresenceAudit"), self.governor)
        self.is_active = False
        
        # Phase C: Real vision interface (lazy loading)
        self.vision = VisionInterface(model_name="clip")  # Start with CLIP for speed
        self._vision_loaded = False

    def capture_snapshot(self, image_path=None):
        """
        Triggers a discrete capture event.
        ADR-012: No streaming, on-demand only.
        
        Args:
            image_path: Path to image file (for testing/production)
        """
        if not self.is_active:
            self.presence_logger.warning("Vision: Capture attempted while sensor is INACTIVE.")
            return None
            
        self.presence_logger.info("Vision: Capture Triggered (Discrete Snapshot)")
        
        # Lazy load vision model on first use
        if not self._vision_loaded:
            self.presence_logger.info("[Vision] First capture - loading vision model...")
            if not self.vision.load():
                self.presence_logger.error("[Vision] Vision model loading failed, falling back to simulation")
                # Fallback to safe simulation
                raw_description = "A desk with a computer monitor and a red notebook."
                stimulus = self.manifest.normalize("VISION", raw_description, is_interrupt=True)
                return stimulus
            self._vision_loaded = True
        
        # Real vision understanding
        if image_path:
            description, confidence, metadata = self.vision.understand(image_path)
            self.presence_logger.info(
                f"[Vision] Understanding: '{description[:50]}...', confidence={confidence:.3f}"
            )
            
            # ADR-012: Normalization to text stimulus
            stimulus = self.manifest.normalize("VISION", description, is_interrupt=True)
            return stimulus
        else:
            # Simulation mode for testing
            raw_description = "A desk with a computer monitor and a red notebook."
            stimulus = self.manifest.normalize("VISION", raw_description, is_interrupt=True)
            return stimulus

    def set_state(self, active=True):
        """Opt-in per session."""
        self.is_active = active
        self.presence_logger.info(f"Vision: State set to {'ACTIVE' if active else 'INACTIVE'}")

    def capture(self):
        """Non-blocking poll (No-op for Vision as it is PULL based)."""
        return None
