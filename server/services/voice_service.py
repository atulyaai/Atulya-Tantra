"""
Voice Service - Handles speech recognition and text-to-speech
Independent microservice for voice operations
"""

import logging
import asyncio
import tempfile
import os

logger = logging.getLogger(__name__)

class VoiceService:
    """Voice service for STT and TTS"""
    
    def __init__(self):
        self.tts_voice = "en-US-AriaNeural"  # Edge-TTS voice
    
    async def text_to_speech(self, text: str) -> bytes:
        """
        Convert text to speech audio
        
        Args:
            text: Text to convert
        
        Returns:
            Audio bytes (MP3 format)
        """
        try:
            import edge_tts
            
            # Remove emojis and special chars
            import re
            clean_text = re.sub(r'[^\w\s.,!?\'-]', '', text)
            
            logger.info(f"TTS: Converting to speech: {clean_text[:50]}...")
            
            # Generate speech
            communicate = edge_tts.Communicate(clean_text, self.tts_voice)
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_path = temp_file.name
            
            await communicate.save(temp_path)
            
            # Read audio bytes
            with open(temp_path, 'rb') as f:
                audio_data = f.read()
            
            # Cleanup
            os.unlink(temp_path)
            
            logger.info(f"TTS: Generated {len(audio_data)} bytes of audio")
            return audio_data
            
        except Exception as e:
            logger.error(f"TTS error: {e}")
            raise
    
    def speech_to_text(self, audio_data: bytes) -> str:
        """
        Convert speech to text
        
        Args:
            audio_data: Audio bytes
        
        Returns:
            Transcribed text
        """
        try:
            import speech_recognition as sr
            
            recognizer = sr.Recognizer()
            
            # Save audio to temp file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            # Recognize
            with sr.AudioFile(temp_path) as source:
                audio = recognizer.record(source)
                text = recognizer.recognize_google(audio)
            
            # Cleanup
            os.unlink(temp_path)
            
            logger.info(f"STT: Recognized: {text}")
            return text
            
        except Exception as e:
            logger.error(f"STT error: {e}")
            raise

# Singleton instance
voice_service = VoiceService()

