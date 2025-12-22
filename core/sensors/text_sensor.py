import sys
import threading
import queue

class TextSensor:
    """
    Phase 1.0B: Async Terminal/STDIN Sensor.
    Uses a background worker to avoid blocking the Presence Loop.
    """
    def __init__(self, manifest):
        self.manifest = manifest
        self.input_queue = queue.Queue()
        self._start_listener()

    def _start_listener(self):
        def listen():
            while True:
                try:
                    line = sys.stdin.readline()
                    if line:
                        self.input_queue.put(line.strip())
                except EOFError:
                    break
        t = threading.Thread(target=listen, daemon=True)
        t.start()

    def capture(self):
        """
        Non-blocking capture for the SensorOrchestrator.
        """
        if self.input_queue.empty():
            return None
            
        raw_text = self.input_queue.get()
        if not raw_text:
            return None
            
        is_interrupt = raw_text.startswith("!")
        if is_interrupt:
            raw_text = raw_text[1:]
            
        # ADR-006: Normalization Invariant enforcement
        stimulus = self.manifest.normalize("TEXT", raw_text, is_interrupt=is_interrupt)
        return stimulus
