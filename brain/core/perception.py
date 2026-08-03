import logging
from core.sensors import SensorManifest, SensorOrchestrator, TextSensor, SystemSensor, VoiceSensor, LocalTranscriber, VisionSensor

logger = logging.getLogger("AtulyaPerception")

class PerceptionManager:
    """Handles sensor registration and signal collection."""
    def __init__(self, governor):
        self.manifest = SensorManifest()
        self.orchestrator = SensorOrchestrator(self.manifest)
        self.governor = governor
        
        # Register Sensors
        self.text_sensor = TextSensor(self.manifest)
        self.system_sensor = SystemSensor(self.manifest)
        
        # Voice
        self.transcriber = LocalTranscriber()
        self.voice_sensor = VoiceSensor(self.manifest, self.transcriber)
        
        # Vision
        self.vision_sensor = VisionSensor(self.manifest, self.governor)
        
        self.orchestrator.register_sensor("TEXT", self.text_sensor, poll_interval=0.1)
        self.orchestrator.register_sensor("SYSTEM", self.system_sensor, poll_interval=0.5)
        self.orchestrator.register_sensor("VOICE", self.voice_sensor, poll_interval=0.5)
        self.orchestrator.register_sensor("VISION", self.vision_sensor, poll_interval=1.0)

    def start(self):
        self.orchestrator.start()

    def stop(self):
        self.orchestrator.stop()

    def collect(self):
        return self.orchestrator.collect()

    def reset_cycle(self):
        self.manifest.reset_cycle()
