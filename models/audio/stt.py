"""
Atulya Tantra - Speech-to-Text Engine
Converts voice to text using Google Speech Recognition
"""

from typing import Optional
from core.logger import get_logger

logger = get_logger('models.audio.stt')


class SpeechToText:
    """Speech-to-Text using Google Speech Recognition"""
    
    def __init__(self):
        """Initialize STT engine"""
        try:
            import speech_recognition as sr
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 300
            self.recognizer.dynamic_energy_threshold = True
            logger.info("STT initialized")
        except ImportError:
            logger.error("speech_recognition not installed")
            raise
    
    def listen(self, timeout: int = 5) -> Optional[str]:
        """
        Listen and convert speech to text
        
        Args:
            timeout: Listening timeout in seconds
            
        Returns:
            Recognized text or None
        """
        try:
            import speech_recognition as sr
            
            with sr.Microphone() as source:
                logger.info("Listening...")
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=10)
            
            logger.info("Recognizing...")
            text = self.recognizer.recognize_google(audio)
            logger.info(f"Recognized: {text}")
            return text
            
        except sr.WaitTimeoutError:
            logger.debug("No speech detected")
            return None
        except sr.UnknownValueError:
            logger.debug("Could not understand audio")
            return None
        except Exception as e:
            logger.error(f"STT error: {e}")
            return None


# Global instance
_stt_engine: Optional[SpeechToText] = None


def get_stt() -> SpeechToText:
    """Get global STT engine instance"""
    global _stt_engine
    if _stt_engine is None:
        _stt_engine = SpeechToText()
    return _stt_engine


__all__ = ['SpeechToText', 'get_stt']

