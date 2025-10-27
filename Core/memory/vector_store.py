"""
Vector Store for Atulya Tantra AGI
Vector storage and similarity search using ChromaDB
"""

import uuid
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import numpy as np

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None

from ..config.logging import get_logger
from ..config.exceptions import MemoryError, ValidationError

logger = get_logger(__name__)


class VectorStore:
    """Vector storage and similarity search"""
    
    def __init__(self, collection_name: str = "default", persist_directory: str = "./chroma_db"):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.client = None
        self.collection = None
        self.embeddings_cache = {}
        
        if not CHROMADB_AVAILABLE:
            logger.warning("ChromaDB not available, using mock implementation")
            self._initialize_mock()
        else:
            self._initialize_chromadb()
    
    def _initialize_chromadb(self):
        """Initialize ChromaDB client and collection"""
        try:
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )
            
            # Get or create collection
            try:
                self.collection = self.client.get_collection(self.collection_name)
            except ValueError:
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "AGI Memory Vector Store"}
                )
            
            logger.info(f"Initialized ChromaDB collection: {self.collection_name}")
            
        except Exception as e:
            logger.error(f"Error initializing ChromaDB: {e}")
            self._initialize_mock()
    
    def _initialize_mock(self):
        """Initialize mock vector store for testing"""
        self.client = None
        self.collection = None
        self.mock_data = {}
        logger.info("Initialized mock vector store")
    
    async def store_memory(
        self,
        content: str,
        metadata: Dict[str, Any] = None,
        user_id: str = None,
        memory_type: str = "general"
    ) -> str:
        """Store memory in vector store"""
        try:
            memory_id = str(uuid.uuid4())
            
            # Prepare metadata
            full_metadata = {
                "memory_id": memory_id,
                "user_id": user_id or "anonymous",
                "memory_type": memory_type,
                "created_at": datetime.now().isoformat(),
                "content_length": len(content),
                **(metadata or {})
            }
            
            if self.collection:
                # Store in ChromaDB
                self.collection.add(
                    documents=[content],
                    metadatas=[full_metadata],
                    ids=[memory_id]
                )
            else:
                # Store in mock
                self.mock_data[memory_id] = {
                    "content": content,
                    "metadata": full_metadata,
                    "embedding": self._generate_mock_embedding(content)
                }
            
            logger.info(f"Stored memory: {memory_id}")
            return memory_id
            
        except Exception as e:
            logger.error(f"Error storing memory: {e}")
            raise MemoryError(f"Failed to store memory: {e}")
    
    async def search_memory(
        self,
        query: str,
        user_id: str = None,
        limit: int = 10,
        threshold: float = 0.7,
        filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Search memories by similarity"""
        try:
            if self.collection:
                # Search in ChromaDB
                where_clause = {"user_id": user_id} if user_id else None
                if filters:
                    where_clause = {**(where_clause or {}), **filters}
                
                results = self.collection.query(
                    query_texts=[query],
                    n_results=limit,
                    where=where_clause
                )
                
                # Format results
                formatted_results = []
                for i, memory_id in enumerate(results["ids"][0]):
                    formatted_results.append({
                        "memory_id": memory_id,
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "similarity": 1 - results["distances"][0][i]  # Convert distance to similarity
                    })
                
                # Filter by threshold
                filtered_results = [
                    result for result in formatted_results
                    if result["similarity"] >= threshold
                ]
                
                return filtered_results
                
            else:
                # Search in mock
                return await self._mock_search(query, user_id, limit, threshold, filters)
                
        except Exception as e:
            logger.error(f"Error searching memory: {e}")
            raise MemoryError(f"Failed to search memory: {e}")
    
    async def get_memory(self, memory_id: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """Get specific memory by ID"""
        try:
            if self.collection:
                # Get from ChromaDB
                results = self.collection.get(
                    ids=[memory_id],
                    include=["documents", "metadatas"]
                )
                
                if not results["ids"]:
                    return None
                
                metadata = results["metadatas"][0]
                if user_id and metadata.get("user_id") != user_id:
                    return None
                
                return {
                    "id": memory_id,
                    "content": results["documents"][0],
                    "metadata": metadata,
                    "created_at": metadata.get("created_at"),
                    "updated_at": metadata.get("updated_at")
                }
                
            else:
                # Get from mock
                if memory_id in self.mock_data:
                    memory = self.mock_data[memory_id]
                    if user_id and memory["metadata"].get("user_id") != user_id:
                        return None
                    return {
                        "id": memory_id,
                        "content": memory["content"],
                        "metadata": memory["metadata"],
                        "created_at": memory["metadata"].get("created_at"),
                        "updated_at": memory["metadata"].get("updated_at")
                    }
                return None
                
        except Exception as e:
            logger.error(f"Error getting memory: {e}")
            return None
    
    async def update_memory(
        self,
        memory_id: str,
        content: str = None,
        metadata: Dict[str, Any] = None,
        user_id: str = None
    ) -> bool:
        """Update existing memory"""
        try:
            # Get existing memory
            existing_memory = await self.get_memory(memory_id, user_id)
            if not existing_memory:
                return False
            
            # Prepare updated metadata
            updated_metadata = existing_memory["metadata"].copy()
            if metadata:
                updated_metadata.update(metadata)
            updated_metadata["updated_at"] = datetime.now().isoformat()
            
            if self.collection:
                # Update in ChromaDB
                self.collection.update(
                    ids=[memory_id],
                    documents=[content or existing_memory["content"]],
                    metadatas=[updated_metadata]
                )
            else:
                # Update in mock
                if memory_id in self.mock_data:
                    if content:
                        self.mock_data[memory_id]["content"] = content
                    self.mock_data[memory_id]["metadata"] = updated_metadata
                    if content:
                        self.mock_data[memory_id]["embedding"] = self._generate_mock_embedding(content)
            
            logger.info(f"Updated memory: {memory_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating memory: {e}")
            return False
    
    async def delete_memory(self, memory_id: str, user_id: str = None) -> bool:
        """Delete memory by ID"""
        try:
            # Check if memory exists and belongs to user
            existing_memory = await self.get_memory(memory_id, user_id)
            if not existing_memory:
                return False
            
            if self.collection:
                # Delete from ChromaDB
                self.collection.delete(ids=[memory_id])
            else:
                # Delete from mock
                if memory_id in self.mock_data:
                    del self.mock_data[memory_id]
            
            logger.info(f"Deleted memory: {memory_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting memory: {e}")
            return False
    
    async def list_memories(
        self,
        user_id: str = None,
        limit: int = 100,
        offset: int = 0,
        memory_type: str = None
    ) -> List[Dict[str, Any]]:
        """List memories with pagination"""
        try:
            if self.collection:
                # Get from ChromaDB
                where_clause = {"user_id": user_id} if user_id else None
                if memory_type:
                    where_clause = {**(where_clause or {}), "memory_type": memory_type}
                
                results = self.collection.get(
                    where=where_clause,
                    limit=limit,
                    offset=offset,
                    include=["documents", "metadatas"]
                )
                
                # Format results
                formatted_results = []
                for i, memory_id in enumerate(results["ids"]):
                    formatted_results.append({
                        "id": memory_id,
                        "content": results["documents"][i],
                        "metadata": results["metadatas"][i],
                        "created_at": results["metadatas"][i].get("created_at"),
                        "updated_at": results["metadatas"][i].get("updated_at")
                    })
                
                return formatted_results
                
            else:
                # Get from mock
                return await self._mock_list_memories(user_id, limit, offset, memory_type)
                
        except Exception as e:
            logger.error(f"Error listing memories: {e}")
            return []
    
    async def get_stats(self, user_id: str = None) -> Dict[str, Any]:
        """Get vector store statistics"""
        try:
            if self.collection:
                # Get stats from ChromaDB
                count = self.collection.count()
                return {
                    "total_memories": count,
                    "collection_name": self.collection_name,
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                # Get stats from mock
                total_memories = len(self.mock_data)
                user_memories = len([
                    memory for memory in self.mock_data.values()
                    if not user_id or memory["metadata"].get("user_id") == user_id
                ])
                
                return {
                    "total_memories": total_memories,
                    "user_memories": user_memories,
                    "collection_name": self.collection_name,
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
    
    async def clear_memories(self, user_id: str = None) -> int:
        """Clear all memories for a user"""
        try:
            if self.collection:
                # Clear from ChromaDB
                if user_id:
                    # Get all memories for user
                    results = self.collection.get(
                        where={"user_id": user_id},
                        include=["ids"]
                    )
                    if results["ids"]:
                        self.collection.delete(ids=results["ids"])
                    return len(results["ids"])
                else:
                    # Clear all memories
                    count = self.collection.count()
                    self.collection.delete()
                    return count
            else:
                # Clear from mock
                if user_id:
                    memories_to_delete = [
                        memory_id for memory_id, memory in self.mock_data.items()
                        if memory["metadata"].get("user_id") == user_id
                    ]
                    for memory_id in memories_to_delete:
                        del self.mock_data[memory_id]
                    return len(memories_to_delete)
                else:
                    count = len(self.mock_data)
                    self.mock_data.clear()
                    return count
                    
        except Exception as e:
            logger.error(f"Error clearing memories: {e}")
            return 0
    
    async def _mock_search(
        self,
        query: str,
        user_id: str = None,
        limit: int = 10,
        threshold: float = 0.7,
        filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Mock search implementation"""
        query_embedding = self._generate_mock_embedding(query)
        results = []
        
        for memory_id, memory in self.mock_data.items():
            # Check user filter
            if user_id and memory["metadata"].get("user_id") != user_id:
                continue
            
            # Check other filters
            if filters:
                skip = False
                for key, value in filters.items():
                    if memory["metadata"].get(key) != value:
                        skip = True
                        break
                if skip:
                    continue
            
            # Calculate similarity
            similarity = self._calculate_similarity(query_embedding, memory["embedding"])
            
            if similarity >= threshold:
                results.append({
                    "memory_id": memory_id,
                    "content": memory["content"],
                    "metadata": memory["metadata"],
                    "similarity": similarity
                })
        
        # Sort by similarity and limit
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]
    
    async def _mock_list_memories(
        self,
        user_id: str = None,
        limit: int = 100,
        offset: int = 0,
        memory_type: str = None
    ) -> List[Dict[str, Any]]:
        """Mock list memories implementation"""
        filtered_memories = []
        
        for memory_id, memory in self.mock_data.items():
            # Check user filter
            if user_id and memory["metadata"].get("user_id") != user_id:
                continue
            
            # Check memory type filter
            if memory_type and memory["metadata"].get("memory_type") != memory_type:
                continue
            
            filtered_memories.append({
                "id": memory_id,
                "content": memory["content"],
                "metadata": memory["metadata"],
                "created_at": memory["metadata"].get("created_at"),
                "updated_at": memory["metadata"].get("updated_at")
            })
        
        # Sort by created_at and apply pagination
        filtered_memories.sort(key=lambda x: x["created_at"], reverse=True)
        return filtered_memories[offset:offset + limit]
    
    def _generate_mock_embedding(self, text: str) -> List[float]:
        """Generate mock embedding for testing"""
        # Simple hash-based embedding
        import hashlib
        hash_obj = hashlib.md5(text.encode())
        hash_bytes = hash_obj.digest()
        
        # Convert to 128-dimensional vector
        embedding = []
        for i in range(0, len(hash_bytes), 4):
            chunk = hash_bytes[i:i+4]
            value = int.from_bytes(chunk, byteorder='big') / (2**32)
            embedding.append(value)
        
        # Pad or truncate to 128 dimensions
        while len(embedding) < 128:
            embedding.append(0.0)
        embedding = embedding[:128]
        
        return embedding
    
    def _calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between embeddings"""
        try:
            # Convert to numpy arrays
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # Calculate cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0


# Global vector store instance
_vector_store = None


def get_vector_store() -> VectorStore:
    """Get global vector store instance"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


# Export public API
__all__ = [
    "VectorStore",
    "get_vector_store"
]