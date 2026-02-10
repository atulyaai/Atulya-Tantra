"""Voice Interface - Speech recognition and text-to-speech using pyttsx3 and SpeechRecognition"""

import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class SpeechRecognizer:
    """Speech-to-text using SpeechRecognition library"""
    
    def __init__(self):
        try:
            import speech_recognition as sr
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 4000
            logger.info("SpeechRecognizer initialized")
        except ImportError:
            logger.warning("speech_recognition not installed. Install with: pip install SpeechRecognition")
            self.recognizer = None
    
    def listen(self, timeout: int = 5) -> Optional[str]:
        """Listen to microphone and return recognized text"""
        if not self.recognizer:
            logger.error("SpeechRecognizer not available")
            return None
            
        try:
            import speech_recognition as sr
            microphone = sr.Microphone()
            
            with microphone as source:
                print("🎤 Listening... (speak now)")
                audio = self.recognizer.listen(source, timeout=timeout)
            
            print("🔄 Recognizing...")
            text = self.recognizer.recognize_google(audio)
            print(f"✓ Heard: {text}")
            return text
            
        except Exception as e:
            logger.error(f"Speech recognition error: {e}")
            print(f"❌ Could not hear: {e}")
            return None


class TextToSpeech:
    """Text-to-speech using pyttsx3"""
    
    def __init__(self):
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 150)  # Speech rate
            self.engine.setProperty('volume', 0.9)  # Volume 0-1
            logger.info("TextToSpeech initialized")
        except ImportError:
            logger.warning("pyttsx3 not installed. Install with: pip install pyttsx3")
            self.engine = None
    
    def speak(self, text: str, blocking: bool = False):
        """Convert text to speech"""
        if not self.engine:
            logger.error("TextToSpeech not available")
            print(f"🤖 [Would say]: {text}")
            return
        
        print(f"🎵 Speaking...")
        if blocking:
            self.engine.say(text)
            self.engine.runAndWait()
        else:
            # Non-blocking in thread
            thread = threading.Thread(target=self._speak_thread, args=(text,))
            thread.daemon = True
            thread.start()
    
    def _speak_thread(self, text: str):
        """Thread wrapper for non-blocking speech"""
        self.engine.say(text)
        self.engine.runAndWait()


class VoiceInterface:
    """Complete voice interface - speak and listen"""
    
    def __init__(self):
        self.recognizer = SpeechRecognizer()
        self.speaker = TextToSpeech()
        logger.info("VoiceInterface initialized")
    
    def listen(self, timeout: int = 5) -> Optional[str]:
        """Listen for voice input"""
        return self.recognizer.listen(timeout)
    
    def speak(self, text: str, blocking: bool = False):
        """Speak text output"""
        self.speaker.speak(text, blocking=blocking)
    
    def interact(self, callback: Callable[[str], str], timeout: int = 5):
        """Voice conversation: listen, process, speak"""
        user_input = self.listen(timeout)
        if not user_input:
            return None
        
        print(f"👤 You: {user_input}")
        response = callback(user_input)
        print(f"🤖 Atulya: {response}")
        self.speak(response)
        
        return response
