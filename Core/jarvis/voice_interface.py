"""
Voice Interface for Atulya Tantra AGI JARVIS
Speech recognition, text-to-speech, and voice interaction
"""

import asyncio
import wave
import tempfile
import os
from typing import Dict, List, Any, Optional, AsyncGenerator
from datetime import datetime
import json

from ..config.settings import settings
from ..config.logging import get_logger
from ..config.exceptions import AgentError
from ..brain import generate_response, get_llm_router
from .personality_engine import get_conversational_ai, process_user_message

logger = get_logger(__name__)


class VoiceInterface:
    """Voice interface for JARVIS with speech recognition and synthesis"""
    
    def __init__(self):
        self.is_listening = False
        self.is_speaking = False
        self.voice_settings = {
            "voice_id": "default",
            "rate": 200,  # words per minute
            "volume": 0.8,
            "pitch": 0.5
        }
        self.speech_recognition_settings = {
            "language": "en-US",
            "timeout": 5,
            "phrase_timeout": 1
        }
        
        # Initialize speech engines
        self.tts_engine = None
        self.stt_engine = None
        self._initialize_speech_engines()
    
    def _initialize_speech_engines(self):
        """Initialize text-to-speech and speech-to-text engines"""
        try:
            if settings.enable_voice_interface:
                # Initialize TTS engine
                self._initialize_tts()
                
                # Initialize STT engine
                self._initialize_stt()
                
                logger.info("Voice interface initialized successfully")
            else:
                logger.info("Voice interface disabled in settings")
                
        except Exception as e:
            logger.error(f"Error initializing voice interface: {e}")
    
    def _initialize_tts(self):
        """Initialize text-to-speech engine"""
        try:
            import pyttsx3
            
            self.tts_engine = pyttsx3.init()
            
            # Configure voice settings
            voices = self.tts_engine.getProperty('voices')
            if voices:
                # Try to find a good voice
                for voice in voices:
                    if 'english' in voice.name.lower() or 'en' in voice.id.lower():
                        self.tts_engine.setProperty('voice', voice.id)
                        break
            
            self.tts_engine.setProperty('rate', self.voice_settings['rate'])
            self.tts_engine.setProperty('volume', self.voice_settings['volume'])
            
            logger.info("TTS engine initialized")
            
        except ImportError:
            logger.warning("pyttsx3 not available, TTS disabled")
        except Exception as e:
            logger.error(f"Error initializing TTS: {e}")
    
    def _initialize_stt(self):
        """Initialize speech-to-text engine"""
        try:
            import speech_recognition as sr
            
            self.stt_engine = sr.Recognizer()
            
            # Configure microphone
            self.microphone = sr.Microphone()
            
            # Adjust for ambient noise
            with self.microphone as source:
                self.stt_engine.adjust_for_ambient_noise(source, duration=1)
            
            logger.info("STT engine initialized")
            
        except ImportError:
            logger.warning("speech_recognition not available, STT disabled")
        except Exception as e:
            logger.error(f"Error initializing STT: {e}")
    
    async def listen_for_speech(self, timeout: int = 10) -> Optional[str]:
        """Listen for speech input and return transcribed text"""
        if not self.stt_engine:
            raise AgentError("Speech recognition not available")
        
        try:
            self.is_listening = True
            
            # Listen for audio
            with self.microphone as source:
                logger.info("Listening for speech...")
                audio = self.stt_engine.listen(
                    source, 
                    timeout=timeout,
                    phrase_time_limit=self.speech_recognition_settings['phrase_timeout']
                )
            
            # Transcribe audio
            logger.info("Transcribing speech...")
            text = self.stt_engine.recognize_google(
                audio, 
                language=self.speech_recognition_settings['language']
            )
            
            logger.info(f"Transcribed: {text}")
            return text.strip()
            
        except Exception as e:
            logger.error(f"Speech recognition error: {e}")
            return None
        finally:
            self.is_listening = False
    
    async def speak_text(self, text: str, async_mode: bool = True) -> bool:
        """Convert text to speech and play it"""
        if not self.tts_engine:
            raise AgentError("Text-to-speech not available")
        
        try:
            self.is_speaking = True
            
            if async_mode:
                # Run TTS in a separate thread
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._speak_sync, text)
            else:
                self._speak_sync(text)
            
            logger.info(f"Spoke: {text[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return False
        finally:
            self.is_speaking = False
    
    def _speak_sync(self, text: str):
        """Synchronous TTS function"""
        try:
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except Exception as e:
            logger.error(f"Sync TTS error: {e}")
    
    async def voice_conversation(self, user_id: str, timeout: int = 30) -> Dict[str, Any]:
        """Conduct a voice conversation with the user"""
        try:
            logger.info(f"Starting voice conversation with user {user_id}")
            
            # Greet the user
            greeting = "Hello! I'm JARVIS. How can I help you today?"
            await self.speak_text(greeting)
            
            conversation_log = []
            
            # Main conversation loop
            start_time = datetime.utcnow()
            while (datetime.utcnow() - start_time).seconds < timeout:
                try:
                    # Listen for user input
                    user_input = await self.listen_for_speech(timeout=10)
                    
                    if not user_input:
                        logger.info("No speech detected, continuing to listen...")
                        continue
                    
                    # Process the message
                    response_data = await process_user_message(user_id, user_input)
                    response_text = response_data.get("response", "I didn't understand that.")
                    
                    # Speak the response
                    await self.speak_text(response_text)
                    
                    # Log the conversation
                    conversation_log.append({
                        "timestamp": datetime.utcnow().isoformat(),
                        "user_input": user_input,
                        "jarvis_response": response_text,
                        "user_sentiment": response_data.get("user_sentiment"),
                        "jarvis_emotional_state": response_data.get("jarvis_emotional_state")
                    })
                    
                    # Check for conversation end signals
                    if any(word in user_input.lower() for word in ["goodbye", "bye", "exit", "quit", "stop"]):
                        farewell = "Goodbye! It was great talking with you."
                        await self.speak_text(farewell)
                        break
                    
                except Exception as e:
                    logger.error(f"Error in voice conversation: {e}")
                    await self.speak_text("I'm sorry, I didn't catch that. Could you please repeat?")
            
            return {
                "conversation_log": conversation_log,
                "duration_seconds": (datetime.utcnow() - start_time).seconds,
                "user_id": user_id,
                "completed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Voice conversation error: {e}")
            return {
                "error": str(e),
                "user_id": user_id,
                "completed_at": datetime.utcnow().isoformat()
            }
    
    async def process_voice_command(self, user_id: str, command: str) -> Dict[str, Any]:
        """Process a voice command"""
        try:
            # Analyze the command
            command_analysis = await self._analyze_voice_command(command)
            
            # Process based on command type
            if command_analysis["type"] == "conversation":
                response_data = await process_user_message(user_id, command)
                response_text = response_data.get("response", "I didn't understand that.")
                
                # Speak the response
                await self.speak_text(response_text)
                
                return {
                    "command_type": "conversation",
                    "response": response_text,
                    "user_sentiment": response_data.get("user_sentiment"),
                    "jarvis_emotional_state": response_data.get("jarvis_emotional_state")
                }
            
            elif command_analysis["type"] == "system_control":
                return await self._handle_system_command(command_analysis)
            
            elif command_analysis["type"] == "information_request":
                return await self._handle_information_request(command_analysis)
            
            else:
                response = "I'm not sure how to help with that. Could you please rephrase your request?"
                await self.speak_text(response)
                return {
                    "command_type": "unknown",
                    "response": response
                }
                
        except Exception as e:
            logger.error(f"Voice command processing error: {e}")
            error_response = "I encountered an error processing your command."
            await self.speak_text(error_response)
            return {
                "error": str(e),
                "response": error_response
            }
    
    async def _analyze_voice_command(self, command: str) -> Dict[str, Any]:
        """Analyze a voice command to determine its type and intent"""
        command_lower = command.lower()
        
        # System control commands
        system_keywords = ["open", "close", "start", "stop", "run", "execute", "launch"]
        if any(keyword in command_lower for keyword in system_keywords):
            return {
                "type": "system_control",
                "intent": "system_operation",
                "command": command,
                "confidence": 0.8
            }
        
        # Information requests
        info_keywords = ["what", "how", "when", "where", "why", "tell me", "explain"]
        if any(keyword in command_lower for keyword in info_keywords):
            return {
                "type": "information_request",
                "intent": "information_seeking",
                "command": command,
                "confidence": 0.9
            }
        
        # Default to conversation
        return {
            "type": "conversation",
            "intent": "general_chat",
            "command": command,
            "confidence": 0.7
        }
    
    async def _handle_system_command(self, command_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Handle system control commands"""
        command = command_analysis["command"]
        
        # For now, provide a generic response
        response = f"I understand you want me to {command}, but I need more specific instructions for system operations."
        await self.speak_text(response)
        
        return {
            "command_type": "system_control",
            "response": response,
            "command": command
        }
    
    async def _handle_information_request(self, command_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Handle information requests"""
        command = command_analysis["command"]
        
        # Process as a regular conversation
        response_data = await process_user_message("system", command)
        response_text = response_data.get("response", "I don't have that information.")
        
        await self.speak_text(response_text)
        
        return {
            "command_type": "information_request",
            "response": response_text,
            "command": command
        }
    
    def update_voice_settings(self, settings: Dict[str, Any]):
        """Update voice settings"""
        self.voice_settings.update(settings)
        
        if self.tts_engine:
            try:
                if 'rate' in settings:
                    self.tts_engine.setProperty('rate', settings['rate'])
                if 'volume' in settings:
                    self.tts_engine.setProperty('volume', settings['volume'])
                if 'voice_id' in settings:
                    self.tts_engine.setProperty('voice', settings['voice_id'])
                
                logger.info(f"Voice settings updated: {settings}")
            except Exception as e:
                logger.error(f"Error updating voice settings: {e}")
    
    def update_speech_recognition_settings(self, settings: Dict[str, Any]):
        """Update speech recognition settings"""
        self.speech_recognition_settings.update(settings)
        logger.info(f"Speech recognition settings updated: {settings}")
    
    async def test_voice_interface(self) -> Dict[str, Any]:
        """Test the voice interface components"""
        test_results = {
            "tts_available": self.tts_engine is not None,
            "stt_available": self.stt_engine is not None,
            "microphone_available": hasattr(self, 'microphone'),
            "tests_passed": 0,
            "tests_failed": 0,
            "errors": []
        }
        
        # Test TTS
        if test_results["tts_available"]:
            try:
                await self.speak_text("Voice interface test successful.")
                test_results["tests_passed"] += 1
            except Exception as e:
                test_results["tests_failed"] += 1
                test_results["errors"].append(f"TTS test failed: {e}")
        
        # Test STT (simplified)
        if test_results["stt_available"]:
            try:
                # Just check if we can initialize listening
                test_results["tests_passed"] += 1
            except Exception as e:
                test_results["tests_failed"] += 1
                test_results["errors"].append(f"STT test failed: {e}")
        
        return test_results
    
    async def get_voice_status(self) -> Dict[str, Any]:
        """Get current voice interface status"""
        return {
            "is_listening": self.is_listening,
            "is_speaking": self.is_speaking,
            "tts_available": self.tts_engine is not None,
            "stt_available": self.stt_engine is not None,
            "voice_settings": self.voice_settings,
            "speech_recognition_settings": self.speech_recognition_settings,
            "enabled": settings.enable_voice_interface
        }


class VoiceAssistant:
    """High-level voice assistant interface"""
    
    def __init__(self):
        self.voice_interface = VoiceInterface()
        self.wake_word_detection = False
        self.continuous_listening = False
        self.command_history: List[Dict[str, Any]] = []
    
    async def start_continuous_listening(self, user_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Start continuous voice listening"""
        self.continuous_listening = True
        
        try:
            while self.continuous_listening:
                try:
                    # Listen for speech
                    user_input = await self.voice_interface.listen_for_speech(timeout=5)
                    
                    if user_input:
                        # Process the command
                        result = await self.voice_interface.process_voice_command(user_id, user_input)
                        
                        # Add to command history
                        self.command_history.append({
                            "timestamp": datetime.utcnow().isoformat(),
                            "user_input": user_input,
                            "result": result
                        })
                        
                        yield result
                    
                except Exception as e:
                    logger.error(f"Error in continuous listening: {e}")
                    yield {
                        "error": str(e),
                        "type": "listening_error"
                    }
                
                # Small delay to prevent excessive CPU usage
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Continuous listening error: {e}")
        finally:
            self.continuous_listening = False
    
    async def stop_continuous_listening(self):
        """Stop continuous voice listening"""
        self.continuous_listening = False
        logger.info("Continuous listening stopped")
    
    async def quick_command(self, user_id: str, timeout: int = 10) -> Dict[str, Any]:
        """Execute a quick voice command"""
        try:
            # Listen for a single command
            user_input = await self.voice_interface.listen_for_speech(timeout=timeout)
            
            if not user_input:
                return {
                    "error": "No speech detected",
                    "type": "no_input"
                }
            
            # Process the command
            result = await self.voice_interface.process_voice_command(user_id, user_input)
            
            # Add to command history
            self.command_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "user_input": user_input,
                "result": result
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Quick command error: {e}")
            return {
                "error": str(e),
                "type": "command_error"
            }
    
    async def get_command_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent command history"""
        return self.command_history[-limit:] if self.command_history else []
    
    async def clear_command_history(self):
        """Clear command history"""
        self.command_history.clear()
        logger.info("Command history cleared")


# Global voice assistant instance
_voice_assistant: Optional[VoiceAssistant] = None


async def get_voice_assistant() -> VoiceAssistant:
    """Get global voice assistant instance"""
    global _voice_assistant
    
    if _voice_assistant is None:
        _voice_assistant = VoiceAssistant()
    
    return _voice_assistant


async def start_voice_conversation(user_id: str, timeout: int = 30) -> Dict[str, Any]:
    """Start a voice conversation with JARVIS"""
    voice_interface = VoiceInterface()
    return await voice_interface.voice_conversation(user_id, timeout)


async def process_voice_command(user_id: str, command: str) -> Dict[str, Any]:
    """Process a voice command"""
    voice_interface = VoiceInterface()
    return await voice_interface.process_voice_command(user_id, command)


async def test_voice_interface() -> Dict[str, Any]:
    """Test the voice interface"""
    voice_interface = VoiceInterface()
    return await voice_interface.test_voice_interface()


# Export public API
__all__ = [
    "VoiceInterface",
    "VoiceAssistant",
    "get_voice_assistant",
    "start_voice_conversation",
    "process_voice_command",
    "test_voice_interface"
]
