"""
Knowledge Graph for Atulya Tantra AGI
Knowledge representation and reasoning using NetworkX
"""

import uuid
import json
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime
from dataclasses import dataclass

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    nx = None

from ..config.logging import get_logger
from ..config.exceptions import MemoryError, ValidationError

logger = get_logger(__name__)


@dataclass
class KnowledgeNode:
    """Knowledge graph node"""
    id: str
    label: str
    node_type: str
    properties: Dict[str, Any]
    created_at: str
    updated_at: str
    user_id: str


@dataclass
class KnowledgeEdge:
    """Knowledge graph edge"""
    id: str
    source: str
    target: str
    relationship: str
    properties: Dict[str, Any]
    created_at: str
    user_id: str


class KnowledgeGraph:
    """Knowledge graph implementation"""
    
    def __init__(self, user_id: str = None):
        self.user_id = user_id or "anonymous"
        self.graph = None
        self.nodes: Dict[str, KnowledgeNode] = {}
        self.edges: Dict[str, KnowledgeEdge] = {}
        
        if not NETWORKX_AVAILABLE:
            logger.warning("NetworkX not available, using mock implementation")
            self._initialize_mock()
        else:
            self._initialize_networkx()
    
    def _initialize_networkx(self):
        """Initialize NetworkX graph"""
        try:
            self.graph = nx.DiGraph()
            logger.info("Initialized NetworkX knowledge graph")
        except Exception as e:
            logger.error(f"Error initializing NetworkX: {e}")
            self._initialize_mock()
    
    def _initialize_mock(self):
        """Initialize mock knowledge graph"""
        self.graph = None
        logger.info("Initialized mock knowledge graph")
    
    async def create_node(
        self,
        label: str,
        node_type: str,
        properties: Dict[str, Any] = None,
        user_id: str = None
    ) -> str:
        """Create a new knowledge node"""
        try:
            node_id = str(uuid.uuid4())
            current_time = datetime.now().isoformat()
            
            node = KnowledgeNode(
                id=node_id,
                label=label,
                node_type=node_type,
                properties=properties or {},
                created_at=current_time,
                updated_at=current_time,
                user_id=user_id or self.user_id
            )
            
            self.nodes[node_id] = node
            
            if self.graph:
                self.graph.add_node(
                    node_id,
                    label=label,
                    node_type=node_type,
                    properties=node.properties,
                    created_at=current_time,
                    updated_at=current_time,
                    user_id=node.user_id
                )
            
            logger.info(f"Created knowledge node: {node_id}")
            return node_id
            
        except Exception as e:
            logger.error(f"Error creating node: {e}")
            raise MemoryError(f"Failed to create node: {e}")
    
    async def create_edge(
        self,
        source: str,
        target: str,
        relationship: str,
        properties: Dict[str, Any] = None,
        user_id: str = None
    ) -> str:
        """Create a new knowledge edge"""
        try:
            # Check if source and target nodes exist
            if source not in self.nodes:
                raise ValidationError(f"Source node not found: {source}")
            if target not in self.nodes:
                raise ValidationError(f"Target node not found: {target}")
            
            edge_id = str(uuid.uuid4())
            current_time = datetime.now().isoformat()
            
            edge = KnowledgeEdge(
                id=edge_id,
                source=source,
                target=target,
                relationship=relationship,
                properties=properties or {},
                created_at=current_time,
                user_id=user_id or self.user_id
            )
            
            self.edges[edge_id] = edge
            
            if self.graph:
                self.graph.add_edge(
                    source,
                    target,
                    id=edge_id,
                    relationship=relationship,
                    properties=edge.properties,
                    created_at=current_time,
                    user_id=edge.user_id
                )
            
            logger.info(f"Created knowledge edge: {edge_id}")
            return edge_id
            
        except Exception as e:
            logger.error(f"Error creating edge: {e}")
            raise MemoryError(f"Failed to create edge: {e}")
    
    async def get_node(self, node_id: str, user_id: str = None) -> Optional[KnowledgeNode]:
        """Get a knowledge node by ID"""
        try:
            if node_id not in self.nodes:
                return None
            
            node = self.nodes[node_id]
            if user_id and node.user_id != user_id:
                return None
            
            return node
            
        except Exception as e:
            logger.error(f"Error getting node: {e}")
            return None
    
    async def get_edge(self, edge_id: str, user_id: str = None) -> Optional[KnowledgeEdge]:
        """Get a knowledge edge by ID"""
        try:
            if edge_id not in self.edges:
                return None
            
            edge = self.edges[edge_id]
            if user_id and edge.user_id != user_id:
                return None
            
            return edge
            
        except Exception as e:
            logger.error(f"Error getting edge: {e}")
            return None
    
    async def update_node(
        self,
        node_id: str,
        label: str = None,
        properties: Dict[str, Any] = None,
        user_id: str = None
    ) -> bool:
        """Update a knowledge node"""
        try:
            if node_id not in self.nodes:
                return False
            
            node = self.nodes[node_id]
            if user_id and node.user_id != user_id:
                return False
            
            # Update node properties
            if label:
                node.label = label
            if properties:
                node.properties.update(properties)
            
            node.updated_at = datetime.now().isoformat()
            
            # Update in graph
            if self.graph and node_id in self.graph.nodes:
                if label:
                    self.graph.nodes[node_id]["label"] = label
                if properties:
                    self.graph.nodes[node_id]["properties"].update(properties)
                self.graph.nodes[node_id]["updated_at"] = node.updated_at
            
            logger.info(f"Updated knowledge node: {node_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating node: {e}")
            return False
    
    async def update_edge(
        self,
        edge_id: str,
        relationship: str = None,
        properties: Dict[str, Any] = None,
        user_id: str = None
    ) -> bool:
        """Update a knowledge edge"""
        try:
            if edge_id not in self.edges:
                return False
            
            edge = self.edges[edge_id]
            if user_id and edge.user_id != user_id:
                return False
            
            # Update edge properties
            if relationship:
                edge.relationship = relationship
            if properties:
                edge.properties.update(properties)
            
            # Update in graph
            if self.graph:
                for source, target, data in self.graph.edges(data=True):
                    if data.get("id") == edge_id:
                        if relationship:
                            data["relationship"] = relationship
                        if properties:
                            data["properties"].update(properties)
                        break
            
            logger.info(f"Updated knowledge edge: {edge_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating edge: {e}")
            return False
    
    async def delete_node(self, node_id: str, user_id: str = None) -> bool:
        """Delete a knowledge node"""
        try:
            if node_id not in self.nodes:
                return False
            
            node = self.nodes[node_id]
            if user_id and node.user_id != user_id:
                return False
            
            # Delete associated edges
            edges_to_delete = []
            for edge_id, edge in self.edges.items():
                if edge.source == node_id or edge.target == node_id:
                    edges_to_delete.append(edge_id)
            
            for edge_id in edges_to_delete:
                await self.delete_edge(edge_id, user_id)
            
            # Delete node
            del self.nodes[node_id]
            
            if self.graph and node_id in self.graph.nodes:
                self.graph.remove_node(node_id)
            
            logger.info(f"Deleted knowledge node: {node_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting node: {e}")
            return False
    
    async def delete_edge(self, edge_id: str, user_id: str = None) -> bool:
        """Delete a knowledge edge"""
        try:
            if edge_id not in self.edges:
                return False
            
            edge = self.edges[edge_id]
            if user_id and edge.user_id != user_id:
                return False
            
            # Delete edge
            del self.edges[edge_id]
            
            if self.graph:
                for source, target, data in self.graph.edges(data=True):
                    if data.get("id") == edge_id:
                        self.graph.remove_edge(source, target)
                        break
            
            logger.info(f"Deleted knowledge edge: {edge_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting edge: {e}")
            return False
    
    async def list_nodes(
        self,
        user_id: str = None,
        node_type: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[KnowledgeNode]:
        """List knowledge nodes with filters"""
        try:
            filtered_nodes = []
            
            for node in self.nodes.values():
                # Check user filter
                if user_id and node.user_id != user_id:
                    continue
                
                # Check node type filter
                if node_type and node.node_type != node_type:
                    continue
                
                filtered_nodes.append(node)
            
            # Sort by created_at and apply pagination
            filtered_nodes.sort(key=lambda x: x.created_at, reverse=True)
            return filtered_nodes[offset:offset + limit]
            
        except Exception as e:
            logger.error(f"Error listing nodes: {e}")
            return []
    
    async def list_edges(
        self,
        user_id: str = None,
        source: str = None,
        target: str = None,
        relationship: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[KnowledgeEdge]:
        """List knowledge edges with filters"""
        try:
            filtered_edges = []
            
            for edge in self.edges.values():
                # Check user filter
                if user_id and edge.user_id != user_id:
                    continue
                
                # Check source filter
                if source and edge.source != source:
                    continue
                
                # Check target filter
                if target and edge.target != target:
                    continue
                
                # Check relationship filter
                if relationship and edge.relationship != relationship:
                    continue
                
                filtered_edges.append(edge)
            
            # Sort by created_at and apply pagination
            filtered_edges.sort(key=lambda x: x.created_at, reverse=True)
            return filtered_edges[offset:offset + limit]
            
        except Exception as e:
            logger.error(f"Error listing edges: {e}")
            return []
    
    async def get_graph_structure(self, user_id: str = None) -> Dict[str, Any]:
        """Get graph structure for visualization"""
        try:
            nodes = []
            edges = []
            
            # Get nodes
            for node in self.nodes.values():
                if user_id and node.user_id != user_id:
                    continue
                
                nodes.append({
                    "id": node.id,
                    "label": node.label,
                    "type": node.node_type,
                    "properties": node.properties,
                    "created_at": node.created_at
                })
            
            # Get edges
            for edge in self.edges.values():
                if user_id and edge.user_id != user_id:
                    continue
                
                edges.append({
                    "id": edge.id,
                    "source": edge.source,
                    "target": edge.target,
                    "relationship": edge.relationship,
                    "properties": edge.properties,
                    "created_at": edge.created_at
                })
            
            return {
                "nodes": nodes,
                "edges": edges,
                "node_count": len(nodes),
                "edge_count": len(edges),
                "user_id": user_id,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting graph structure: {e}")
            return {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0}
    
    async def query_graph(self, query: str, user_id: str = None) -> List[Dict[str, Any]]:
        """Query the knowledge graph"""
        try:
            # Simple text-based query
            results = []
            
            # Search nodes
            for node in self.nodes.values():
                if user_id and node.user_id != user_id:
                    continue
                
                if query.lower() in node.label.lower() or query.lower() in str(node.properties).lower():
                    results.append({
                        "type": "node",
                        "id": node.id,
                        "label": node.label,
                        "node_type": node.node_type,
                        "properties": node.properties,
                        "relevance": self._calculate_relevance(query, node.label, node.properties)
                    })
            
            # Search edges
            for edge in self.edges.values():
                if user_id and edge.user_id != user_id:
                    continue
                
                if query.lower() in edge.relationship.lower() or query.lower() in str(edge.properties).lower():
                    results.append({
                        "type": "edge",
                        "id": edge.id,
                        "source": edge.source,
                        "target": edge.target,
                        "relationship": edge.relationship,
                        "properties": edge.properties,
                        "relevance": self._calculate_relevance(query, edge.relationship, edge.properties)
                    })
            
            # Sort by relevance
            results.sort(key=lambda x: x["relevance"], reverse=True)
            return results
            
        except Exception as e:
            logger.error(f"Error querying graph: {e}")
            return []
    
    async def find_path(
        self,
        source: str,
        target: str,
        max_length: int = 5,
        user_id: str = None
    ) -> List[List[str]]:
        """Find paths between nodes"""
        try:
            if not self.graph:
                return []
            
            # Filter graph by user
            filtered_graph = self._get_filtered_graph(user_id)
            
            if source not in filtered_graph.nodes or target not in filtered_graph.nodes:
                return []
            
            # Find all simple paths
            paths = list(nx.all_simple_paths(
                filtered_graph,
                source,
                target,
                cutoff=max_length
            ))
            
            return paths[:10]  # Limit to 10 paths
            
        except Exception as e:
            logger.error(f"Error finding path: {e}")
            return []
    
    async def get_neighbors(
        self,
        node_id: str,
        direction: str = "both",
        user_id: str = None
    ) -> List[Dict[str, Any]]:
        """Get neighbors of a node"""
        try:
            if node_id not in self.nodes:
                return []
            
            node = self.nodes[node_id]
            if user_id and node.user_id != user_id:
                return []
            
            neighbors = []
            
            for edge in self.edges.values():
                if user_id and edge.user_id != user_id:
                    continue
                
                if direction in ["in", "both"] and edge.target == node_id:
                    source_node = self.nodes.get(edge.source)
                    if source_node:
                        neighbors.append({
                            "node": source_node,
                            "edge": edge,
                            "direction": "in"
                        })
                
                if direction in ["out", "both"] and edge.source == node_id:
                    target_node = self.nodes.get(edge.target)
                    if target_node:
                        neighbors.append({
                            "node": target_node,
                            "edge": edge,
                            "direction": "out"
                        })
            
            return neighbors
            
        except Exception as e:
            logger.error(f"Error getting neighbors: {e}")
            return []
    
    async def get_stats(self, user_id: str = None) -> Dict[str, Any]:
        """Get knowledge graph statistics"""
        try:
            node_count = len([
                node for node in self.nodes.values()
                if not user_id or node.user_id == user_id
            ])
            
            edge_count = len([
                edge for edge in self.edges.values()
                if not user_id or edge.user_id == user_id
            ])
            
            # Count by node type
            node_types = {}
            for node in self.nodes.values():
                if user_id and node.user_id != user_id:
                    continue
                
                node_type = node.node_type
                node_types[node_type] = node_types.get(node_type, 0) + 1
            
            # Count by relationship type
            relationship_types = {}
            for edge in self.edges.values():
                if user_id and edge.user_id != user_id:
                    continue
                
                relationship = edge.relationship
                relationship_types[relationship] = relationship_types.get(relationship, 0) + 1
            
            return {
                "node_count": node_count,
                "edge_count": edge_count,
                "node_types": node_types,
                "relationship_types": relationship_types,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
    
    def _get_filtered_graph(self, user_id: str = None):
        """Get graph filtered by user"""
        if not self.graph:
            return nx.DiGraph()
        
        filtered_graph = nx.DiGraph()
        
        # Add nodes
        for node in self.nodes.values():
            if not user_id or node.user_id == user_id:
                filtered_graph.add_node(
                    node.id,
                    label=node.label,
                    node_type=node.node_type,
                    properties=node.properties
                )
        
        # Add edges
        for edge in self.edges.values():
            if not user_id or edge.user_id == user_id:
                if edge.source in filtered_graph.nodes and edge.target in filtered_graph.nodes:
                    filtered_graph.add_edge(
                        edge.source,
                        edge.target,
                        relationship=edge.relationship,
                        properties=edge.properties
                    )
        
        return filtered_graph
    
    def _calculate_relevance(self, query: str, text: str, properties: Dict[str, Any]) -> float:
        """Calculate relevance score for query"""
        try:
            query_lower = query.lower()
            text_lower = text.lower()
            
            # Simple relevance calculation
            if query_lower in text_lower:
                return 1.0
            
            # Check properties
            for value in properties.values():
                if isinstance(value, str) and query_lower in value.lower():
                    return 0.8
            
            # Check partial matches
            query_words = query_lower.split()
            text_words = text_lower.split()
            
            matches = sum(1 for word in query_words if word in text_words)
            if matches > 0:
                return matches / len(query_words)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating relevance: {e}")
            return 0.0


# Global knowledge graph instance
_knowledge_graph = None


def get_knowledge_graph(user_id: str = None) -> KnowledgeGraph:
    """Get global knowledge graph instance"""
    global _knowledge_graph
    if _knowledge_graph is None:
        _knowledge_graph = KnowledgeGraph(user_id)
    return _knowledge_graph


# Export public API
__all__ = [
    "KnowledgeNode",
    "KnowledgeEdge",
    "KnowledgeGraph",
    "get_knowledge_graph"
]