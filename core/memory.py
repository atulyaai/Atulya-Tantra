"""
Atulya Tantra - Memory Management System
Version: 2.0.1
Handles knowledge graphs, vector stores, and memory management for the AGI system.
"""

import asyncio
import json
import sqlite3
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import networkx as nx
import chromadb
from sentence_transformers import SentenceTransformer
import numpy as np

@dataclass
class Memory:
    """Memory data structure"""
    id: str
    content: str
    memory_type: str  # 'conversation', 'knowledge', 'experience', 'preference'
    timestamp: datetime
    importance: float  # 0.0 to 1.0
    tags: List[str]
    metadata: Dict[str, Any]

@dataclass
class KnowledgeNode:
    """Knowledge graph node"""
    id: str
    label: str
    node_type: str  # 'concept', 'entity', 'relation', 'fact'
    properties: Dict[str, Any]
    confidence: float

class VectorStore:
    """Vector database for semantic search"""
    
    def __init__(self, persist_directory: str = "data/database/vectors"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(
            name="atulya_memories",
            metadata={"description": "Atulya Tantra memory vectors"}
        )
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
    
    async def add_memory(self, memory: Memory) -> str:
        """Add memory to vector store"""
        embedding = self.embedder.encode(memory.content).tolist()
        
        self.collection.add(
            embeddings=[embedding],
            documents=[memory.content],
            metadatas=[asdict(memory)],
            ids=[memory.id]
        )
        return memory.id
    
    async def search_memories(self, query: str, limit: int = 10) -> List[Memory]:
        """Search memories by semantic similarity"""
        query_embedding = self.embedder.encode(query).tolist()
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit
        )
        
        memories = []
        for i, doc_id in enumerate(results['ids'][0]):
            metadata = results['metadatas'][0][i]
            memory = Memory(**metadata)
            memories.append(memory)
        
        return memories

class KnowledgeGraph:
    """Knowledge graph for relationship management"""
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self.node_counter = 0
    
    def add_node(self, label: str, node_type: str, properties: Dict[str, Any] = None) -> str:
        """Add node to knowledge graph"""
        node_id = f"{node_type}_{self.node_counter}"
        self.node_counter += 1
        
        self.graph.add_node(
            node_id,
            label=label,
            node_type=node_type,
            properties=properties or {},
            confidence=1.0,
            created_at=datetime.now()
        )
        
        return node_id
    
    def add_relation(self, source_id: str, target_id: str, relation_type: str, 
                    properties: Dict[str, Any] = None) -> None:
        """Add relation between nodes"""
        self.graph.add_edge(
            source_id,
            target_id,
            relation_type=relation_type,
            properties=properties or {},
            confidence=1.0,
            created_at=datetime.now()
        )
    
    def find_related_nodes(self, node_id: str, max_depth: int = 2) -> List[str]:
        """Find nodes related to given node"""
        related = []
        for depth in range(1, max_depth + 1):
            nodes_at_depth = list(nx.single_source_shortest_path_length(
                self.graph, node_id, cutoff=depth
            ).keys())
            related.extend(nodes_at_depth)
        
        return list(set(related))
    
    def get_node_info(self, node_id: str) -> Optional[KnowledgeNode]:
        """Get detailed node information"""
        if node_id not in self.graph:
            return None
        
        node_data = self.graph.nodes[node_id]
        return KnowledgeNode(
            id=node_id,
            label=node_data['label'],
            node_type=node_data['node_type'],
            properties=node_data['properties'],
            confidence=node_data['confidence']
        )

class MemoryManager:
    """Main memory management system"""
    
    def __init__(self):
        self.vector_store = VectorStore()
        self.knowledge_graph = KnowledgeGraph()
        self.memory_db = "data/database/memories.db"
        self._init_database()
    
    def _init_database(self):
        """Initialize memory database"""
        conn = sqlite3.connect(self.memory_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                importance REAL NOT NULL,
                tags TEXT NOT NULL,
                metadata TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    async def store_memory(self, content: str, memory_type: str = "conversation",
                          importance: float = 0.5, tags: List[str] = None,
                          metadata: Dict[str, Any] = None) -> str:
        """Store a new memory"""
        memory_id = f"mem_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(content) % 10000}"
        
        memory = Memory(
            id=memory_id,
            content=content,
            memory_type=memory_type,
            timestamp=datetime.now(),
            importance=importance,
            tags=tags or [],
            metadata=metadata or {}
        )
        
        # Store in vector database
        await self.vector_store.add_memory(memory)
        
        # Store in SQLite database
        conn = sqlite3.connect(self.memory_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO memories 
            (id, content, memory_type, timestamp, importance, tags, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            memory.id,
            memory.content,
            memory.memory_type,
            memory.timestamp.isoformat(),
            memory.importance,
            json.dumps(memory.tags),
            json.dumps(memory.metadata)
        ))
        
        conn.commit()
        conn.close()
        
        return memory_id
    
    async def retrieve_memories(self, query: str, limit: int = 10) -> List[Memory]:
        """Retrieve memories by semantic search"""
        return await self.vector_store.search_memories(query, limit)
    
    async def get_recent_memories(self, hours: int = 24, limit: int = 50) -> List[Memory]:
        """Get recent memories"""
        conn = sqlite3.connect(self.memory_db)
        cursor = conn.cursor()
        
        cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        cursor.execute('''
            SELECT id, content, memory_type, timestamp, importance, tags, metadata
            FROM memories
            WHERE timestamp > ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (cutoff_time, limit))
        
        memories = []
        for row in cursor.fetchall():
            memory = Memory(
                id=row[0],
                content=row[1],
                memory_type=row[2],
                timestamp=datetime.fromisoformat(row[3]),
                importance=row[4],
                tags=json.loads(row[5]),
                metadata=json.loads(row[6])
            )
            memories.append(memory)
        
        conn.close()
        return memories
    
    def add_knowledge(self, concept: str, concept_type: str = "concept",
                     properties: Dict[str, Any] = None) -> str:
        """Add knowledge to the knowledge graph"""
        return self.knowledge_graph.add_node(concept, concept_type, properties)
    
    def link_knowledge(self, source_id: str, target_id: str, 
                      relation_type: str, properties: Dict[str, Any] = None) -> None:
        """Link knowledge nodes"""
        self.knowledge_graph.add_relation(source_id, target_id, relation_type, properties)
    
    def get_knowledge_context(self, concept: str) -> List[KnowledgeNode]:
        """Get knowledge context for a concept"""
        # Find nodes matching the concept
        matching_nodes = []
        for node_id, data in self.knowledge_graph.graph.nodes(data=True):
            if concept.lower() in data['label'].lower():
                matching_nodes.append(node_id)
        
        # Get related nodes
        all_related = []
        for node_id in matching_nodes:
            related = self.knowledge_graph.find_related_nodes(node_id)
            all_related.extend(related)
        
        # Convert to KnowledgeNode objects
        context = []
        for node_id in set(all_related):
            node_info = self.knowledge_graph.get_node_info(node_id)
            if node_info:
                context.append(node_info)
        
        return context

class PreferenceLearning:
    """Learn and adapt to user preferences"""
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager
        self.preferences = {}
    
    async def learn_preference(self, interaction: str, user_feedback: str) -> None:
        """Learn from user interaction and feedback"""
        # Extract preference patterns
        if "like" in user_feedback.lower() or "good" in user_feedback.lower():
            await self.memory_manager.store_memory(
                content=f"User likes: {interaction}",
                memory_type="preference",
                importance=0.8,
                tags=["positive", "preference"],
                metadata={"feedback": user_feedback}
            )
        elif "dislike" in user_feedback.lower() or "bad" in user_feedback.lower():
            await self.memory_manager.store_memory(
                content=f"User dislikes: {interaction}",
                memory_type="preference",
                importance=0.8,
                tags=["negative", "preference"],
                metadata={"feedback": user_feedback}
            )
    
    async def get_user_preferences(self, context: str) -> Dict[str, Any]:
        """Get user preferences for given context"""
        memories = await self.memory_manager.retrieve_memories(context, limit=5)
        
        preferences = {
            "positive": [],
            "negative": [],
            "patterns": []
        }
        
        for memory in memories:
            if memory.memory_type == "preference":
                if "positive" in memory.tags:
                    preferences["positive"].append(memory.content)
                elif "negative" in memory.tags:
                    preferences["negative"].append(memory.content)
        
        return preferences

# Global instances
_memory_manager: Optional[MemoryManager] = None
_vector_store: Optional[VectorStore] = None
_knowledge_graph: Optional[KnowledgeGraph] = None
_preference_learning: Optional[PreferenceLearning] = None

def get_memory_manager() -> MemoryManager:
    """Get global memory manager instance"""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager

def get_vector_store() -> VectorStore:
    """Get global vector store instance"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store

def get_knowledge_graph() -> KnowledgeGraph:
    """Get global knowledge graph instance"""
    global _knowledge_graph
    if _knowledge_graph is None:
        _knowledge_graph = KnowledgeGraph()
    return _knowledge_graph

def get_preference_learning() -> PreferenceLearning:
    """Get global preference learning instance"""
    global _preference_learning
    if _preference_learning is None:
        _preference_learning = PreferenceLearning(get_memory_manager())
    return _preference_learning

# Export main classes and functions
__all__ = [
    "Memory",
    "KnowledgeNode", 
    "VectorStore",
    "KnowledgeGraph",
    "MemoryManager",
    "PreferenceLearning",
    "get_memory_manager",
    "get_vector_store", 
    "get_knowledge_graph",
    "get_preference_learning"
]
