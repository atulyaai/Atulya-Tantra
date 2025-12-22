import time
import logging

class LocalTranscriber:
    """
    ADR-008: Local Transcription Interface.
    In Phase 1.0C-PTT, this serves as the local STT bridge.
    """
    def __init__(self, confidence_floor=0.5):
        self.confidence_floor = confidence_floor
        self.presence_logger = logging.getLogger("PresenceAudit")

    def transcribe(self, audio_data=None):
        """
        Mock transcription for architectural verification.
        Returns (text, confidence).
        In 1.0C-PTT deployment, this calls Whisper-v3-Turbo locally.
        """
        if not audio_data:
            return None, 0.0
            
        # Simulation: Join fragments if it's a list (simulating stream assembly)
        if isinstance(audio_data, list):
            text = " ".join(audio_data)
        else:
            text = str(audio_data)
            
        return text, 1.0 

class VoiceSensor:
    """
    Phase 1.0C-PTT: Bounded Voice Driver.
    Captures windowed audio episodes under Push-To-Talk discipline.
    """
    def __init__(self, manifest, transcriber):
        self.manifest = manifest
        self.transcriber = transcriber
        self.is_capturing = False
        self.capture_start_time = 0
        self.current_buffer = None
        self.presence_logger = logging.getLogger("PresenceAudit")

    def start_ptt(self):
        """Opens the mic window."""
        self.is_capturing = True
        self.capture_start_time = time.time()
        self.current_buffer = [] # Ephemeral buffer
        self.presence_logger.info("Voice: PTT Active (Mic Open)")

    def stop_ptt(self):
        """Closes the mic window and returns normalized stimulus."""
        if not self.is_capturing:
            return None
            
        self.is_capturing = False
        duration = time.time() - self.capture_start_time
        self.presence_logger.info(f"Voice: PTT Inactive (Duration: {duration:.2f}s)")
        
        # ADR-008: Episode Cap (10s)
        if duration > 10.0:
            self.presence_logger.warning("Voice: Episode truncated (Budget Exceeded)")
            
        # ADR-008: Transcription
        text, confidence = self.transcriber.transcribe(self.current_buffer)
        self.current_buffer = None # ADR-008: Privacy (Clear raw data immediately)
        
        if not text or confidence < self.transcriber.confidence_floor:
            return None
            
        # ADR-006: Normalization Invariant
        stimulus = self.manifest.normalize("VOICE", text, is_interrupt=False)
        return stimulus

    def record(self, data):
        """ADR-008: Appends data to the ephemeral episode buffer."""
        if self.is_capturing:
            if isinstance(self.current_buffer, list):
                self.current_buffer.append(data)
            else:
                self.current_buffer = [data]

    def capture(self):
        """
        Non-blocking capture for SensorOrchestrator.
        In PTT mode, this only returns data if PTT was just stopped.
        """
        # For Phase 1.0C-PTT, the Orchestrator polls this.
        # However, PTT is user-triggered. 
        # We handle the state externally and this returns the result.
        return None 

    def inject_voice(self, text):
        """Simulation injection for PTT testing."""
        self.is_capturing = True
        self.current_buffer = text
        return self.stop_ptt()
