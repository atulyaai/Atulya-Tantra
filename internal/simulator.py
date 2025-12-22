import time
import uuid

class StimulusInjector:
    """
    Simulates external sensor signals for Phase 0.5 verification.
    No hardware dependency.
    """
    def __init__(self):
        self.signal_buffer = []

    def inject(self, sensor_class, stimulus, interrupt=False):
        """
        Injects a synthetic signal into the buffer.
        """
        priority = 10 if interrupt else 5
        if sensor_class == "SYSTEM_TIMER":
            priority = 1
            
        signal = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": time.time(),
            "sensor": sensor_class,
            "stimulus": stimulus,
            "priority": priority,
            "policy": "INTERRUPT" if interrupt else "BUFFER"
        }
        self.signal_buffer.append(signal)
        return signal

    def get_signals(self):
        """
        Retrieves and clears the current signal buffer.
        """
        signals = sorted(self.signal_buffer, key=lambda x: x['priority'], reverse=True)
        self.signal_buffer = []
        return signals
