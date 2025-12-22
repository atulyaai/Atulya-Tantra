from internal.simulator import StimulusInjector

class SystemSensor:
    """
    Phase 1.0B: System/Simulation Sensor Wrapper.
    Bridges the Phase 0.5 Simulator into the Phase 1.0B Orchestrator.
    """
    def __init__(self, manifest):
        self.manifest = manifest
        self.simulator = StimulusInjector()

    def capture(self):
        """
        Pulls signals from the simulator and normalizes them.
        """
        signals = self.simulator.get_signals()
        if not signals:
            return None
            
        # ADR-007: Return only the first valid one per poll to maintain fairness
        # The orchestrator will call again.
        raw = signals[0]
        stimulus = self.manifest.normalize("SYSTEM", raw["stimulus"], is_interrupt=(raw["priority"] >= 10))
        return stimulus

    def inject_noise(self, text, interrupt=False):
        self.simulator.inject("SYSTEM_TIMER", text, interrupt=interrupt)
