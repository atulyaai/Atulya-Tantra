import threading
import queue
import time
import logging

class SensorOrchestrator:
    """
    ADR-007 Concurrency Hub.
    Manages background sensor threads and centralizes stimulus collection.
    """
    def __init__(self, manifest):
        self.manifest = manifest
        self.stimulus_queue = queue.Queue(maxsize=100) # ADR-007: Buffer Backpressure
        self.sensors = {}
        self.running = False
        self.presence_logger = logging.getLogger("PresenceAudit")

    def register_sensor(self, name, sensor_instance, poll_interval=1.0):
        """
        Connects a sensor driver to the orchestrator.
        """
        self.sensors[name] = {
            "instance": sensor_instance,
            "thread": None,
            "poll_interval": poll_interval,
            "last_active": time.time(),
            "status": "READY"
        }

    def _sensor_loop(self, name):
        """
        Isolated background thread for each sensor.
        """
        config = self.sensors[name]
        sensor = config["instance"]
        
        while self.running:
            if self.manifest.get_config(name)["state"] == "IGNORED":
                time.sleep(config["poll_interval"])
                continue
                
            try:
                # Sensors must implement a non-blocking poll/capture
                stimulus = sensor.capture()
                if stimulus:
                    try:
                        self.stimulus_queue.put(stimulus, block=False)
                        config["last_active"] = time.time()
                    except queue.Full:
                        self.presence_logger.warning(f"[CONGESTION] Dropping signal from {name}")
                
                time.sleep(config["poll_interval"])
            except Exception as e:
                self.presence_logger.error(f"Sensor Error ({name}): {str(e)}")
                config["status"] = "ERROR"
                break

    def start(self):
        """
        Spins up background threads for all registered sensors.
        """
        self.running = True
        for name in self.sensors:
            thread = threading.Thread(target=self._sensor_loop, args=(name,), daemon=True)
            self.sensors[name]["thread"] = thread
            thread.start()
        self.presence_logger.info("Sensor Orchestrator Started.")

    def stop(self):
        self.running = False
        self.presence_logger.info("Sensor Orchestrator Stopped.")

    def collect(self):
        """
        Drains the stimulus queue into a list for the Presence Loop.
        """
        signals = []
        while not self.stimulus_queue.empty():
            signals.append(self.stimulus_queue.get())
        return signals
