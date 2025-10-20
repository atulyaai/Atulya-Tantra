"""
Atulya Tantra - Semantic Memory System
Version: 2.5.0
Semantic memory for storing and retrieving facts, concepts, and relationships
"""

import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import json
import uuid
from collections import defaultdict
import asyncio
import networkx as nx

logger = logging.getLogger(__name__)


@dataclass
class SemanticFact:
    """Semantic memory fact"""
    fact_id: str
    subject: str
    predicate: str
    object: str
    confidence: float  # 0.0 to 1.0
    source: str  # "user", "inferred", "external"
    timestamp: datetime
    metadata: Dict[str, Any]


@dataclass
class Concept:
    """Semantic concept"""
    concept_id: str
    name: str
    definition: str
    attributes: Dict[str, Any]
    relationships: Dict[str, List[str]]  # relationship_type -> List[related_concepts]
    confidence: float
    last_updated: datetime


@dataclass
class Relationship:
    """Relationship between concepts"""
    relationship_id: str
    source_concept: str
    target_concept: str
    relationship_type: str
    strength: float  # 0.0 to 1.0
    bidirectional: bool
    metadata: Dict[str, Any]


class SemanticMemory:
    """Semantic memory system for facts, concepts, and relationships"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.facts = {}  # fact_id -> SemanticFact
        self.concepts = {}  # concept_id -> Concept
        self.relationships = {}  # relationship_id -> Relationship
        self.knowledge_graph = nx.DiGraph()
        self.fact_index = defaultdict(set)  # keyword -> Set[fact_id]
        self.concept_index = defaultdict(set)  # keyword -> Set[concept_id]
        self.confidence_threshold = 0.5  # Minimum confidence to store
        
        logger.info("SemanticMemory initialized")
    
    async def store_fact(
        self,
        subject: str,
        predicate: str,
        object: str,
        confidence: float,
        source: str = "user",
        metadata: Dict[str, Any] = None
    ) -> str:
        """Store a semantic fact"""
        
        # Only store if confidence is above threshold
        if confidence < self.confidence_threshold:
            return None
        
        fact_id = str(uuid.uuid4())
        
        fact = SemanticFact(
            fact_id=fact_id,
            subject=subject,
            predicate=predicate,
            object=object,
            confidence=confidence,
            source=source,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        # Store fact
        self.facts[fact_id] = fact
        
        # Index fact
        await self._index_fact(fact)
        
        # Update knowledge graph
        await self._update_knowledge_graph_with_fact(fact)
        
        logger.info(f"Stored semantic fact: {subject} {predicate} {object} (confidence: {confidence:.2f})")
        return fact_id
    
    async def store_concept(
        self,
        name: str,
        definition: str,
        attributes: Dict[str, Any] = None,
        confidence: float = 0.8,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Store a semantic concept"""
        
        concept_id = str(uuid.uuid4())
        
        concept = Concept(
            concept_id=concept_id,
            name=name,
            definition=definition,
            attributes=attributes or {},
            relationships={},
            confidence=confidence,
            last_updated=datetime.now()
        )
        
        # Store concept
        self.concepts[concept_id] = concept
        
        # Index concept
        await self._index_concept(concept)
        
        # Add to knowledge graph
        self.knowledge_graph.add_node(concept_id, **concept.__dict__)
        
        logger.info(f"Stored semantic concept: {name} (confidence: {confidence:.2f})")
        return concept_id
    
    async def create_relationship(
        self,
        source_concept: str,
        target_concept: str,
        relationship_type: str,
        strength: float = 0.8,
        bidirectional: bool = False,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Create a relationship between concepts"""
        
        relationship_id = str(uuid.uuid4())
        
        relationship = Relationship(
            relationship_id=relationship_id,
            source_concept=source_concept,
            target_concept=target_concept,
            relationship_type=relationship_type,
            strength=strength,
            bidirectional=bidirectional,
            metadata=metadata or {}
        )
        
        # Store relationship
        self.relationships[relationship_id] = relationship
        
        # Update knowledge graph
        self.knowledge_graph.add_edge(
            source_concept, target_concept,
            relationship_type=relationship_type,
            strength=strength,
            bidirectional=bidirectional,
            relationship_id=relationship_id
        )
        
        # If bidirectional, add reverse edge
        if bidirectional:
            self.knowledge_graph.add_edge(
                target_concept, source_concept,
                relationship_type=relationship_type,
                strength=strength,
                bidirectional=bidirectional,
                relationship_id=relationship_id
            )
        
        # Update concept relationships
        if source_concept in self.concepts:
            if relationship_type not in self.concepts[source_concept].relationships:
                self.concepts[source_concept].relationships[relationship_type] = []
            self.concepts[source_concept].relationships[relationship_type].append(target_concept)
        
        if target_concept in self.concepts and bidirectional:
            if relationship_type not in self.concepts[target_concept].relationships:
                self.concepts[target_concept].relationships[relationship_type] = []
            self.concepts[target_concept].relationships[relationship_type].append(source_concept)
        
        logger.info(f"Created relationship: {source_concept} --{relationship_type}--> {target_concept}")
        return relationship_id
    
    async def query_facts(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        object: Optional[str] = None,
        min_confidence: float = 0.5,
        limit: int = 10
    ) -> List[SemanticFact]:
        """Query facts based on subject, predicate, or object"""
        
        matching_facts = []
        
        for fact in self.facts.values():
            if fact.confidence < min_confidence:
                continue
            
            # Check if fact matches query criteria
            matches = True
            
            if subject and subject.lower() not in fact.subject.lower():
                matches = False
            
            if predicate and predicate.lower() not in fact.predicate.lower():
                matches = False
            
            if object and object.lower() not in fact.object.lower():
                matches = False
            
            if matches:
                matching_facts.append(fact)
        
        # Sort by confidence
        matching_facts.sort(key=lambda x: x.confidence, reverse=True)
        
        return matching_facts[:limit]
    
    async def search_concepts(
        self,
        query: str,
        min_confidence: float = 0.5,
        limit: int = 10
    ) -> List[Concept]:
        """Search for concepts by name or definition"""
        
        query_lower = query.lower()
        matching_concepts = []
        
        for concept in self.concepts.values():
            if concept.confidence < min_confidence:
                continue
            
            # Check if query matches concept name or definition
            if (query_lower in concept.name.lower() or 
                query_lower in concept.definition.lower()):
                matching_concepts.append(concept)
        
        # Sort by confidence and relevance
        matching_concepts.sort(key=lambda x: x.confidence, reverse=True)
        
        return matching_concepts[:limit]
    
    async def find_related_concepts(
        self,
        concept_name: str,
        relationship_type: Optional[str] = None,
        max_depth: int = 2
    ) -> List[Tuple[str, str, float]]:
        """Find concepts related to a given concept"""
        
        related_concepts = []
        
        # Find concept ID
        concept_id = None
        for cid, concept in self.concepts.items():
            if concept.name.lower() == concept_name.lower():
                concept_id = cid
                break
        
        if not concept_id:
            return related_concepts
        
        # Use networkx to find related concepts
        try:
            if relationship_type:
                # Find specific relationship type
                for neighbor in self.knowledge_graph.neighbors(concept_id):
                    edge_data = self.knowledge_graph.get_edge_data(concept_id, neighbor)
                    if edge_data and edge_data.get('relationship_type') == relationship_type:
                        neighbor_name = self.concepts[neighbor].name if neighbor in self.concepts else neighbor
                        strength = edge_data.get('strength', 0.5)
                        related_concepts.append((neighbor_name, relationship_type, strength))
            else:
                # Find all related concepts
                for neighbor in self.knowledge_graph.neighbors(concept_id):
                    edge_data = self.knowledge_graph.get_edge_data(concept_id, neighbor)
                    if edge_data:
                        neighbor_name = self.concepts[neighbor].name if neighbor in self.concepts else neighbor
                        rel_type = edge_data.get('relationship_type', 'related')
                        strength = edge_data.get('strength', 0.5)
                        related_concepts.append((neighbor_name, rel_type, strength))
        
        except Exception as e:
            logger.error(f"Error finding related concepts: {e}")
        
        # Sort by strength
        related_concepts.sort(key=lambda x: x[2], reverse=True)
        
        return related_concepts
    
    async def infer_facts(
        self,
        new_fact: SemanticFact
    ) -> List[SemanticFact]:
        """Infer new facts from existing knowledge"""
        
        inferred_facts = []
        
        # Simple inference rules
        # Rule 1: Transitivity (if A is part of B and B is part of C, then A is part of C)
        if new_fact.predicate == "is_part_of":
            # Find facts where new_fact.object is the subject
            for fact in self.facts.values():
                if (fact.subject == new_fact.object and 
                    fact.predicate == "is_part_of" and
                    fact.confidence > 0.7):
                    
                    # Infer: new_fact.subject is_part_of fact.object
                    inferred_fact = SemanticFact(
                        fact_id=str(uuid.uuid4()),
                        subject=new_fact.subject,
                        predicate="is_part_of",
                        object=fact.object,
                        confidence=min(new_fact.confidence, fact.confidence) * 0.8,  # Reduce confidence for inference
                        source="inferred",
                        timestamp=datetime.now(),
                        metadata={"inference_rule": "transitivity", "source_facts": [new_fact.fact_id, fact.fact_id]}
                    )
                    
                    inferred_facts.append(inferred_fact)
        
        # Rule 2: Symmetry (if A is_similar_to B, then B is_similar_to A)
        if new_fact.predicate == "is_similar_to":
            inferred_fact = SemanticFact(
                fact_id=str(uuid.uuid4()),
                subject=new_fact.object,
                predicate="is_similar_to",
                object=new_fact.subject,
                confidence=new_fact.confidence * 0.9,  # High confidence for symmetry
                source="inferred",
                timestamp=datetime.now(),
                metadata={"inference_rule": "symmetry", "source_fact": new_fact.fact_id}
            )
            
            inferred_facts.append(inferred_fact)
        
        return inferred_facts
    
    async def get_knowledge_summary(self) -> Dict[str, Any]:
        """Get summary of stored knowledge"""
        
        return {
            "total_facts": len(self.facts),
            "total_concepts": len(self.concepts),
            "total_relationships": len(self.relationships),
            "knowledge_graph_nodes": self.knowledge_graph.number_of_nodes(),
            "knowledge_graph_edges": self.knowledge_graph.number_of_edges(),
            "fact_sources": {
                source: sum(1 for fact in self.facts.values() if fact.source == source)
                for source in set(fact.source for fact in self.facts.values())
            },
            "concept_categories": {
                name: len([c for c in self.concepts.values() if c.name.startswith(name.split()[0])])
                for name in set(c.name for c in self.concepts.values())
            },
            "relationship_types": {
                rel_type: sum(1 for rel in self.relationships.values() if rel.relationship_type == rel_type)
                for rel_type in set(rel.relationship_type for rel in self.relationships.values())
            }
        }
    
    async def _index_fact(self, fact: SemanticFact):
        """Index fact by keywords"""
        
        # Extract keywords from subject, predicate, and object
        text = f"{fact.subject} {fact.predicate} {fact.object}".lower()
        keywords = set(text.split())
        
        # Remove common stop words
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        keywords = keywords - stop_words
        
        # Index by keywords
        for keyword in keywords:
            self.fact_index[keyword].add(fact.fact_id)
    
    async def _index_concept(self, concept: Concept):
        """Index concept by keywords"""
        
        # Extract keywords from name and definition
        text = f"{concept.name} {concept.definition}".lower()
        keywords = set(text.split())
        
        # Remove common stop words
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        keywords = keywords - stop_words
        
        # Index by keywords
        for keyword in keywords:
            self.concept_index[keyword].add(concept.concept_id)
    
    async def _update_knowledge_graph_with_fact(self, fact: SemanticFact):
        """Update knowledge graph with a new fact"""
        
        # Create nodes for subject and object if they don't exist
        subject_id = f"fact_subject_{fact.subject}"
        object_id = f"fact_object_{fact.object}"
        
        if subject_id not in self.knowledge_graph:
            self.knowledge_graph.add_node(subject_id, name=fact.subject, type="fact_entity")
        
        if object_id not in self.knowledge_graph:
            self.knowledge_graph.add_node(object_id, name=fact.object, type="fact_entity")
        
        # Add edge for the relationship
        self.knowledge_graph.add_edge(
            subject_id, object_id,
            predicate=fact.predicate,
            confidence=fact.confidence,
            fact_id=fact.fact_id
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of semantic memory"""
        return {
            "semantic_memory": True,
            "total_facts": len(self.facts),
            "total_concepts": len(self.concepts),
            "total_relationships": len(self.relationships),
            "knowledge_graph_connected": nx.is_connected(self.knowledge_graph.to_undirected()) if self.knowledge_graph.number_of_nodes() > 0 else True,
            "confidence_threshold": self.confidence_threshold
        }
