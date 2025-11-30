"""
Memory Manager - Vector Database for Tantra AI
Uses ChromaDB for semantic memory storage and retrieval
"""

import logging
from typing import List, Dict, Optional, Any
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class MemoryManager:
    """
    Manages long-term memory using vector database (ChromaDB)
    Stores: conversations, facts, preferences, learnings
    """
    
    def __init__(self, persist_directory: str = "./data/vectors"):
        """
        Initialize memory manager with ChromaDB
        
        Args:
            persist_directory: Where to store vector database
        """
        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize ChromaDB
        self.client = chromadb.Client(Settings(
            persist_directory=persist_directory,
            anonymized_telemetry=False
        ))
        
        # Initialize sentence transformer for embeddings
        logger.info("Loading embedding model...")
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')  # Fast, lightweight
        logger.info("✓ Embedding model loaded")
        
        # Create collections
        self.conversations = self._get_or_create_collection("conversations")
        self.facts = self._get_or_create_collection("facts")
        self.preferences = self._get_or_create_collection("preferences")
        
        logger.info("✓ Memory Manager initialized")
    
    def _get_or_create_collection(self, name: str):
        """Get or create a collection"""
        try:
            return self.client.get_collection(name=name)
        except:
            return self.client.create_collection(
                name=name,
                metadata={"description": f"Tantra {name} memory"}
            )
    
    def store_conversation(self, user_msg: str, assistant_msg: str, metadata: Optional[Dict] = None):
        """
        Store a conversation exchange
        
        Args:
            user_msg: User's message
            assistant_msg: Assistant's response
            metadata: Optional metadata (timestamp, context, etc.)
        """
        if metadata is None:
            metadata = {}
        
        metadata["timestamp"] = datetime.now().isoformat()
        metadata["type"] = "conversation"
        
        # Combine for semantic search
        combined_text = f"User: {user_msg}\nAssistant: {assistant_msg}"
        
        self.conversations.add(
            documents=[combined_text],
            metadatas=[metadata],
            ids=[f"conv_{datetime.now().timestamp()}"]
        )
        
        logger.info(f"Stored conversation: {user_msg[:50]}...")
    
    def store_fact(self, fact: str, source: str = "conversation", metadata: Optional[Dict] = None):
        """
        Store a learned fact
        
        Args:
            fact: The factual information
            source: Where this fact came from
            metadata: Additional context
        """
        if metadata is None:
            metadata = {}
        
        metadata.update({
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "type": "fact"
        })
        
        self.facts.add(
            documents=[fact],
            metadatas=[metadata],
            ids=[f"fact_{datetime.now().timestamp()}"]
        )
        
        logger.info(f"Stored fact: {fact[:50]}...")
    
    def store_preference(self, key: str, value: str, metadata: Optional[Dict] = None):
        """
        Store user preference
        
        Args:
            key: Preference category (e.g., "coding_language")
            value: Preference value (e.g., "Python")
            metadata: Additional context
        """
        if metadata is None:
            metadata = {}
        
        metadata.update({
            "timestamp": datetime.now().isoformat(),
            "key": key,
            "type": "preference"
        })
        
        self.preferences.add(
            documents=[f"{key}: {value}"],
            metadatas=[metadata],
            ids=[f"pref_{key}_{datetime.now().timestamp()}"]
        )
        
        logger.info(f"Stored preference: {key} = {value}")
    
    def search_conversations(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search conversation history
        
        Args:
            query: Search query
            n_results: Number of results to return
            
        Returns:
            List of relevant conversations
        """
        results = self.conversations.query(
            query_texts=[query],
            n_results=n_results
        )
        
        return self._format_results(results)
    
    def search_facts(self, query: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """Search stored facts"""
        results = self.facts.query(
            query_texts=[query],
            n_results=n_results
        )
        
        return self._format_results(results)
    
    def search_preferences(self, query: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """Search user preferences"""
        results = self.preferences.query(
            query_texts=[query],
            n_results=n_results
        )
        
        return self._format_results(results)
    
    def search_all(self, query: str, n_results: int = 5) -> Dict[str, List[Dict]]:
        """
        Search across all memory types
        
        Returns:
            Dict with keys: conversations, facts, preferences
        """
        return {
            "conversations": self.search_conversations(query, n_results),
            "facts": self.search_facts(query, n_results),
            "preferences": self.search_preferences(query, n_results)
        }
    
    def _format_results(self, results) -> List[Dict[str, Any]]:
        """Format ChromaDB results"""
        if not results or not results['documents']:
            return []
        
        formatted = []
        for i, doc in enumerate(results['documents'][0]):
            formatted.append({
                "text": doc,
                "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                "distance": results['distances'][0][i] if 'distances' in results else None
            })
        
        return formatted
    
    def clear_all(self):
        """Clear all memory (use with caution!)"""
        self.client.delete_collection("conversations")
        self.client.delete_collection("facts")
        self.client.delete_collection("preferences")
        
        # Recreate empty collections
        self.conversations = self._get_or_create_collection("conversations")
        self.facts = self._get_or_create_collection("facts")
        self.preferences = self._get_or_create_collection("preferences")
        
        logger.warning("⚠️ All memory cleared")
    
    def get_stats(self) -> Dict[str, int]:
        """Get memory statistics"""
        return {
            "conversations": self.conversations.count(),
            "facts": self.facts.count(),
            "preferences": self.preferences.count()
        }
