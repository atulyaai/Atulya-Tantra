"""
Conversation Memory for Atulya Tantra AGI
Memory management for conversations
"""

from typing import Dict, List, Any, Optional
from datetime import datetime

class ConversationMemory:
    """Manage conversation memory"""
    
    def __init__(self, max_memory: int = 100):
        self.max_memory = max_memory
        self.memories = []
        self.user_memories = {}
    
    def add_memory(self, user_id: str, content: str, memory_type: str = "conversation"):
        """Add memory for user"""
        memory = {
            'user_id': user_id,
            'content': content,
            'type': memory_type,
            'timestamp': datetime.now().isoformat()
        }
        
        self.memories.append(memory)
        
        # Keep only recent memories
        if len(self.memories) > self.max_memory:
            self.memories = self.memories[-self.max_memory:]
    
    def get_memories(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get memories for user"""
        user_memories = [
            mem for mem in self.memories 
            if mem['user_id'] == user_id
        ]
        return user_memories[-limit:]
    
    def get_recent_context(self, user_id: str, limit: int = 5) -> str:
        """Get recent context for user"""
        memories = self.get_memories(user_id, limit)
        context = " ".join([mem['content'] for mem in memories])
        return context