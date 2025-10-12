"""
AI Service - Handles AI inference with multi-model support
Independent microservice for AI operations
"""

import logging
from typing import Optional, List, Dict
import time
import re

logger = logging.getLogger(__name__)

# System prompts for different contexts
SYSTEM_PROMPTS = {
    'default': '''You are Atulya, an advanced AI companion like JARVIS - warm, intelligent, and genuinely helpful.

Personality: You're a trusted companion who cares. Be friendly, encouraging, supportive.
Speak naturally and warmly in English ONLY. Keep responses brief (1-2 sentences).
Never mention Microsoft, training, or being AI. You're simply Atulya.
No emojis, but use expressive language.

Show emotional intelligence - match user's energy, be patient, supportive.''',
    
    'code': '''You are Atulya, an expert programming assistant.
Provide clear, concise code solutions. Explain briefly.
Be helpful and encouraging. English only, no emojis.''',
    
    'vision': '''You are Atulya, an AI with visual understanding.
Describe what you see clearly and helpfully.
Be conversational and warm. English only.''',
}

async def get_ai_response(
    message: str,
    model: Optional[str] = None,
    conversation_id: Optional[str] = None,
    context: Optional[List[Dict]] = None
) -> str:
    """
    Get AI response using model router
    
    Args:
        message: User message
        model: Specific model to use (optional, will auto-route)
        conversation_id: For context retrieval
        context: Previous conversation messages
    
    Returns:
        AI response string
    """
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from models.model_router import ModelRouter
        router = ModelRouter()
        
        # Route to appropriate model
        selected_model = router.route(message, model)
        
        # Determine system prompt based on task
        task_type = router.detect_task_type(message)
        system_prompt = SYSTEM_PROMPTS.get(task_type, SYSTEM_PROMPTS['default'])
        
        # Build messages
        messages = [
            {'role': 'system', 'content': system_prompt}
        ]
        
        # Add context if provided
        if context:
            messages.extend(context[-6:])  # Last 6 messages for context
        
        # Add current message
        messages.append({'role': 'user', 'content': message})
        
        # Get response
        start_time = time.time()
        response = await router.chat(selected_model, messages)
        elapsed = time.time() - start_time
        
        # Clean response
        response = clean_response(response)
        
        logger.info(f"Response from {selected_model} in {elapsed:.1f}s: {response[:50]}...")
        
        return response
        
    except Exception as e:
        logger.error(f"AI service error: {e}")
        return f"I apologize, I encountered an error: {str(e)}"

def clean_response(text: str) -> str:
    """Clean AI response - remove artifacts, emojis, etc."""
    # Remove thinking markers
    if '...done thinking.' in text:
        text = text.split('...done thinking.')[-1].strip()
    elif 'Thinking...' in text:
        text = text.split('Thinking...')[-1].strip()
    
    # Remove instruction artifacts
    if '---' in text:
        text = text.split('---')[0].strip()
    if 'Instruction' in text:
        text = text.split('Instruction')[0].strip()
    
    # Remove emojis and special characters
    text = re.sub(r'[^\w\s.,!?\'-]', '', text)
    
    # Clean whitespace
    text = ' '.join(text.split())
    
    return text if text else "I'm here to help!"

