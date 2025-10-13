"""
Atulya Tantra - Text-to-Speech Engine
Makes JARVIS talk using Edge-TTS
"""

import asyncio
from typing import Optional
from pathlib import Path
from core.logger import get_logger
from core import get_config

logger = get_logger('models.audio.tts')


class TextToSpeech:
    """Text-to-Speech engine using Edge-TTS"""
    
    def __init__(self, voice: Optional[str] = None):
        """
        Initialize TTS engine
        
        Args:
            voice: Voice to use (default from config)
        """
        config = get_config()
        self.voice = voice or config.tts_voice
        logger.info(f"TTS initialized with voice: {self.voice}")
    
    async def speak(self, text: str, output_file: Optional[str] = None) -> str:
        """
        Convert text to speech
        
        Args:
            text: Text to speak
            output_file: Optional output file path
            
        Returns:
            Path to audio file
        """
        try:
            import edge_tts
            
            # Generate output path
            if not output_file:
                output_file = "data/speech_output.mp3"
            
            # Ensure directory exists
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            
            # Generate speech
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(output_file)
            
            logger.info(f"Speech generated: {len(text)} chars → {output_file}")
            return output_file
            
        except ImportError:
            logger.error("edge-tts not installed")
            return None
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return None
    
    def speak_sync(self, text: str, output_file: Optional[str] = None) -> str:
        """
        Synchronous version of speak
        
        Args:
            text: Text to speak
            output_file: Optional output file path
            
        Returns:
            Path to audio file
        """
        return asyncio.run(self.speak(text, output_file))
    
    async def speak_and_play(self, text: str) -> bool:
        """
        Speak text and play it immediately
        
        Args:
            text: Text to speak
            
        Returns:
            True if successful
        """
        audio_file = await self.speak(text)
        if not audio_file:
            return False
        
        # Play audio
        try:
            import pygame
            pygame.mixer.init()
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            
            # Wait for playback to finish
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.1)
            
            return True
            
        except ImportError:
            logger.warning("pygame not installed - audio saved but not played")
            return True
        except Exception as e:
            logger.error(f"Playback error: {e}")
            return False


# Global instance
_tts_engine: Optional[TextToSpeech] = None


def get_tts() -> TextToSpeech:
    """Get global TTS engine instance"""
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = TextToSpeech()
    return _tts_engine


__all__ = ['TextToSpeech', 'get_tts']

