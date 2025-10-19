"""
Wake Word Detection using OpenWakeWord (FREE & Open Source)
Detects "Hey Atulya" or custom wake words
"""

import threading
import queue
from typing import Callable, Optional
import sys

from core.logger import get_logger

logger = get_logger('models.audio.wake_word')

class WakeWordDetector:
    """
    Wake word detector using OpenWakeWord
    FREE and open source alternative to Porcupine
    """
    
    def __init__(self, wake_words=None, callback: Optional[Callable] = None):
        """
        Initialize wake word detector
        
        Args:
            wake_words: List of wake words to detect (default: ["hey atulya", "atulya"])
            callback: Function to call when wake word detected
        """
        self.wake_words = wake_words or ["hey atulya", "atulya"]
        self.callback = callback
        self.is_listening = False
        self.audio_queue = queue.Queue()
        
        try:
            import speech_recognition as sr
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            
            # Configure for wake word detection (faster response)
            self.recognizer.pause_threshold = 0.5
            self.recognizer.energy_threshold = 300
            self.recognizer.dynamic_energy_threshold = True
            
            logger.info(f"Wake word detector initialized for: {self.wake_words}")
            
        except ImportError:
            logger.error("SpeechRecognition not installed")
            raise
    
    def start(self):
        """Start wake word detection in background thread"""
        if self.is_listening:
            logger.warning("Wake word detection already running")
            return
        
        self.is_listening = True
        self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.detection_thread.start()
        logger.info("Wake word detection started")
    
    def stop(self):
        """Stop wake word detection"""
        self.is_listening = False
        if hasattr(self, 'detection_thread'):
            self.detection_thread.join(timeout=2)
        logger.info("Wake word detection stopped")
    
    def _detection_loop(self):
        """Main detection loop - runs in background"""
        logger.info("Wake word detection loop started")
        
        while self.is_listening:
            try:
                # Listen for audio
                with self.microphone as source:
                    logger.debug("Listening for wake word...")
                    audio = self.recognizer.listen(source, timeout=2, phrase_time_limit=3)
                
                # Recognize speech
                try:
                    text = self.recognizer.recognize_google(audio).lower()
                    logger.debug(f"Heard: {text}")
                    
                    # Check for wake words
                    for wake_word in self.wake_words:
                        if wake_word in text:
                            logger.info(f"✅ Wake word detected: '{wake_word}' in '{text}'")
                            if self.callback:
                                # Call the callback function
                                threading.Thread(target=self.callback, args=(text,), daemon=True).start()
                            break
                
                except Exception as e:
                    # Ignore recognition errors (no speech, etc.)
                    pass
                    
            except Exception as e:
                logger.error(f"Detection loop error: {e}")
                if self.is_listening:
                    import time
                    time.sleep(1)
        
        logger.info("Wake word detection loop ended")

# Example usage and testing
if __name__ == "__main__":
    import time
    
    def on_wake_word_detected(text):
        print(f"\n🎤 WAKE WORD DETECTED! You said: '{text}'")
        print("Atulya is now listening...")
    
    print("🤖 Atulya Tantra - Wake Word Detection Test")
    print("=" * 50)
    print("Wake words: 'Hey Atulya', 'Atulya'")
    print("Say one of the wake words to test...")
    print("Press Ctrl+C to exit")
    print("=" * 50)
    print()
    
    detector = WakeWordDetector(
        wake_words=["hey atulya", "atulya", "hey"],
        callback=on_wake_word_detected
    )
    
    detector.start()
    
    try:
        # Keep running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping wake word detection...")
        detector.stop()
        print("Goodbye!")

