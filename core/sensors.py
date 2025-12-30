import time
import threading
import queue
import logging
import sys
import uuid
import math
from typing import Tuple, Dict, Optional, List
from pathlib import Path

logger = logging.getLogger("SensorOrgan")

class SensorManifest:
    """Central Registry for Sensor States."""
    def __init__(self):
        self.registry = {
            "TEXT": {"state": "BUFFER", "priority_base": 5, "quota": 2, "cycle_count": 0, "starvation": 0},
            "VOICE": {"state": "IGNORED", "priority_base": 5, "quota": 1, "cycle_count": 0, "starvation": 0},
            "VISION": {"state": "IGNORED", "priority_base": 5, "opt_in_required": True, "quota": 1, "cycle_count": 0, "starvation": 0},
            "SYSTEM": {"state": "BUFFER", "priority_base": 1, "quota": 5, "cycle_count": 0, "starvation": 0}
        }
        self.embodiment_active = True

    def reset_cycle(self):
        for name in self.registry:
            if self.registry[name]["cycle_count"] == 0:
                self.registry[name]["starvation"] += 1
            else:
                self.registry[name]["starvation"] = 0
            self.registry[name]["cycle_count"] = 0

    def get_config(self, sensor_name):
        return self.registry.get(sensor_name)

    def set_state(self, sensor_name, state):
        if sensor_name in self.registry:
            self.registry[sensor_name]["state"] = state

    def normalize(self, sensor_name, raw_stimulus, is_interrupt=False):
        if not self.embodiment_active: return None
        config = self.get_config(sensor_name)
        if not config or config["state"] == "IGNORED": return None
        if config["cycle_count"] >= config["quota"]: return None

        priority = 10 if is_interrupt else config["priority_base"]
        if config["starvation"] > 5 and priority < 10: priority += 1
        config["cycle_count"] += 1
        
        return {
            "id": f"S-{int(time.time()*1000)}",
            "timestamp": time.time(),
            "sensor": sensor_name,
            "stimulus": raw_stimulus,
            "priority": priority,
            "policy": "INTERRUPT" if is_interrupt else config["state"]
        }

class SensorOrchestrator:
    """Concurrency Hub for stimulus collection."""
    def __init__(self, manifest):
        self.manifest = manifest
        self.stimulus_queue = queue.Queue(maxsize=100)
        self.sensors = {}
        self.running = False

    def register_sensor(self, name, sensor_instance, poll_interval=1.0):
        self.sensors[name] = {"instance": sensor_instance, "thread": None, "poll_interval": poll_interval, "status": "READY"}

    def _sensor_loop(self, name):
        config = self.sensors[name]
        sensor = config["instance"]
        while self.running:
            if self.manifest.get_config(name)["state"] == "IGNORED":
                time.sleep(config["poll_interval"])
                continue
            try:
                stimulus = sensor.capture()
                if stimulus:
                    try: self.stimulus_queue.put(stimulus, block=False)
                    except queue.Full: pass
                time.sleep(config["poll_interval"])
            except Exception: break

    def start(self):
        self.running = True
        for name in self.sensors:
            thread = threading.Thread(target=self._sensor_loop, args=(name,), daemon=True)
            self.sensors[name]["thread"] = thread
            thread.start()

    def stop(self): self.running = False

    def collect(self):
        signals = []
        while not self.stimulus_queue.empty(): signals.append(self.stimulus_queue.get())
        return signals

class TextSensor:
    def __init__(self, manifest, input_stream=sys.stdin):
        self.manifest = manifest
        self.input_queue = queue.Queue()
        self.input_stream = input_stream
        self._running = True
        self._start_listener()

    def _start_listener(self):
        def listen():
            while self._running:
                try:
                    if hasattr(self.input_stream, 'readline'):
                        line = self.input_stream.readline()
                        if line: self.input_queue.put(line.strip())
                        else: time.sleep(0.1)
                except Exception: break
        threading.Thread(target=listen, daemon=True).start()

    def stop(self): self._running = False

    def capture(self):
        if self.input_queue.empty(): return None
        raw_text = self.input_queue.get()
        if not raw_text: return None
        raw_text = raw_text.replace('\x00', '')[:10000]
        if not raw_text.strip(): return None
        is_interrupt = raw_text.startswith("!")
        if is_interrupt: raw_text = raw_text[1:]
        return self.manifest.normalize("TEXT", raw_text, is_interrupt=is_interrupt)

class SystemSensor:
    def __init__(self, manifest): self.manifest = manifest
    def capture(self): return None
    def inject_event(self, event_type, data):
        return self.manifest.normalize("SYSTEM", f"{event_type}: {data}")

class VoiceSensor:
    def __init__(self, manifest, transcriber):
        self.manifest = manifest
        self.transcriber = transcriber
        self.is_capturing = False
        self.current_buffer = None

    def start_ptt(self):
        self.is_capturing = True
        self.current_buffer = []

    def stop_ptt(self):
        if not self.is_capturing: return None
        self.is_capturing = False
        text, confidence = self.transcriber.transcribe(self.current_buffer)
        self.current_buffer = None
        if not text: return None
        return self.manifest.normalize("VOICE", text, is_interrupt=False)

    def record(self, data):
        if self.is_capturing:
            if not isinstance(self.current_buffer, list): self.current_buffer = []
            self.current_buffer.append(data)

    def capture(self): return None

class LocalTranscriber:
    def __init__(self, confidence_floor=0.5): self.confidence_floor = confidence_floor
    def transcribe(self, audio_data=None):
        if not audio_data: return "", 0.0
        text = " ".join(str(d) for d in audio_data) if isinstance(audio_data, list) else str(audio_data)
        return (text.strip(), 1.0) if text.strip() else ("", 0.0)

class VisionSensor:
    def __init__(self, manifest, governor=None):
        self.manifest = manifest
        self.governor = governor
        self.is_active = False
        self._vision_loaded = False

    def capture_snapshot(self):
        if not self.is_active: return None
        # Simplified simulation to avoid complex dependencies in sensors.py
        return self.manifest.normalize("VISION", "Visual snapshot captured.", is_interrupt=True)

    def set_state(self, active=True): self.is_active = active
    def capture(self): return self.capture_snapshot()
