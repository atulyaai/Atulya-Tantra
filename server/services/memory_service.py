"""
Memory Service - Handles conversation memory and context
Independent microservice for memory operations
"""

import logging
from typing import Optional, List, Dict
from datetime import datetime
import json
import os

logger = logging.getLogger(__name__)

# Simple file-based storage (will integrate ChromaDB later)
MEMORY_DIR = "data/conversations"

async def save_conversation(data: dict) -> str:
    """Save conversation to memory"""
    try:
        os.makedirs(MEMORY_DIR, exist_ok=True)
        
        conversation_id = data.get('conversation_id', f"conv_{datetime.now().timestamp()}")
        filepath = os.path.join(MEMORY_DIR, f"{conversation_id}.json")
        
        # Load existing or create new
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                conversation = json.load(f)
        else:
            conversation = {
                'id': conversation_id,
                'created_at': datetime.now().isoformat(),
                'messages': []
            }
        
        # Add new message
        conversation['messages'].append({
            'timestamp': datetime.now().isoformat(),
            'user': data.get('user_message'),
            'assistant': data.get('assistant_response'),
            'model': data.get('model', 'phi3:mini')
        })
        
        conversation['updated_at'] = datetime.now().isoformat()
        
        # Save
        with open(filepath, 'w') as f:
            json.dump(conversation, f, indent=2)
        
        logger.info(f"Saved conversation: {conversation_id}")
        return conversation_id
        
    except Exception as e:
        logger.error(f"Save conversation error: {e}")
        raise

async def get_conversation(conversation_id: str) -> Dict:
    """Retrieve conversation from memory"""
    try:
        filepath = os.path.join(MEMORY_DIR, f"{conversation_id}.json")
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Conversation {conversation_id} not found")
        
        with open(filepath, 'r') as f:
            conversation = json.load(f)
        
        return conversation
        
    except Exception as e:
        logger.error(f"Get conversation error: {e}")
        raise

async def get_context_for_conversation(conversation_id: str, limit: int = 6) -> List[Dict]:
    """Get recent context messages for a conversation"""
    try:
        conversation = await get_conversation(conversation_id)
        messages = conversation.get('messages', [])
        
        # Get last N messages and format for AI
        recent = messages[-limit:]
        context = []
        
        for msg in recent:
            if msg.get('user'):
                context.append({'role': 'user', 'content': msg['user']})
            if msg.get('assistant'):
                context.append({'role': 'assistant', 'content': msg['assistant']})
        
        return context
        
    except Exception as e:
        logger.info(f"No context for {conversation_id}: {e}")
        return []

