"""
Voice Output Module for Atulya Tantra
Handles text-to-speech using Piper TTS (high quality)
"""

import logging
from typing import Optional
import subprocess
import tempfile
import os
import sounddevice as sd
import soundfile as sf

logger = logging.getLogger(__name__)


class VoiceOutput:
    """Text-to-speech for voice output using Piper TTS"""
    
    def __init__(
        self,
        engine: str = "piper",
        voice: str = "en_US-lessac-medium",
        speaking_rate: float = 1.0,
        volume: float = 0.8,
        use_gpu: bool = False
    ):
        """
        Initialize voice output
        
        Args:
            engine: TTS engine ("piper" or "pyttsx3" fallback)
            voice: Voice model name for piper
            speaking_rate: Speaking rate multiplier
            volume: Volume level (0.0 to 1.0)
            use_gpu: Ignored for piper
        """
        self.engine = engine
        self.voice = voice
        self.speaking_rate = speaking_rate
        self.volume = volume
        
        logger.info(f"Initializing VoiceOutput with {engine}")
        
        # Check if piper is available
        if engine == "piper":
            try:
                result = subprocess.run(
                    ["piper", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0:
                    logger.info("✓ Piper TTS available")
                else:
                    logger.warning("Piper not found, will use espeak fallback")
                    self.engine = "espeak"
            except:
                logger.warning("Piper not found, will use espeak fallback")
                self.engine = "espeak"
        
        logger.info(f"✓ TTS engine ({self.engine}) initialized")
    
    def speak(self, text: str, blocking: bool = True):
        """
        Convert text to speech and play
        
        Args:
            text: Text to speak
            blocking: Wait for speech to finish
        """
        if not text or len(text.strip()) == 0:
            return
        
        logger.info(f"🔊 Speaking: {text[:50]}...")
        
        try:
            if self.engine == "piper":
                self._speak_piper(text, blocking)
            else:
                self._speak_espeak(text, blocking)
                
        except Exception as e:
            logger.error(f"Speech error: {e}")
            # Try espeak as fallback
            try:
                self._speak_espeak(text, blocking)
            except:
                logger.error("All TTS methods failed")
    
    def _speak_piper(self, text: str, blocking: bool = True):
        """Use Piper TTS"""
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_file = f.name
            
            # Generate speech with piper
            cmd = [
                "piper",
                "--model", self.voice,
                "--output_file", temp_file
            ]
            
            # Add speaking rate if supported
            length_scale = 1.0 / self.speaking_rate
            cmd.extend(["--length_scale", str(length_scale)])
            
            # Run piper
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            process.communicate(input=text.encode('utf-8'))
            
            # Play the audio file
            if os.path.exists(temp_file):
                self._play_audio_file(temp_file, blocking)
                
                # Clean up
                try:
                    os.remove(temp_file)
                except:
                    pass
            
        except Exception as e:
            logger.error(f"Piper error: {e}")
            raise
    
    def _speak_espeak(self, text: str, blocking: bool = True):
        """Use espeak for TTS (fallback)"""
        try:
            # Calculate speed (espeak uses words per minute, default ~175)
            speed = int(175 * self.speaking_rate)
            
            # Use espeak command
            cmd = ["espeak", "-s", str(speed), text]
            
            if blocking:
                subprocess.run(cmd, check=False, capture_output=True)
            else:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
        except FileNotFoundError:
            logger.error("espeak not found. Please install: sudo apt-get install espeak")
        except Exception as e:
            logger.error(f"espeak error: {e}")
    
    def _play_audio_file(self, filepath: str, blocking: bool = True):
        """Play an audio file"""
        try:
            data, samplerate = sf.read(filepath)
            
            # Adjust volume
            data = data * self.volume
            
            # Play
            sd.play(data, samplerate)
            
            if blocking:
                sd.wait()
                
        except Exception as e:
            logger.error(f"Audio playback error: {e}")
    
    def stop(self):
        """Stop current speech"""
        try:
            sd.stop()
        except:
            pass
    
    def test_voice(self):
        """Test the voice output"""
        test_text = "Hello, I am Atulya Tantra, your AI assistant."
        logger.info("Testing voice output...")
        self.speak(test_text)
