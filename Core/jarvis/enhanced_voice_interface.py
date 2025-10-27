"""
Enhanced Voice Interface for JARVIS AGI
Advanced speech recognition, natural conversation flow, and emotional voice synthesis
"""

import asyncio
import wave
import tempfile
import os
import threading
import queue
import time
from typing import Dict, List, Any, Optional, AsyncGenerator, Callable
from datetime import datetime, timedelta
from enum import Enum
import json
import re

from ..config.settings import settings
from ..config.logging import get_logger
from ..config.exceptions import AgentError
from ..brain import generate_response, get_llm_router
from .personality_engine import get_conversational_ai, process_user_message
from .sentiment_analyzer import get_sentiment_analyzer, analyze_user_sentiment, EmotionalContext

logger = get_logger(__name__)

# Voice interface dependencies
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    logger.warning("SpeechRecognition not available. Voice interface will be limited.")

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    logger.warning("pyttsx3 not available. TTS will be limited.")

try:
    import win32com.client
    WIN32_TTS_AVAILABLE = True
except ImportError:
    WIN32_TTS_AVAILABLE = False


class VoiceState(str, Enum):
    """Voice interface states"""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


class ConversationMode(str, Enum):
    """Conversation modes"""
    CONTINUOUS = "continuous"  # Always listening
    PUSH_TO_TALK = "push_to_talk"  # Press to talk
    WAKE_WORD = "wake_word"  # Listen for wake word
    MANUAL = "manual"  # Manual activation


class VoiceCommand:
    """Represents a voice command"""
    
    def __init__(self, text: str, confidence: float, timestamp: datetime = None):
        self.text = text
        self.confidence = confidence
        self.timestamp = timestamp or datetime.now()
        self.processed = False
        self.response = None
        self.emotional_context = None


class EnhancedVoiceInterface:
    """Enhanced voice interface with natural conversation flow"""
    
    def __init__(self):
        self.state = VoiceState.IDLE
        self.conversation_mode = ConversationMode.WAKE_WORD
        self.is_active = False
        self.is_listening = False
        self.is_speaking = False
        
        # Voice settings
        self.voice_settings = {
            "voice_id": "default",
            "rate": 200,  # words per minute
            "volume": 0.8,
            "pitch": 0.5,
            "emotion_modulation": True
        }
        
        # Speech recognition settings
        self.speech_settings = {
            "language": "en-US",
            "timeout": 5,
            "phrase_timeout": 1,
            "energy_threshold": 300,
            "pause_threshold": 0.8,
            "wake_word": "jarvis"
        }
        
        # Conversation management
        self.conversation_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.command_history = []
        self.conversation_context = []
        self.current_user_id = None
        
        # Voice engines
        self.recognizer = None
        self.microphone = None
        self.tts_engine = None
        self.sentiment_analyzer = get_sentiment_analyzer()
        
        # Callbacks
        self.on_command_received = None
        self.on_response_ready = None
        self.on_state_changed = None
        
        # Initialize components
        self._initialize_voice_engines()
        self._start_background_threads()
    
    def _initialize_voice_engines(self):
        """Initialize speech recognition and TTS engines"""
        try:
            # Initialize speech recognition
            if SPEECH_RECOGNITION_AVAILABLE:
                self.recognizer = sr.Recognizer()
                self.microphone = sr.Microphone()
                
                # Adjust for ambient noise
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=1)
                    self.recognizer.energy_threshold = self.speech_settings["energy_threshold"]
                    self.recognizer.pause_threshold = self.speech_settings["pause_threshold"]
                
                logger.info("Speech recognition initialized successfully")
            else:
                logger.warning("Speech recognition not available")
            
            # Initialize TTS
            if PYTTSX3_AVAILABLE:
                self.tts_engine = pyttsx3.init()
                self._configure_tts()
                logger.info("TTS engine initialized successfully")
            elif WIN32_TTS_AVAILABLE:
                self.tts_engine = win32com.client.Dispatch("SAPI.SpVoice")
                logger.info("Windows TTS engine initialized successfully")
            else:
                logger.warning("No TTS engine available")
                
        except Exception as e:
            logger.error(f"Error initializing voice engines: {e}")
    
    def _configure_tts(self):
        """Configure TTS engine settings"""
        if not self.tts_engine:
            return
        
        try:
            if PYTTSX3_AVAILABLE:
                # Set voice properties
                voices = self.tts_engine.getProperty('voices')
                if voices:
                    # Try to find a suitable voice
                    for voice in voices:
                        if 'english' in voice.name.lower() or 'en' in voice.id.lower():
                            self.tts_engine.setProperty('voice', voice.id)
                            break
                
                # Set speech rate
                self.tts_engine.setProperty('rate', self.voice_settings["rate"])
                
                # Set volume
                self.tts_engine.setProperty('volume', self.voice_settings["volume"])
                
        except Exception as e:
            logger.error(f"Error configuring TTS: {e}")
    
    def _start_background_threads(self):
        """Start background processing threads"""
        # Command processing thread
        threading.Thread(target=self._process_commands, daemon=True).start()
        
        # Response synthesis thread
        threading.Thread(target=self._synthesize_responses, daemon=True).start()
        
        # Conversation monitoring thread
        threading.Thread(target=self._monitor_conversation, daemon=True).start()
    
    async def start_conversation(self, user_id: str = None, mode: ConversationMode = None):
        """Start voice conversation"""
        try:
            self.current_user_id = user_id or "default_user"
            if mode:
                self.conversation_mode = mode
            
            self.is_active = True
            self._change_state(VoiceState.IDLE)
            
            # Start listening based on mode
            if self.conversation_mode == ConversationMode.CONTINUOUS:
                await self._start_continuous_listening()
            elif self.conversation_mode == ConversationMode.WAKE_WORD:
                await self._start_wake_word_listening()
            
            logger.info(f"Voice conversation started for user {self.current_user_id}")
            
        except Exception as e:
            logger.error(f"Error starting conversation: {e}")
            self._change_state(VoiceState.ERROR)
    
    async def stop_conversation(self):
        """Stop voice conversation"""
        try:
            self.is_active = False
            self.is_listening = False
            self.is_speaking = False
            self._change_state(VoiceState.IDLE)
            
            logger.info("Voice conversation stopped")
            
        except Exception as e:
            logger.error(f"Error stopping conversation: {e}")
    
    async def _start_continuous_listening(self):
        """Start continuous listening mode"""
        while self.is_active and not self.is_speaking:
            try:
                await self._listen_for_command()
                await asyncio.sleep(0.1)  # Small delay to prevent excessive CPU usage
            except Exception as e:
                logger.error(f"Error in continuous listening: {e}")
                await asyncio.sleep(1)
    
    async def _start_wake_word_listening(self):
        """Start wake word listening mode"""
        while self.is_active and not self.is_speaking:
            try:
                # Listen for wake word
                wake_word_detected = await self._detect_wake_word()
                if wake_word_detected:
                    logger.info("Wake word detected, starting command listening")
                    await self._listen_for_command()
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in wake word listening: {e}")
                await asyncio.sleep(1)
    
    async def _detect_wake_word(self) -> bool:
        """Detect wake word in audio"""
        if not self.recognizer or not self.microphone:
            return False
        
        try:
            with self.microphone as source:
                # Listen for wake word with shorter timeout
                audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=2)
            
            # Recognize wake word
            text = self.recognizer.recognize_google(audio, language=self.speech_settings["language"])
            text = text.lower().strip()
            
            # Check if wake word is present
            wake_word = self.speech_settings["wake_word"].lower()
            if wake_word in text:
                logger.info(f"Wake word '{wake_word}' detected in: {text}")
                return True
            
            return False
            
        except sr.WaitTimeoutError:
            return False
        except sr.UnknownValueError:
            return False
        except Exception as e:
            logger.error(f"Error detecting wake word: {e}")
            return False
    
    async def _listen_for_command(self):
        """Listen for voice command"""
        if not self.recognizer or not self.microphone:
            return
        
        try:
            self._change_state(VoiceState.LISTENING)
            self.is_listening = True
            
            with self.microphone as source:
                # Listen for command
                audio = self.recognizer.listen(
                    source, 
                    timeout=self.speech_settings["timeout"],
                    phrase_time_limit=10
                )
            
            # Recognize speech
            text = self.recognizer.recognize_google(
                audio, 
                language=self.speech_settings["language"]
            )
            
            # Create voice command
            command = VoiceCommand(text, 0.8)  # Default confidence
            command.emotional_context = await analyze_user_sentiment(text, self.current_user_id)
            
            # Add to conversation queue
            self.conversation_queue.put(command)
            self.command_history.append(command)
            
            logger.info(f"Voice command received: {text}")
            
        except sr.WaitTimeoutError:
            logger.debug("No speech detected within timeout")
        except sr.UnknownValueError:
            logger.debug("Could not understand speech")
        except Exception as e:
            logger.error(f"Error listening for command: {e}")
        finally:
            self.is_listening = False
            if self.state == VoiceState.LISTENING:
                self._change_state(VoiceState.IDLE)
    
    def _process_commands(self):
        """Process voice commands in background thread"""
        while True:
            try:
                if not self.conversation_queue.empty():
                    command = self.conversation_queue.get()
                    if command and not command.processed:
                        self._process_command(command)
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error processing command: {e}")
                time.sleep(1)
    
    def _process_command(self, command: VoiceCommand):
        """Process a voice command"""
        try:
            self._change_state(VoiceState.PROCESSING)
            
            # Process with conversational AI
            response = asyncio.run(self._generate_response(command))
            command.response = response
            command.processed = True
            
            # Add to response queue
            self.response_queue.put(response)
            
            # Callback
            if self.on_command_received:
                self.on_command_received(command)
            
            logger.info(f"Command processed: {command.text}")
            
        except Exception as e:
            logger.error(f"Error processing command: {e}")
            command.response = "I'm sorry, I had trouble processing that command."
            command.processed = True
        finally:
            if self.state == VoiceState.PROCESSING:
                self._change_state(VoiceState.IDLE)
    
    async def _generate_response(self, command: VoiceCommand) -> str:
        """Generate response for voice command"""
        try:
            # Get conversational AI
            conversational_ai = get_conversational_ai()
            
            # Process with emotional context
            if command.emotional_context:
                response = await conversational_ai.process_with_emotion(
                    command.text,
                    command.emotional_context,
                    user_id=self.current_user_id
                )
            else:
                response = await conversational_ai.process_message(
                    command.text,
                    user_id=self.current_user_id
                )
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I'm sorry, I couldn't process that request."
    
    def _synthesize_responses(self):
        """Synthesize responses in background thread"""
        while True:
            try:
                if not self.response_queue.empty():
                    response = self.response_queue.get()
                    if response:
                        self._speak_response(response)
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error synthesizing response: {e}")
                time.sleep(1)
    
    def _speak_response(self, text: str):
        """Speak response using TTS"""
        try:
            self._change_state(VoiceState.SPEAKING)
            self.is_speaking = True
            
            # Clean text for speech
            clean_text = self._clean_text_for_speech(text)
            
            # Speak using available TTS engine
            if PYTTSX3_AVAILABLE and self.tts_engine:
                self.tts_engine.say(clean_text)
                self.tts_engine.runAndWait()
            elif WIN32_TTS_AVAILABLE and self.tts_engine:
                self.tts_engine.Speak(clean_text)
            else:
                logger.warning("No TTS engine available, cannot speak response")
                print(f"JARVIS: {clean_text}")  # Fallback to text output
            
            # Callback
            if self.on_response_ready:
                self.on_response_ready(text)
            
            logger.info(f"Response spoken: {clean_text[:50]}...")
            
        except Exception as e:
            logger.error(f"Error speaking response: {e}")
        finally:
            self.is_speaking = False
            if self.state == VoiceState.SPEAKING:
                self._change_state(VoiceState.IDLE)
    
    def _clean_text_for_speech(self, text: str) -> str:
        """Clean text for better speech synthesis"""
        # Remove markdown formatting
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # Italic
        text = re.sub(r'`(.*?)`', r'\1', text)        # Code
        
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Clean up punctuation
        text = re.sub(r'[^\w\s.,!?;:]', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _monitor_conversation(self):
        """Monitor conversation state and manage flow"""
        while True:
            try:
                # Check for conversation timeouts
                if self.is_active and not self.is_speaking and not self.is_listening:
                    # If no activity for too long, go back to wake word mode
                    if self.conversation_mode == ConversationMode.CONTINUOUS:
                        # Check if we should switch to wake word mode
                        pass
                
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error monitoring conversation: {e}")
                time.sleep(5)
    
    def _change_state(self, new_state: VoiceState):
        """Change voice interface state"""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            logger.debug(f"Voice state changed: {old_state} -> {new_state}")
            
            # Callback
            if self.on_state_changed:
                self.on_state_changed(old_state, new_state)
    
    def set_voice_settings(self, settings: Dict[str, Any]):
        """Update voice settings"""
        self.voice_settings.update(settings)
        self._configure_tts()
    
    def set_speech_settings(self, settings: Dict[str, Any]):
        """Update speech recognition settings"""
        self.speech_settings.update(settings)
        if self.recognizer:
            self.recognizer.energy_threshold = self.speech_settings["energy_threshold"]
            self.recognizer.pause_threshold = self.speech_settings["pause_threshold"]
    
    def get_conversation_history(self) -> List[VoiceCommand]:
        """Get conversation history"""
        return self.command_history.copy()
    
    def clear_conversation_history(self):
        """Clear conversation history"""
        self.command_history.clear()
        self.conversation_context.clear()
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get current voice interface state"""
        return {
            "state": self.state.value,
            "conversation_mode": self.conversation_mode.value,
            "is_active": self.is_active,
            "is_listening": self.is_listening,
            "is_speaking": self.is_speaking,
            "user_id": self.current_user_id,
            "command_count": len(self.command_history)
        }


# Global instance
_enhanced_voice_interface = None

def get_enhanced_voice_interface() -> EnhancedVoiceInterface:
    """Get global enhanced voice interface instance"""
    global _enhanced_voice_interface
    if _enhanced_voice_interface is None:
        _enhanced_voice_interface = EnhancedVoiceInterface()
    return _enhanced_voice_interface

async def start_voice_conversation(user_id: str = None, mode: ConversationMode = None):
    """Start voice conversation"""
    interface = get_enhanced_voice_interface()
    await interface.start_conversation(user_id, mode)

async def stop_voice_conversation():
    """Stop voice conversation"""
    interface = get_enhanced_voice_interface()
    await interface.stop_conversation()

def get_voice_state() -> Dict[str, Any]:
    """Get current voice interface state"""
    interface = get_enhanced_voice_interface()
    return interface.get_current_state()

def set_voice_callbacks(on_command=None, on_response=None, on_state_change=None):
    """Set voice interface callbacks"""
    interface = get_enhanced_voice_interface()
    interface.on_command_received = on_command
    interface.on_response_ready = on_response
    interface.on_state_changed = on_state_change
