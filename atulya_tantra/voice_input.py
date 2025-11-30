"""
Voice Input Module for Atulya Tantra  
Handles speech-to-text using OpenAI Whisper
"""

import numpy as np
import sounddevice as sd
import logging
from typing import Optional
import whisper

logger = logging.getLogger(__name__)


class VoiceInput:
    """Speech-to-text using OpenAI Whisper"""
    
    def __init__(
        self,
        model_size: str = "base",
        language: str = "en",
        device: str = "cpu",
        compute_type: str = "int8",
        sample_rate: int = 16000,
        vad_enabled: bool = False
    ):
        """
        Initialize voice input
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
            language: Language code (e.g., "en")
            device: Device to run on ("cpu" or "cuda")
            compute_type: Ignored for openai-whisper
            sample_rate: Audio sample rate
            vad_enabled: Ignored for simplicity
        """
        self.model_size = model_size
        self.language = language
        self.sample_rate = sample_rate
        self.model = None
        
        logger.info(f"Initializing VoiceInput with model: {model_size}")
        
        # Load model
        try:
            self.model = whisper.load_model(model_size, device=device)
            logger.info("✓ Speech recognition model loaded")
        except Exception as e:
            logger.error(f"Error loading Whisper model: {e}")
            raise
    
    def record_audio(
        self,
        duration: Optional[float] = None,
        silence_duration: float = 1.5,
        max_duration: float = 30.0
    ) -> np.ndarray:
        """
        Record audio from microphone
        
        Args:
            duration: Fixed duration in seconds (if None, use fixed 5s)
            silence_duration: Ignored (simplified version)
            max_duration: Maximum recording duration
            
        Returns:
            Audio data as numpy array
        """
        logger.info("🎤 Listening...")
        
        # Use fixed duration for simplicity
        rec_duration = duration if duration else 5.0
        rec_duration = min(rec_duration, max_duration)
        
        try:
            # Record audio
            audio = sd.rec(
                int(rec_duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32'
            )
            sd.wait()
            
            audio_data = audio.flatten()
            logger.info(f"✓ Recorded {len(audio_data) / self.sample_rate:.1f}s of audio")
            return audio_data
            
        except Exception as e:
            logger.error(f"Recording error: {e}")
            return np.array([], dtype=np.float32)
    
    def transcribe(self, audio_data: np.ndarray) -> str:
        """
        Transcribe audio to text
        
        Args:
            audio_data: Audio data as numpy array
            
        Returns:
            Transcribed text
        """
        if len(audio_data) == 0:
            return ""
        
        try:
            # Transcribe
            result = self.model.transcribe(
                audio_data,
                language=self.language,
                fp16=False  # Use FP32 for CPU
            )
            
            text = result["text"].strip()
            
            if text:
                logger.info(f"📝 Transcribed: {text}")
            
            return text
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""
    
    def listen_and_transcribe(
        self,
        duration: Optional[float] = None,
        silence_duration: float = 1.5,
        max_duration: float = 30.0
    ) -> str:
        """
        Record audio and transcribe in one call
        
        Args:
            duration: Fixed duration in seconds (default 5s)
            silence_duration: Ignored
            max_duration: Maximum recording duration
            
        Returns:
            Transcribed text
        """
        audio = self.record_audio(duration, silence_duration, max_duration)
        return self.transcribe(audio)

