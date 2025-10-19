"""
Atulya Tantra - Knowledge Graph
Version: 2.5.0
Knowledge graph for storing relationships and entities
"""

from typing import List, Dict, Optional, Any, Set
from dataclasses import dataclass
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeNode:
    """Knowledge graph node"""
    id: str
    node_type: str
    properties: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class KnowledgeGraph:
    """Knowledge graph using NetworkX for storing relationships"""
    
    def __init__(self):
        self.graph = None
        self._initialize()
    
    def _initialize(self):
        """Initialize NetworkX graph"""
        try:
            import networkx as nx
            self.graph = nx.DiGraph()
            logger.info("Knowledge graph initialized successfully")
        except ImportError:
            logger.warning("NetworkX not available, using simple dict-based graph")
            self.graph = None
    
    async def add_node(
        self,
        node_id: str,
        node_type: str,
        properties: Dict[str, Any]
    ) -> bool:
        """Add node to knowledge graph"""
        try:
            if self.graph is not None:
                # Using NetworkX
                import networkx as nx
                self.graph.add_node(
                    node_id,
                    node_type=node_type,
                    properties=properties,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
            else:
                # Simple dict-based storage
                if not hasattr(self, '_nodes'):
                    self._nodes = {}
                
                self._nodes[node_id] = {
                    'node_type': node_type,
                    'properties': properties,
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
            
            logger.info(f"Added node {node_id} of type {node_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add node {node_id}: {e}")
            return False
    
    async def add_edge(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add edge between nodes"""
        try:
            if self.graph is not None:
                # Using NetworkX
                self.graph.add_edge(
                    source_id,
                    target_id,
                    relationship_type=relationship_type,
                    properties=properties or {},
                    created_at=datetime.now()
                )
            else:
                # Simple dict-based storage
                if not hasattr(self, '_edges'):
                    self._edges = []
                
                self._edges.append({
                    'source': source_id,
                    'target': target_id,
                    'relationship_type': relationship_type,
                    'properties': properties or {},
                    'created_at': datetime.now()
                })
            
            logger.info(f"Added edge {source_id} -> {target_id} ({relationship_type})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add edge {source_id} -> {target_id}: {e}")
            return False
    
    async def query_graph(
        self,
        node_type: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        relationship_type: Optional[str] = None
    ) -> List[KnowledgeNode]:
        """Query knowledge graph for nodes matching criteria"""
        try:
            nodes = []
            
            if self.graph is not None:
                # Using NetworkX
                for node_id, data in self.graph.nodes(data=True):
                    if self._matches_criteria(data, node_type, properties):
                        nodes.append(KnowledgeNode(
                            id=node_id,
                            node_type=data.get('node_type', ''),
                            properties=data.get('properties', {}),
                            created_at=data.get('created_at', datetime.now()),
                            updated_at=data.get('updated_at', datetime.now())
                        ))
            else:
                # Simple dict-based storage
                if hasattr(self, '_nodes'):
                    for node_id, data in self._nodes.items():
                        if self._matches_criteria(data, node_type, properties):
                            nodes.append(KnowledgeNode(
                                id=node_id,
                                node_type=data.get('node_type', ''),
                                properties=data.get('properties', {}),
                                created_at=data.get('created_at', datetime.now()),
                                updated_at=data.get('updated_at', datetime.now())
                            ))
            
            logger.info(f"Found {len(nodes)} nodes matching criteria")
            return nodes
            
        except Exception as e:
            logger.error(f"Failed to query graph: {e}")
            return []
    
    def _matches_criteria(
        self,
        data: Dict[str, Any],
        node_type: Optional[str],
        properties: Optional[Dict[str, Any]]
    ) -> bool:
        """Check if node data matches query criteria"""
        # Check node type
        if node_type and data.get('node_type') != node_type:
            return False
        
        # Check properties
        if properties:
            node_properties = data.get('properties', {})
            for key, value in properties.items():
                if node_properties.get(key) != value:
                    return False
        
        return True
    
    async def remove_node(self, node_id: str) -> bool:
        """Remove node from knowledge graph"""
        try:
            if self.graph is not None:
                # Using NetworkX
                if self.graph.has_node(node_id):
                    self.graph.remove_node(node_id)
            else:
                # Simple dict-based storage
                if hasattr(self, '_nodes') and node_id in self._nodes:
                    del self._nodes[node_id]
                
                # Remove related edges
                if hasattr(self, '_edges'):
                    self._edges = [
                        edge for edge in self._edges
                        if edge['source'] != node_id and edge['target'] != node_id
                    ]
            
            logger.info(f"Removed node {node_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove node {node_id}: {e}")
            return False
    
    async def get_graph_stats(self) -> Dict[str, Any]:
        """Get knowledge graph statistics"""
        try:
            if self.graph is not None:
                # Using NetworkX
                return {
                    "status": "available",
                    "total_nodes": self.graph.number_of_nodes(),
                    "total_edges": self.graph.number_of_edges(),
                    "node_types": list(set(
                        data.get('node_type', 'unknown')
                        for _, data in self.graph.nodes(data=True)
                    ))
                }
            else:
                # Simple dict-based storage
                node_count = len(getattr(self, '_nodes', {}))
                edge_count = len(getattr(self, '_edges', []))
                node_types = list(set(
                    data.get('node_type', 'unknown')
                    for data in getattr(self, '_nodes', {}).values()
                ))
                
                return {
                    "status": "available",
                    "total_nodes": node_count,
                    "total_edges": edge_count,
                    "node_types": node_types
                }
                
        except Exception as e:
            logger.error(f"Failed to get graph stats: {e}")
            return {"status": "error", "error": str(e)}
