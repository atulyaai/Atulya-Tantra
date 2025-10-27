"""
Memory Management API for Atulya Tantra AGI
Memory operations, vector store, and knowledge graph endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from ..memory.vector_store import VectorStore
from ..memory.knowledge_graph import KnowledgeGraph
from ..auth.jwt import verify_token, TokenData
from ..config.logging import get_logger
from ..config.exceptions import MemoryError, ValidationError

logger = get_logger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryItem(BaseModel):
    """Memory item model"""
    id: str
    content: str
    metadata: Dict[str, Any] = {}
    created_at: str
    updated_at: str


class MemorySearchRequest(BaseModel):
    """Memory search request model"""
    query: str
    limit: int = 10
    threshold: float = 0.7
    filters: Dict[str, Any] = {}


class MemorySearchResponse(BaseModel):
    """Memory search response model"""
    results: List[Dict[str, Any]]
    total: int
    query: str


class KnowledgeNode(BaseModel):
    """Knowledge node model"""
    id: str
    label: str
    node_type: str
    properties: Dict[str, Any] = {}
    created_at: str


class KnowledgeEdge(BaseModel):
    """Knowledge edge model"""
    id: str
    source: str
    target: str
    relationship: str
    properties: Dict[str, Any] = {}
    created_at: str


def get_current_user(token: str = Depends(verify_token)) -> TokenData:
    """Get current user from token"""
    return token


@router.post("/store", response_model=Dict[str, str])
async def store_memory(
    content: str,
    metadata: Dict[str, Any] = {},
    current_user: TokenData = Depends(get_current_user)
):
    """Store memory item"""
    try:
        vector_store = VectorStore()
        memory_id = vector_store.store_memory(
            content=content,
            metadata=metadata,
            user_id=current_user.user_id
        )
        
        return {"memory_id": memory_id, "message": "Memory stored successfully"}
        
    except Exception as e:
        logger.error(f"Error storing memory: {e}")
        raise HTTPException(status_code=500, detail="Failed to store memory")


@router.post("/search", response_model=MemorySearchResponse)
async def search_memory(
    search_request: MemorySearchRequest,
    current_user: TokenData = Depends(get_current_user)
):
    """Search memory"""
    try:
        vector_store = VectorStore()
        results = vector_store.search_memory(
            query=search_request.query,
            user_id=current_user.user_id,
            limit=search_request.limit,
            threshold=search_request.threshold,
            filters=search_request.filters
        )
        
        return MemorySearchResponse(
            results=results,
            total=len(results),
            query=search_request.query
        )
        
    except Exception as e:
        logger.error(f"Error searching memory: {e}")
        raise HTTPException(status_code=500, detail="Failed to search memory")


@router.get("/{memory_id}", response_model=MemoryItem)
async def get_memory(
    memory_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Get specific memory item"""
    try:
        vector_store = VectorStore()
        memory = vector_store.get_memory(memory_id, current_user.user_id)
        
        if not memory:
            raise HTTPException(status_code=404, detail="Memory not found")
        
        return MemoryItem(
            id=memory["id"],
            content=memory["content"],
            metadata=memory["metadata"],
            created_at=memory["created_at"],
            updated_at=memory["updated_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting memory: {e}")
        raise HTTPException(status_code=500, detail="Failed to get memory")


@router.put("/{memory_id}")
async def update_memory(
    memory_id: str,
    content: str,
    metadata: Dict[str, Any] = {},
    current_user: TokenData = Depends(get_current_user)
):
    """Update memory item"""
    try:
        vector_store = VectorStore()
        success = vector_store.update_memory(
            memory_id=memory_id,
            content=content,
            metadata=metadata,
            user_id=current_user.user_id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")
        
        return {"message": "Memory updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating memory: {e}")
        raise HTTPException(status_code=500, detail="Failed to update memory")


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Delete memory item"""
    try:
        vector_store = VectorStore()
        success = vector_store.delete_memory(memory_id, current_user.user_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")
        
        return {"message": "Memory deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting memory: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete memory")


@router.get("/", response_model=List[MemoryItem])
async def list_memories(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: TokenData = Depends(get_current_user)
):
    """List user memories"""
    try:
        vector_store = VectorStore()
        memories = vector_store.list_memories(
            user_id=current_user.user_id,
            limit=limit,
            offset=offset
        )
        
        memory_items = []
        for memory in memories:
            memory_items.append(MemoryItem(
                id=memory["id"],
                content=memory["content"],
                metadata=memory["metadata"],
                created_at=memory["created_at"],
                updated_at=memory["updated_at"]
            ))
        
        return memory_items
        
    except Exception as e:
        logger.error(f"Error listing memories: {e}")
        raise HTTPException(status_code=500, detail="Failed to list memories")


@router.post("/knowledge/nodes", response_model=Dict[str, str])
async def create_knowledge_node(
    label: str,
    node_type: str,
    properties: Dict[str, Any] = {},
    current_user: TokenData = Depends(get_current_user)
):
    """Create knowledge node"""
    try:
        knowledge_graph = KnowledgeGraph()
        node_id = knowledge_graph.create_node(
            label=label,
            node_type=node_type,
            properties=properties,
            user_id=current_user.user_id
        )
        
        return {"node_id": node_id, "message": "Knowledge node created successfully"}
        
    except Exception as e:
        logger.error(f"Error creating knowledge node: {e}")
        raise HTTPException(status_code=500, detail="Failed to create knowledge node")


@router.post("/knowledge/edges", response_model=Dict[str, str])
async def create_knowledge_edge(
    source: str,
    target: str,
    relationship: str,
    properties: Dict[str, Any] = {},
    current_user: TokenData = Depends(get_current_user)
):
    """Create knowledge edge"""
    try:
        knowledge_graph = KnowledgeGraph()
        edge_id = knowledge_graph.create_edge(
            source=source,
            target=target,
            relationship=relationship,
            properties=properties,
            user_id=current_user.user_id
        )
        
        return {"edge_id": edge_id, "message": "Knowledge edge created successfully"}
        
    except Exception as e:
        logger.error(f"Error creating knowledge edge: {e}")
        raise HTTPException(status_code=500, detail="Failed to create knowledge edge")


@router.get("/knowledge/nodes", response_model=List[KnowledgeNode])
async def list_knowledge_nodes(
    node_type: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100),
    current_user: TokenData = Depends(get_current_user)
):
    """List knowledge nodes"""
    try:
        knowledge_graph = KnowledgeGraph()
        nodes = knowledge_graph.list_nodes(
            user_id=current_user.user_id,
            node_type=node_type,
            limit=limit
        )
        
        knowledge_nodes = []
        for node in nodes:
            knowledge_nodes.append(KnowledgeNode(
                id=node["id"],
                label=node["label"],
                node_type=node["node_type"],
                properties=node["properties"],
                created_at=node["created_at"]
            ))
        
        return knowledge_nodes
        
    except Exception as e:
        logger.error(f"Error listing knowledge nodes: {e}")
        raise HTTPException(status_code=500, detail="Failed to list knowledge nodes")


@router.get("/knowledge/edges", response_model=List[KnowledgeEdge])
async def list_knowledge_edges(
    source: Optional[str] = None,
    target: Optional[str] = None,
    relationship: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100),
    current_user: TokenData = Depends(get_current_user)
):
    """List knowledge edges"""
    try:
        knowledge_graph = KnowledgeGraph()
        edges = knowledge_graph.list_edges(
            user_id=current_user.user_id,
            source=source,
            target=target,
            relationship=relationship,
            limit=limit
        )
        
        knowledge_edges = []
        for edge in edges:
            knowledge_edges.append(KnowledgeEdge(
                id=edge["id"],
                source=edge["source"],
                target=edge["target"],
                relationship=edge["relationship"],
                properties=edge["properties"],
                created_at=edge["created_at"]
            ))
        
        return knowledge_edges
        
    except Exception as e:
        logger.error(f"Error listing knowledge edges: {e}")
        raise HTTPException(status_code=500, detail="Failed to list knowledge edges")


@router.get("/knowledge/graph")
async def get_knowledge_graph(
    current_user: TokenData = Depends(get_current_user)
):
    """Get knowledge graph structure"""
    try:
        knowledge_graph = KnowledgeGraph()
        graph_data = knowledge_graph.get_graph_structure(current_user.user_id)
        
        return graph_data
        
    except Exception as e:
        logger.error(f"Error getting knowledge graph: {e}")
        raise HTTPException(status_code=500, detail="Failed to get knowledge graph")


@router.post("/knowledge/query")
async def query_knowledge_graph(
    query: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Query knowledge graph"""
    try:
        knowledge_graph = KnowledgeGraph()
        results = knowledge_graph.query_graph(
            query=query,
            user_id=current_user.user_id
        )
        
        return {"results": results, "query": query}
        
    except Exception as e:
        logger.error(f"Error querying knowledge graph: {e}")
        raise HTTPException(status_code=500, detail="Failed to query knowledge graph")


@router.get("/stats")
async def get_memory_stats(current_user: TokenData = Depends(get_current_user)):
    """Get memory statistics"""
    try:
        vector_store = VectorStore()
        knowledge_graph = KnowledgeGraph()
        
        memory_stats = vector_store.get_stats(current_user.user_id)
        graph_stats = knowledge_graph.get_stats(current_user.user_id)
        
        return {
            "memory": memory_stats,
            "knowledge_graph": graph_stats
        }
        
    except Exception as e:
        logger.error(f"Error getting memory stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get memory stats")