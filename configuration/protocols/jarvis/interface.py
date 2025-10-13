"""
JARVIS Protocol - Main Interface
Primary interaction layer for our JARVIS-inspired AI
"""

import asyncio
import time
from typing import Optional, Dict, Any, List
from core.logger import get_logger
from configuration.prompts import get_prompt
from configuration import settings
from .conversation import ConversationManager
from .personality import PersonalityEngine

logger = get_logger('protocols.jarvis')

# Import TTS for voice output
try:
    from models.audio import get_tts
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    logger.warning("TTS not available")


class JarvisInterface:
    """
    JARVIS Protocol Interface
    
    Main entry point for JARVIS-style AI interactions
    Handles natural conversation with emotional intelligence
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize JARVIS interface
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.is_active = False
        
        # Get JARVIS protocol configuration
        from configuration import JARVIS_CONFIG
        protocol_settings = JARVIS_CONFIG.settings
        
        # Initialize sub-components
        max_history = protocol_settings.get('max_conversation_history', 50)
        self.conversation = ConversationManager(max_history=max_history)
        self.personality = PersonalityEngine()
        
        # AI Model configuration
        self.model = self.config.get('model', settings.default_model)
        self.temperature = self.config.get('temperature', settings.temperature)
        
        logger.info(f"JARVIS Protocol interface initialized with model: {self.model}")
    
    async def activate(self):
        """Activate JARVIS Protocol"""
        self.is_active = True
        logger.info("JARVIS Protocol activated")
        return {
            'status': 'active',
            'message': 'JARVIS Protocol online. Ready to assist.',
            'version': '1.0.1',
            'model': self.model
        }
    
    async def deactivate(self):
        """Deactivate JARVIS Protocol"""
        self.is_active = False
        logger.info("JARVIS Protocol deactivated")
        return {
            'status': 'inactive',
            'message': 'JARVIS Protocol offline.'
        }
    
    async def process_message(self, message: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Process incoming message through JARVIS Protocol
        
        Args:
            message: User message
            context: Optional context dictionary
            
        Returns:
            Response dictionary with message and metadata
        """
        if not self.is_active:
            await self.activate()
        
        start_time = time.time()
        logger.info(f"Processing message: {message[:50]}...")
        
        try:
            # Step 1: Detect emotion from user message
            user_emotion = self.personality.detect_emotion(message)
            logger.debug(f"Detected emotion: {user_emotion}")
            
            # Step 2: Adapt personality based on emotion
            emotional_state = self.personality.adapt_response_tone(user_emotion)
            modifiers = self.personality.get_response_modifiers()
            logger.debug(f"Personality state: {emotional_state.value}")
            
            # Step 3: Get conversation context
            recent_context = self.conversation.get_context(last_n=5)
            
            # Step 4: Build messages for AI
            messages = self._build_messages(message, recent_context, modifiers)
            
            # Step 5: Generate response using Ollama
            response_text = await self._generate_response(messages)
            
            # Step 6: Save to conversation history
            self.conversation.add_message('user', message, {'emotion': user_emotion})
            self.conversation.add_message('assistant', response_text, {
                'personality_state': emotional_state.value,
                'model': self.model
            })
            
            execution_time = time.time() - start_time
            logger.info(f"Response generated in {execution_time:.2f}s")
            
            # Generate audio if requested
            audio_file = None
            if context and context.get('enable_voice', False) and TTS_AVAILABLE:
                try:
                    tts = get_tts()
                    audio_file = await tts.speak(response_text)
                    logger.info(f"Audio generated: {audio_file}")
                except Exception as e:
                    logger.warning(f"TTS failed: {e}")
            
            return {
                'response': response_text,
                'status': 'success',
                'protocol': 'JARVIS',
                'emotion_detected': user_emotion,
                'personality_state': emotional_state.value,
                'model_used': self.model,
                'execution_time': execution_time,
                'context_preserved': True,
                'audio_file': audio_file,
                'voice_enabled': audio_file is not None
            }
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return {
                'response': "I apologize, but I encountered an error processing your message. Please try again.",
                'status': 'error',
                'protocol': 'JARVIS',
                'error': str(e)
            }
    
    def _build_messages(self, message: str, context: List[Dict], modifiers: Dict) -> List[Dict]:
        """
        Build messages array for AI model
        
        Args:
            message: Current user message
            context: Recent conversation context
            modifiers: Personality modifiers
            
        Returns:
            List of message dictionaries
        """
        # Get JARVIS system prompt
        base_prompt = get_prompt('jarvis')
        
        # Add personality modifiers to system prompt
        enhanced_prompt = f"{base_prompt}\n\nCurrent tone: {modifiers['tone']}\nBrevity: {modifiers['brevity']}"
        
        messages = [
            {'role': 'system', 'content': enhanced_prompt}
        ]
        
        # Add recent conversation context
        for ctx in context[-3:]:  # Last 3 messages for context
            messages.append({
                'role': ctx['role'],
                'content': ctx['content']
            })
        
        # Add current message
        messages.append({
            'role': 'user',
            'content': message
        })
        
        return messages
    
    async def _generate_response(self, messages: List[Dict]) -> str:
        """
        Generate response using Ollama with smart model routing
        
        Args:
            messages: Message history for context
            
        Returns:
            Generated response text
        """
        try:
            import ollama
            from models.model_router import get_model_router
            
            # Get user message
            user_message = messages[-1]['content'] if messages else ""
            
            # Select best model for task
            router = get_model_router()
            selected_model = router.select_model(user_message)
            model_config = router.get_model_config(selected_model)
            
            logger.info(f"Using {selected_model} for: {user_message[:30]}...")
            
            response = await asyncio.to_thread(
                ollama.chat,
                model=selected_model,
                messages=messages,
                options=model_config
            )
            
            # Get response text
            text = response['message']['content'].strip()
            
            # For simple greetings with simple model, keep it very short
            if selected_model == router.simple_model and len(user_message) < 20:
                # Take first sentence only
                if '. ' in text:
                    text = text.split('. ')[0] + '.'
                # Max 60 chars for greetings
                if len(text) > 60:
                    text = text[:60].rsplit(' ', 1)[0] + '.'
            
            return text
            
        except ImportError:
            logger.error("Ollama package not installed")
            return "AI model interface not available. Please install ollama package."
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """Get current JARVIS Protocol status"""
        return {
            'protocol': 'JARVIS',
            'version': '1.0.1',
            'active': self.is_active,
            'conversation_length': len(self.conversation.history),
            'model': self.model,
            'temperature': self.temperature,
            'capabilities': [
                'Natural Conversation',
                'Emotional Intelligence',
                'Voice Interaction',
                'Context Awareness',
                'Emotion Detection',
                'Personality Adaptation'
            ]
        }


# Placeholder for future expansion
__all__ = ['JarvisInterface']

