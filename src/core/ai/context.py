"""
Atulya Tantra - Conversation Context Management
Version: 2.5.0
Advanced conversation context and memory management
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import uuid
import logging
from src.core.memory.vector_store import VectorStore
from src.core.memory.knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Chat message data structure"""
    id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata or {}
        }


@dataclass
class ConversationContext:
    """Conversation context with semantic search capabilities"""
    conversation_id: str
    user_id: Optional[str]
    messages: List[Message]
    summary: Optional[str] = None
    topics: List[str] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.topics is None:
            self.topics = []
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


class ConversationMemory:
    """Manages conversation memory with semantic search and context relevance"""
    
    def __init__(self, vector_store: VectorStore, knowledge_graph: KnowledgeGraph):
        self.vector_store = vector_store
        self.knowledge_graph = knowledge_graph
        self.conversations: Dict[str, ConversationContext] = {}
        self.max_context_messages = 20  # Keep last 20 messages in context
        self.max_search_results = 5  # Max relevant messages to retrieve
    
    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """Add message to conversation and update memory"""
        
        # Create message
        message = Message(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata
        )
        
        # Get or create conversation
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = ConversationContext(
                conversation_id=conversation_id,
                user_id=user_id,
                messages=[]
            )
        
        conversation = self.conversations[conversation_id]
        conversation.messages.append(message)
        conversation.updated_at = datetime.now()
        
        # Add to vector store for semantic search
        await self.vector_store.add_memory(
            content=content,
            metadata={
                "conversation_id": conversation_id,
                "message_id": message.id,
                "role": role,
                "timestamp": message.timestamp.isoformat(),
                "user_id": user_id,
                **(metadata or {})
            }
        )
        
        # Update knowledge graph with topics/entities
        await self._extract_and_store_topics(conversation_id, content)
        
        # Keep conversation manageable
        if len(conversation.messages) > self.max_context_messages:
            conversation.messages = conversation.messages[-self.max_context_messages:]
        
        logger.info(f"Added {role} message to conversation {conversation_id}")
        return message
    
    async def get_relevant_context(
        self,
        conversation_id: str,
        query: str,
        limit: int = None
    ) -> List[Message]:
        """Get relevant messages from conversation history using semantic search"""
        
        if limit is None:
            limit = self.max_search_results
        
        # Search vector store for relevant messages
        search_results = await self.vector_store.search_memories(
            query=query,
            limit=limit,
            filters={"conversation_id": conversation_id}
        )
        
        # Convert to Message objects
        relevant_messages = []
        for result in search_results:
            message_id = result.metadata.get("message_id")
            if message_id:
                # Find message in conversation
                conversation = self.conversations.get(conversation_id)
                if conversation:
                    for msg in conversation.messages:
                        if msg.id == message_id:
                            relevant_messages.append(msg)
                            break
        
        logger.info(f"Found {len(relevant_messages)} relevant messages for query")
        return relevant_messages
    
    async def get_conversation_history(
        self,
        conversation_id: str,
        limit: Optional[int] = None
    ) -> List[Message]:
        """Get conversation history"""
        
        if conversation_id not in self.conversations:
            return []
        
        messages = self.conversations[conversation_id].messages
        
        if limit:
            messages = messages[-limit:]
        
        return messages
    
    async def get_conversation_summary(self, conversation_id: str) -> Optional[str]:
        """Get conversation summary"""
        
        if conversation_id not in self.conversations:
            return None
        
        conversation = self.conversations[conversation_id]
        
        if conversation.summary:
            return conversation.summary
        
        # Generate summary from recent messages
        recent_messages = conversation.messages[-10:]  # Last 10 messages
        if not recent_messages:
            return None
        
        # Simple summary generation (in production, use AI)
        topics = conversation.topics[:3]  # Top 3 topics
        message_count = len(conversation.messages)
        
        summary = f"Conversation with {message_count} messages"
        if topics:
            summary += f" covering topics: {', '.join(topics)}"
        
        conversation.summary = summary
        return summary
    
    async def _extract_and_store_topics(self, conversation_id: str, content: str):
        """Extract topics from message content and store in knowledge graph"""
        
        # Simple topic extraction (in production, use NLP)
        topics = []
        
        # Extract common topics
        topic_keywords = {
            "programming": ["code", "program", "function", "python", "javascript", "java"],
            "ai": ["ai", "artificial intelligence", "machine learning", "neural network"],
            "science": ["science", "research", "study", "experiment", "theory"],
            "business": ["business", "company", "market", "sales", "revenue"],
            "technology": ["tech", "software", "hardware", "computer", "internet"]
        }
        
        content_lower = content.lower()
        for topic, keywords in topic_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                topics.append(topic)
        
        # Store topics in knowledge graph
        conversation = self.conversations.get(conversation_id)
        if conversation:
            for topic in topics:
                if topic not in conversation.topics:
                    conversation.topics.append(topic)
                
                # Add to knowledge graph
                await self.knowledge_graph.add_node(
                    node_id=f"topic_{topic}",
                    node_type="topic",
                    properties={"name": topic, "conversation_id": conversation_id}
                )
    
    async def delete_conversation(self, conversation_id: str):
        """Delete conversation and its memory"""
        
        if conversation_id in self.conversations:
            conversation = self.conversations[conversation_id]
            
            # Remove from vector store
            for message in conversation.messages:
                await self.vector_store.delete_memory(message.id)
            
            # Remove from knowledge graph
            for topic in conversation.topics:
                await self.knowledge_graph.remove_node(f"topic_{topic}")
            
            # Remove from memory
            del self.conversations[conversation_id]
            
            logger.info(f"Deleted conversation {conversation_id}")
    
    def get_conversation_stats(self) -> Dict[str, Any]:
        """Get conversation statistics"""
        
        total_conversations = len(self.conversations)
        total_messages = sum(len(conv.messages) for conv in self.conversations.values())
        
        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "average_messages_per_conversation": total_messages / total_conversations if total_conversations > 0 else 0
        }
