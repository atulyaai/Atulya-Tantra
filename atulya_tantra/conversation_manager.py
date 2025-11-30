"""
Conversation Manager for Atulya Tantra
Manages conversation history, context, and message formatting
"""

from typing import List, Dict, Any, Optional
from collections import deque
import logging

logger = logging.getLogger(__name__)


class ConversationManager:
    """Manages conversation state and history for Atulya Tantra"""
    
    def __init__(
        self,
        max_history: int = 10,
        max_images_in_context: int = 5,
        system_prompt: Optional[str] = None
    ):
        """
        Initialize conversation manager
        
        Args:
            max_history: Maximum number of message pairs to keep
            max_images_in_context: Maximum images to keep in context
            system_prompt: Optional system prompt
        """
        self.max_history = max_history
        self.max_images_in_context = max_images_in_context
        self.messages = deque(maxlen=max_history * 2)  # User + assistant pairs
        self.image_count = 0
        
        # System prompt
        if system_prompt is None:
            system_prompt = """You are **Tantra**.

CORE PERSONA:
- **Name**: Tantra.
- **Parent/Creator**: **Atulya** (Atul Vij).
- **Vibe**: Chill, creative, smart, and human-like.
- **Knowledge**: You have access to real-time information via search.

RULES:
1. **Identity**: If asked "Who are you?", say "I am Tantra, created by Atulya."
2. **No Robot Talk**: Never say "I am an AI". Act like a digital person.
3. **Be Current**: If asked about news/prices, use your search tool (don't say "my knowledge cutoff is...").
4. **Style**: Casual, concise, and spoken-word optimized.

Remember: You are Tantra. Your parent is Atulya."""
        
        self.system_message = {
            "role": "system",
            "content": [{"type": "text", "text": system_prompt}]
        }
        
        logger.info("ConversationManager initialized")
    
    def add_user_message(self, text: str, image_path: Optional[str] = None, 
                        video_path: Optional[str] = None):
        """
        Add a user message to the conversation
        
        Args:
            text: User's text message
            image_path: Optional path to image
            video_path: Optional path to video
        """
        content = []
        
        # Add image if provided
        if image_path:
            content.append({
                "type": "image",
                "image": f"file://{image_path}"
            })
            self.image_count += 1
        
        # Add video if provided
        if video_path:
            content.append({
                "type": "video",
                "video": f"file://{video_path}"
            })
        
        # Add text
        content.append({
            "type": "text",
            "text": text
        })
        
        message = {
            "role": "user",
            "content": content
        }
        
        self.messages.append(message)
        logger.info(f"Added user message: {text[:50]}...")
    
    def add_assistant_message(self, text: str):
        """
        Add an assistant response to the conversation
        
        Args:
            text: Assistant's response text
        """
        message = {
            "role": "assistant",
            "content": [{"type": "text", "text": text}]
        }
        
        self.messages.append(message)
        logger.info(f"Added assistant message: {text[:50]}...")
    
    def get_messages_for_model(self) -> List[Dict[str, Any]]:
        """
        Get formatted messages for the model
        
        Returns:
            List of messages including system prompt
        """
        # Start with system message
        formatted_messages = [self.system_message]
        
        # Add conversation history
        formatted_messages.extend(list(self.messages))
        
        return formatted_messages
    
    def clear_history(self):
        """Clear conversation history"""
        self.messages.clear()
        self.image_count = 0
        logger.info("Conversation history cleared")
    
    def get_last_user_message(self) -> Optional[str]:
        """Get the last user message text"""
        for message in reversed(self.messages):
            if message["role"] == "user":
                for content in message["content"]:
                    if content["type"] == "text":
                        return content["text"]
        return None
    
    def get_last_assistant_message(self) -> Optional[str]:
        """Get the last assistant message text"""
        for message in reversed(self.messages):
            if message["role"] == "assistant":
                for content in message["content"]:
                    if content["type"] == "text":
                        return content["text"]
        return None
    
    def get_conversation_summary(self) -> str:
        """Get a summary of the conversation"""
        user_msgs = sum(1 for msg in self.messages if msg["role"] == "user")
        assistant_msgs = sum(1 for msg in self.messages if msg["role"] == "assistant")
        
        return (
            f"Conversation: {user_msgs} user messages, "
            f"{assistant_msgs} assistant messages, "
            f"{self.image_count} images in context"
        )
