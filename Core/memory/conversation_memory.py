"""
Conversation Memory System
Manages conversation history, user preferences, and context persistence
"""

import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from ..jarvis.personality_engine import ConversationContext

class ConversationMemory:
    """
    Advanced memory system for conversation context and user preferences
    """
    
    def __init__(self, memory_dir: str = "memory"):
        self.memory_dir = memory_dir
        self.user_memories: Dict[str, Dict[str, Any]] = {}
        self.conversation_histories: Dict[str, List[Dict[str, Any]]] = {}
        
        # Create memory directory if it doesn't exist
        os.makedirs(memory_dir, exist_ok=True)
        
        # Load existing memories
        self._load_memories()
    
    def save_context(self, context: ConversationContext):
        """
        Save conversation context to memory
        """
        user_id = context.user_id
        session_id = context.session_id
        
        # Save user preferences
        if user_id not in self.user_memories:
            self.user_memories[user_id] = {
                "preferences": {},
                "profile": {},
                "history": []
            }
        
        # Update user preferences
        self.user_memories[user_id]["preferences"].update(context.user_preferences)
        
        # Save conversation history
        context_key = f"{user_id}_{session_id}"
        self.conversation_histories[context_key] = context.conversation_history
        
        # Persist to disk
        self._persist_memories()
    
    def load_context(self, user_id: str, session_id: str) -> Optional[ConversationContext]:
        """
        Load conversation context from memory
        """
        context_key = f"{user_id}_{session_id}"
        
        if context_key in self.conversation_histories:
            conversation_history = self.conversation_histories[context_key]
            user_preferences = self.user_memories.get(user_id, {}).get("preferences", {})
            
            return ConversationContext(
                user_id=user_id,
                session_id=session_id,
                current_state=None,  # Will be set by the calling code
                conversation_history=conversation_history,
                user_preferences=user_preferences,
                active_tasks=[]
            )
        
        return None
    
    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Get user preferences
        """
        return self.user_memories.get(user_id, {}).get("preferences", {})
    
    def update_user_preferences(self, user_id: str, preferences: Dict[str, Any]):
        """
        Update user preferences
        """
        if user_id not in self.user_memories:
            self.user_memories[user_id] = {
                "preferences": {},
                "profile": {},
                "history": []
            }
        
        self.user_memories[user_id]["preferences"].update(preferences)
        self._persist_memories()
    
    def get_conversation_summary(self, user_id: str, session_id: str) -> Dict[str, Any]:
        """
        Get conversation summary for context
        """
        context_key = f"{user_id}_{session_id}"
        conversation_history = self.conversation_histories.get(context_key, [])
        
        if not conversation_history:
            return {"summary": "No previous conversation", "key_topics": []}
        
        # Extract key topics from conversation
        key_topics = self._extract_key_topics(conversation_history)
        
        # Generate summary
        summary = self._generate_summary(conversation_history)
        
        return {
            "summary": summary,
            "key_topics": key_topics,
            "message_count": len(conversation_history),
            "last_activity": conversation_history[-1].get("timestamp") if conversation_history else None
        }
    
    def search_conversation_history(self, user_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search through conversation history
        """
        results = []
        query_lower = query.lower()
        
        for context_key, history in self.conversation_histories.items():
            if context_key.startswith(f"{user_id}_"):
                for message in history:
                    if query_lower in message.get("content", "").lower():
                        results.append({
                            "content": message["content"],
                            "role": message["role"],
                            "timestamp": message["timestamp"],
                            "session_id": context_key.split("_", 1)[1]
                        })
        
        # Sort by timestamp and limit results
        results.sort(key=lambda x: x["timestamp"], reverse=True)
        return results[:limit]
    
    def cleanup_old_memories(self, days: int = 30):
        """
        Clean up old conversation memories
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        to_remove = []
        
        for context_key, history in self.conversation_histories.items():
            if history:
                last_message = history[-1]
                last_timestamp = datetime.fromisoformat(last_message.get("timestamp", ""))
                if last_timestamp < cutoff_date:
                    to_remove.append(context_key)
        
        for context_key in to_remove:
            del self.conversation_histories[context_key]
        
        self._persist_memories()
    
    def _extract_key_topics(self, conversation_history: List[Dict[str, Any]]) -> List[str]:
        """
        Extract key topics from conversation history
        """
        topics = []
        topic_keywords = {
            "weather": ["weather", "temperature", "forecast", "rain", "sunny"],
            "system": ["open", "close", "volume", "screenshot", "window"],
            "search": ["search", "find", "look up", "google"],
            "communication": ["email", "message", "send", "notify"],
            "scheduling": ["schedule", "appointment", "meeting", "calendar"],
            "information": ["what is", "tell me", "explain", "how to"]
        }
        
        for message in conversation_history:
            content = message.get("content", "").lower()
            for topic, keywords in topic_keywords.items():
                if any(keyword in content for keyword in keywords):
                    if topic not in topics:
                        topics.append(topic)
        
        return topics
    
    def _generate_summary(self, conversation_history: List[Dict[str, Any]]) -> str:
        """
        Generate conversation summary
        """
        if not conversation_history:
            return "No conversation history"
        
        # Count message types
        user_messages = [msg for msg in conversation_history if msg.get("role") == "user"]
        assistant_messages = [msg for msg in conversation_history if msg.get("role") == "assistant"]
        
        # Extract common themes
        themes = self._extract_key_topics(conversation_history)
        
        summary = f"Conversation with {len(user_messages)} user messages and {len(assistant_messages)} assistant responses"
        
        if themes:
            summary += f". Key topics discussed: {', '.join(themes)}"
        
        return summary
    
    def _load_memories(self):
        """
        Load memories from disk
        """
        try:
            # Load user memories
            user_memories_file = os.path.join(self.memory_dir, "user_memories.json")
            if os.path.exists(user_memories_file):
                with open(user_memories_file, 'r') as f:
                    self.user_memories = json.load(f)
            
            # Load conversation histories
            conversation_file = os.path.join(self.memory_dir, "conversations.json")
            if os.path.exists(conversation_file):
                with open(conversation_file, 'r') as f:
                    self.conversation_histories = json.load(f)
        
        except Exception as e:
            print(f"Error loading memories: {e}")
            self.user_memories = {}
            self.conversation_histories = {}
    
    def _persist_memories(self):
        """
        Persist memories to disk
        """
        try:
            # Save user memories
            user_memories_file = os.path.join(self.memory_dir, "user_memories.json")
            with open(user_memories_file, 'w') as f:
                json.dump(self.user_memories, f, indent=2)
            
            # Save conversation histories
            conversation_file = os.path.join(self.memory_dir, "conversations.json")
            with open(conversation_file, 'w') as f:
                json.dump(self.conversation_histories, f, indent=2)
        
        except Exception as e:
            print(f"Error persisting memories: {e}")
