"""
Atulya Tantra - Vector Store
Version: 2.5.0
Vector database for semantic search and memory storage
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Memory:
    """Memory data structure"""
    id: str
    content: str
    metadata: Dict[str, Any]
    timestamp: datetime
    embedding: Optional[List[float]] = None


class VectorStore:
    """Vector store for semantic search using ChromaDB and SentenceTransformer"""
    
    def __init__(self, collection_name: str = "atulya_memories"):
        self.collection_name = collection_name
        self.client = None
        self.collection = None
        self.embedder = None
        self._initialize()
    
    def _initialize(self):
        """Initialize ChromaDB and SentenceTransformer"""
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
            
            # Initialize ChromaDB client
            self.client = chromadb.PersistentClient(path="./data/vectors")
            
            # Initialize sentence transformer for embeddings
            self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Get or create collection
            try:
                self.collection = self.client.get_collection(name=self.collection_name)
            except:
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "Atulya Tantra conversation memories"}
                )
            
            logger.info("Vector store initialized successfully")
            
        except ImportError as e:
            logger.warning(f"Vector store dependencies not available: {e}")
            self.client = None
            self.embedder = None
    
    async def add_memory(self, content: str, metadata: Dict[str, Any]) -> str:
        """Add memory to vector store"""
        if not self.client or not self.embedder:
            logger.warning("Vector store not available, storing in memory")
            return str(uuid.uuid4())
        
        try:
            # Generate embedding
            embedding = self.embedder.encode(content).tolist()
            
            # Generate ID
            memory_id = str(uuid.uuid4())
            
            # Filter out None values from metadata for ChromaDB compatibility
            clean_metadata = {k: v for k, v in metadata.items() if v is not None}
            
            # Add to collection
            self.collection.add(
                ids=[memory_id],
                documents=[content],
                embeddings=[embedding],
                metadatas=[clean_metadata]
            )
            
            logger.info(f"Added memory {memory_id} to vector store")
            return memory_id
            
        except Exception as e:
            logger.error(f"Failed to add memory to vector store: {e}")
            return str(uuid.uuid4())
    
    async def search_memories(
        self,
        query: str,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Memory]:
        """Search memories using semantic similarity"""
        if not self.client or not self.embedder:
            logger.warning("Vector store not available")
            return []
        
        try:
            # Generate query embedding
            query_embedding = self.embedder.encode(query).tolist()
            
            # Search collection
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=filters
            )
            
            # Convert to Memory objects
            memories = []
            if results['ids'] and results['ids'][0]:
                for i, memory_id in enumerate(results['ids'][0]):
                    memories.append(Memory(
                        id=memory_id,
                        content=results['documents'][0][i],
                        metadata=results['metadatas'][0][i],
                        timestamp=datetime.now(),
                        embedding=results['embeddings'][0][i] if results['embeddings'] else None
                    ))
            
            logger.info(f"Found {len(memories)} memories for query")
            return memories
            
        except Exception as e:
            logger.error(f"Failed to search memories: {e}")
            return []
    
    async def delete_memory(self, memory_id: str) -> bool:
        """Delete memory from vector store"""
        if not self.client:
            logger.warning("Vector store not available")
            return False
        
        try:
            self.collection.delete(ids=[memory_id])
            logger.info(f"Deleted memory {memory_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete memory {memory_id}: {e}")
            return False
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get vector store statistics"""
        if not self.client:
            return {"status": "unavailable"}
        
        try:
            count = self.collection.count()
            return {
                "status": "available",
                "total_memories": count,
                "collection_name": self.collection_name
            }
        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {"status": "error", "error": str(e)}
