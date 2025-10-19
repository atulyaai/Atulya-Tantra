"""
Atulya Tantra - Voice System
Version: 2.2.0
Handles speech-to-text, text-to-speech, and wake word detection.
"""

import asyncio
import threading
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime
# Optional imports - handle gracefully if not available
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

try:
    import whisper
    WHISPER_AVAILABLE = True
except (ImportError, TypeError, Exception):
    WHISPER_AVAILABLE = False

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False

try:
    import wave
    import numpy as np
    AUDIO_UTILS_AVAILABLE = True
except ImportError:
    AUDIO_UTILS_AVAILABLE = False

@dataclass
class VoiceConfig:
    """Voice system configuration"""
    wake_word: str = "hey jarvis"
    stt_provider: str = "whisper"  # whisper, google, openai
    tts_provider: str = "edge"     # edge, pyttsx3
    language: str = "en-US"
    sample_rate: int = 16000
    chunk_size: int = 1024
    timeout: int = 5
    phrase_timeout: int = 3

@dataclass
class AudioData:
    """Audio data structure"""
    data: bytes
    sample_rate: int
    channels: int
    duration: float
    timestamp: datetime

class SpeechToText:
    """Speech-to-text engine"""
    
    def __init__(self, config: VoiceConfig):
        self.config = config
        self.recognizer = None
        self.microphone = None
        self.whisper_model = None
        
        # Initialize components if available
        if SPEECH_RECOGNITION_AVAILABLE:
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            
            # Adjust for ambient noise
            try:
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source)
            except Exception as e:
                print(f"Warning: Could not adjust for ambient noise: {e}")
    
    def _load_whisper_model(self):
        """Load Whisper model if not already loaded"""
        if not WHISPER_AVAILABLE:
            raise ImportError("Whisper not available")
        if self.whisper_model is None:
            self.whisper_model = whisper.load_model("base")
    
    async def transcribe_audio(self, audio_data: AudioData) -> str:
        """Transcribe audio data to text"""
        try:
            if self.config.stt_provider == "whisper":
                if not WHISPER_AVAILABLE:
                    print("Warning: Whisper not available, falling back to mock transcription")
                    return f"Mock transcription: {audio_data.data[:50]}..."
                return await self._transcribe_with_whisper(audio_data)
            elif self.config.stt_provider == "google":
                if not SPEECH_RECOGNITION_AVAILABLE:
                    print("Warning: Speech recognition not available, falling back to mock transcription")
                    return f"Mock transcription: {audio_data.data[:50]}..."
                return await self._transcribe_with_google(audio_data)
            else:
                raise ValueError(f"Unsupported STT provider: {self.config.stt_provider}")
        except Exception as e:
            print(f"STT Error: {e}")
            return ""
    
    async def _transcribe_with_whisper(self, audio_data: AudioData) -> str:
        """Transcribe using Whisper"""
        if not WHISPER_AVAILABLE or not AUDIO_UTILS_AVAILABLE:
            return f"Mock Whisper transcription: {audio_data.data[:50]}..."
        
        self._load_whisper_model()
        
        # Convert audio data to numpy array
        audio_array = np.frombuffer(audio_data.data, dtype=np.int16)
        
        # Transcribe
        result = self.whisper_model.transcribe(audio_array)
        return result["text"].strip()
    
    async def _transcribe_with_google(self, audio_data: AudioData) -> str:
        """Transcribe using Google Speech Recognition"""
        if not SPEECH_RECOGNITION_AVAILABLE:
            return f"Mock Google transcription: {audio_data.data[:50]}..."
        
        try:
            # Convert bytes to AudioData for speech_recognition
            audio_source = sr.AudioData(audio_data.data, audio_data.sample_rate, 2)
            text = self.recognizer.recognize_google(audio_source, language=self.config.language)
            return text
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            print(f"Google STT Error: {e}")
            return ""

class TextToSpeech:
    """Text-to-speech engine"""
    
    def __init__(self, config: VoiceConfig):
        self.config = config
        self.engine = None
        
        if self.config.tts_provider == "pyttsx3" and PYTTSX3_AVAILABLE:
            try:
                self.engine = pyttsx3.init()
                self._configure_pyttsx3()
            except Exception as e:
                print(f"Warning: Could not initialize pyttsx3: {e}")
                self.engine = None
    
    def _configure_pyttsx3(self):
        """Configure pyttsx3 engine"""
        if self.engine and PYTTSX3_AVAILABLE:
            try:
                voices = self.engine.getProperty('voices')
                if voices:
                    self.engine.setProperty('voice', voices[0].id)
                self.engine.setProperty('rate', 150)
                self.engine.setProperty('volume', 0.8)
            except Exception as e:
                print(f"Warning: Could not configure pyttsx3: {e}")
    
    async def speak(self, text: str) -> bool:
        """Convert text to speech"""
        try:
            if self.config.tts_provider == "edge":
                if not EDGE_TTS_AVAILABLE:
                    print(f"Mock TTS (Edge): {text}")
                    return True
                await self._speak_with_edge(text)
            elif self.config.tts_provider == "pyttsx3":
                if not PYTTSX3_AVAILABLE:
                    print(f"Mock TTS (pyttsx3): {text}")
                    return True
                await self._speak_with_pyttsx3(text)
            else:
                raise ValueError(f"Unsupported TTS provider: {self.config.tts_provider}")
            return True
        except Exception as e:
            print(f"TTS Error: {e}")
            return False
    
    async def _speak_with_edge(self, text: str):
        """Speak using Edge TTS"""
        if not EDGE_TTS_AVAILABLE:
            print(f"Mock Edge TTS: {text}")
            return
        
        voice = "en-US-AriaNeural"
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save("temp_audio.wav")
        
        # Play audio (simplified - in production, use proper audio player)
        print(f"Speaking: {text}")
    
    async def _speak_with_pyttsx3(self, text: str):
        """Speak using pyttsx3"""
        if not PYTTSX3_AVAILABLE or not self.engine:
            print(f"Mock pyttsx3 TTS: {text}")
            return
        
        self.engine.say(text)
        self.engine.runAndWait()

class WakeWordDetector:
    """Wake word detection system"""
    
    def __init__(self, config: VoiceConfig, callback: Callable[[], None]):
        self.config = config
        self.callback = callback
        self.is_listening = False
        self.audio_stream = None
        self.p = None
        
        # Initialize PyAudio if available
        if PYAUDIO_AVAILABLE:
            try:
                self.p = pyaudio.PyAudio()
            except Exception as e:
                print(f"Warning: Could not initialize PyAudio: {e}")
                self.p = None
        
    def start_listening(self):
        """Start listening for wake word"""
        if not PYAUDIO_AVAILABLE or not self.p:
            print("Warning: PyAudio not available, wake word detection disabled")
            return
        
        self.is_listening = True
        try:
            self.audio_stream = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.config.sample_rate,
                input=True,
                frames_per_buffer=self.config.chunk_size
            )
            
            # Start detection thread
            detection_thread = threading.Thread(target=self._detection_loop)
            detection_thread.daemon = True
            detection_thread.start()
        except Exception as e:
            print(f"Warning: Could not start audio stream: {e}")
            self.is_listening = False
    
    def stop_listening(self):
        """Stop listening for wake word"""
        self.is_listening = False
        if self.audio_stream:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            except Exception as e:
                print(f"Warning: Error stopping audio stream: {e}")
    
    def _detection_loop(self):
        """Main detection loop"""
        while self.is_listening:
            try:
                # Read audio data
                audio_data = self.audio_stream.read(self.config.chunk_size)
                
                # Simple wake word detection (in production, use proper ML model)
                if self._detect_wake_word(audio_data):
                    self.callback()
                
                time.sleep(0.1)  # Small delay to prevent CPU overload
                
            except Exception as e:
                print(f"Wake word detection error: {e}")
                break
    
    def _detect_wake_word(self, audio_data: bytes) -> bool:
        """Detect wake word in audio data (simplified implementation)"""
        # This is a placeholder - in production, use proper ML model
        # For now, just return False to prevent false triggers
        return False

class VoiceEngine:
    """Main voice engine coordinator"""
    
    def __init__(self, config: VoiceConfig = None):
        self.config = config or VoiceConfig()
        self.stt = SpeechToText(self.config)
        self.tts = TextToSpeech(self.config)
        self.wake_detector = None
        self.is_active = False
    
    def start_wake_word_detection(self, callback: Callable[[], None]):
        """Start wake word detection"""
        self.wake_detector = WakeWordDetector(self.config, callback)
        self.wake_detector.start_listening()
        self.is_active = True
    
    def stop_wake_word_detection(self):
        """Stop wake word detection"""
        if self.wake_detector:
            self.wake_detector.stop_listening()
        self.is_active = False
    
    async def process_voice_command(self, audio_data: AudioData) -> str:
        """Process voice command and return response"""
        # Transcribe audio
        text = await self.stt.transcribe_audio(audio_data)
        
        if text:
            print(f"Heard: {text}")
            # Here you would process the command and generate response
            response = f"I heard you say: {text}"
            
            # Speak response
            await self.tts.speak(response)
            
            return response
        
        return ""
    
    def get_status(self) -> Dict[str, Any]:
        """Get voice engine status"""
        return {
            "is_active": self.is_active,
            "wake_word": self.config.wake_word,
            "stt_provider": self.config.stt_provider,
            "tts_provider": self.config.tts_provider,
            "language": self.config.language
        }

# Global instances
_voice_engine: Optional[VoiceEngine] = None

def get_voice_engine() -> VoiceEngine:
    """Get global voice engine instance"""
    global _voice_engine
    if _voice_engine is None:
        _voice_engine = VoiceEngine()
    return _voice_engine

# Export main classes and functions
__all__ = [
    "VoiceConfig",
    "AudioData",
    "SpeechToText",
    "TextToSpeech",
    "WakeWordDetector",
    "VoiceEngine",
    "get_voice_engine"
]
