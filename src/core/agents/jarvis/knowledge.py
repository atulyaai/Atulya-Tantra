"""
Atulya Tantra - JARVIS Knowledge Management
Version: 2.5.0
Knowledge management system for personal knowledge base and learning
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import uuid
from collections import defaultdict
import hashlib
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeItem:
    """Knowledge item in personal knowledge base"""
    item_id: str
    user_id: str
    title: str
    content: str
    category: str
    tags: List[str]
    source: str  # "user_input", "conversation", "document", "web"
    confidence: float  # 0.0 to 1.0
    created_at: datetime
    updated_at: datetime
    access_count: int
    last_accessed: Optional[datetime]
    metadata: Dict[str, Any]


@dataclass
class LearningPattern:
    """Pattern learned from user interactions"""
    pattern_id: str
    user_id: str
    pattern_type: str  # "preference", "behavior", "knowledge_gap", "interest"
    description: str
    evidence: List[str]
    confidence: float
    created_at: datetime
    last_updated: datetime


@dataclass
class Document:
    """Document in knowledge base"""
    document_id: str
    user_id: str
    filename: str
    content: str
    content_type: str
    size_bytes: int
    upload_date: datetime
    last_accessed: Optional[datetime]
    tags: List[str]
    summary: Optional[str]
    key_points: List[str]
    metadata: Dict[str, Any]


class KnowledgeManager:
    """Knowledge management system for JARVIS"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.knowledge_items = {}  # item_id -> KnowledgeItem
        self.user_knowledge = defaultdict(list)  # user_id -> List[item_id]
        self.knowledge_index = defaultdict(set)  # keyword -> Set[item_id]
        self.documents = {}  # document_id -> Document
        self.user_documents = defaultdict(list)  # user_id -> List[document_id]
        self.learning_patterns = defaultdict(list)  # user_id -> List[LearningPattern]
        self.user_preferences = defaultdict(dict)  # user_id -> preferences
        
        logger.info("KnowledgeManager initialized")
    
    async def store_knowledge(
        self,
        user_id: str,
        title: str,
        content: str,
        category: str = "general",
        tags: List[str] = None,
        source: str = "user_input",
        confidence: float = 0.8
    ) -> str:
        """Store knowledge item in personal knowledge base"""
        
        item_id = str(uuid.uuid4())
        
        knowledge_item = KnowledgeItem(
            item_id=item_id,
            user_id=user_id,
            title=title,
            content=content,
            category=category,
            tags=tags or [],
            source=source,
            confidence=confidence,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            access_count=0,
            last_accessed=None,
            metadata={}
        )
        
        # Store knowledge item
        self.knowledge_items[item_id] = knowledge_item
        self.user_knowledge[user_id].append(item_id)
        
        # Index by keywords
        await self._index_knowledge_item(knowledge_item)
        
        # Learn from the knowledge
        await self._learn_from_knowledge(user_id, knowledge_item)
        
        logger.info(f"Stored knowledge item for user {user_id}: {title}")
        return item_id
    
    async def search_knowledge(
        self,
        user_id: str,
        query: str,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[KnowledgeItem]:
        """Search knowledge base for relevant information"""
        
        query_lower = query.lower()
        query_keywords = set(query_lower.split())
        
        # Get user's knowledge items
        user_item_ids = self.user_knowledge.get(user_id, [])
        
        matching_items = []
        
        for item_id in user_item_ids:
            if item_id not in self.knowledge_items:
                continue
            
            item = self.knowledge_items[item_id]
            
            # Filter by category
            if category and category != item.category:
                continue
            
            # Filter by tags
            if tags and not any(tag in item.tags for tag in tags):
                continue
            
            # Calculate relevance score
            relevance_score = await self._calculate_knowledge_relevance(item, query_keywords)
            
            if relevance_score > 0.1:  # Minimum relevance threshold
                matching_items.append((item, relevance_score))
        
        # Sort by relevance and confidence
        matching_items.sort(
            key=lambda x: (x[1] * 0.7 + x[0].confidence * 0.3),
            reverse=True
        )
        
        # Update access counts
        for item, _ in matching_items[:limit]:
            item.access_count += 1
            item.last_accessed = datetime.now()
        
        return [item for item, _ in matching_items[:limit]]
    
    async def store_document(
        self,
        user_id: str,
        filename: str,
        content: str,
        content_type: str,
        tags: List[str] = None
    ) -> str:
        """Store document in knowledge base"""
        
        document_id = str(uuid.uuid4())
        
        # Generate summary and key points
        summary = await self._generate_document_summary(content)
        key_points = await self._extract_key_points(content)
        
        document = Document(
            document_id=document_id,
            user_id=user_id,
            filename=filename,
            content=content,
            content_type=content_type,
            size_bytes=len(content.encode('utf-8')),
            upload_date=datetime.now(),
            last_accessed=None,
            tags=tags or [],
            summary=summary,
            key_points=key_points,
            metadata={}
        )
        
        # Store document
        self.documents[document_id] = document
        self.user_documents[user_id].append(document_id)
        
        # Extract and store knowledge from document
        await self._extract_knowledge_from_document(user_id, document)
        
        logger.info(f"Stored document for user {user_id}: {filename}")
        return document_id
    
    async def search_documents(
        self,
        user_id: str,
        query: str,
        content_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Document]:
        """Search documents in knowledge base"""
        
        query_lower = query.lower()
        user_document_ids = self.user_documents.get(user_id, [])
        
        matching_documents = []
        
        for document_id in user_document_ids:
            if document_id not in self.documents:
                continue
            
            document = self.documents[document_id]
            
            # Filter by content type
            if content_type and content_type != document.content_type:
                continue
            
            # Filter by tags
            if tags and not any(tag in document.tags for tag in tags):
                continue
            
            # Calculate relevance score
            relevance_score = await self._calculate_document_relevance(document, query_lower)
            
            if relevance_score > 0.1:
                matching_documents.append((document, relevance_score))
        
        # Sort by relevance
        matching_documents.sort(key=lambda x: x[1], reverse=True)
        
        # Update access counts
        for document, _ in matching_documents[:limit]:
            document.last_accessed = datetime.now()
        
        return [document for document, _ in matching_documents[:limit]]
    
    async def learn_from_interaction(
        self,
        user_id: str,
        interaction_type: str,
        content: str,
        context: Dict[str, Any]
    ):
        """Learn from user interactions"""
        
        # Extract learning patterns
        patterns = await self._extract_learning_patterns(user_id, interaction_type, content, context)
        
        for pattern in patterns:
            # Check if similar pattern already exists
            existing_pattern = self._find_similar_pattern(user_id, pattern)
            
            if existing_pattern:
                # Update existing pattern
                existing_pattern.evidence.append(content)
                existing_pattern.confidence = min(1.0, existing_pattern.confidence + 0.1)
                existing_pattern.last_updated = datetime.now()
            else:
                # Create new pattern
                pattern.pattern_id = str(uuid.uuid4())
                self.learning_patterns[user_id].append(pattern)
        
        # Update user preferences
        await self._update_user_preferences(user_id, interaction_type, content, context)
        
        logger.info(f"Learned from interaction for user {user_id}: {interaction_type}")
    
    async def get_user_knowledge_summary(self, user_id: str) -> Dict[str, Any]:
        """Get summary of user's knowledge base"""
        
        knowledge_items = [self.knowledge_items[item_id] for item_id in self.user_knowledge[user_id] 
                          if item_id in self.knowledge_items]
        documents = [self.documents[doc_id] for doc_id in self.user_documents[user_id] 
                    if doc_id in self.documents]
        patterns = self.learning_patterns[user_id]
        
        # Calculate statistics
        total_knowledge_items = len(knowledge_items)
        total_documents = len(documents)
        total_patterns = len(patterns)
        
        # Category distribution
        categories = defaultdict(int)
        for item in knowledge_items:
            categories[item.category] += 1
        
        # Most accessed items
        most_accessed = sorted(knowledge_items, key=lambda x: x.access_count, reverse=True)[:5]
        
        # Recent additions
        recent_items = sorted(knowledge_items, key=lambda x: x.created_at, reverse=True)[:5]
        
        # Learning patterns summary
        pattern_types = defaultdict(int)
        for pattern in patterns:
            pattern_types[pattern.pattern_type] += 1
        
        return {
            "user_id": user_id,
            "total_knowledge_items": total_knowledge_items,
            "total_documents": total_documents,
            "total_learning_patterns": total_patterns,
            "categories": dict(categories),
            "pattern_types": dict(pattern_types),
            "most_accessed_items": [
                {
                    "title": item.title,
                    "category": item.category,
                    "access_count": item.access_count,
                    "last_accessed": item.last_accessed.isoformat() if item.last_accessed else None
                }
                for item in most_accessed
            ],
            "recent_items": [
                {
                    "title": item.title,
                    "category": item.category,
                    "created_at": item.created_at.isoformat(),
                    "confidence": item.confidence
                }
                for item in recent_items
            ]
        }
    
    async def suggest_knowledge_gaps(
        self,
        user_id: str,
        context: Dict[str, Any]
    ) -> List[str]:
        """Suggest knowledge gaps based on user interactions"""
        
        gaps = []
        
        # Analyze recent interactions for knowledge gaps
        recent_patterns = self.learning_patterns[user_id][-10:]  # Last 10 patterns
        
        for pattern in recent_patterns:
            if pattern.pattern_type == "knowledge_gap":
                gaps.append(pattern.description)
        
        # Analyze conversation topics vs. stored knowledge
        user_knowledge_categories = set()
        for item_id in self.user_knowledge[user_id]:
            if item_id in self.knowledge_items:
                user_knowledge_categories.add(self.knowledge_items[item_id].category)
        
        # Common knowledge categories
        common_categories = {
            "programming", "technology", "science", "business", "health",
            "education", "arts", "sports", "travel", "cooking"
        }
        
        missing_categories = common_categories - user_knowledge_categories
        if missing_categories:
            gaps.append(f"Consider exploring topics in: {', '.join(list(missing_categories)[:3])}")
        
        return gaps[:5]  # Return top 5 suggestions
    
    async def _index_knowledge_item(self, item: KnowledgeItem):
        """Index knowledge item by keywords"""
        
        # Extract keywords from title and content
        text = f"{item.title} {item.content}".lower()
        keywords = set(text.split())
        
        # Remove common stop words
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        keywords = keywords - stop_words
        
        # Index by keywords
        for keyword in keywords:
            self.knowledge_index[keyword].add(item.item_id)
    
    async def _calculate_knowledge_relevance(
        self,
        item: KnowledgeItem,
        query_keywords: set
    ) -> float:
        """Calculate relevance score for knowledge item"""
        
        item_keywords = set(f"{item.title} {item.content}".lower().split())
        
        # Calculate keyword overlap
        overlap = len(query_keywords.intersection(item_keywords))
        total_keywords = len(query_keywords.union(item_keywords))
        
        if total_keywords == 0:
            return 0.0
        
        # Base relevance from keyword overlap
        keyword_relevance = overlap / total_keywords
        
        # Boost relevance based on confidence and access frequency
        confidence_boost = item.confidence * 0.2
        
        # Access frequency boost (items accessed more are more relevant)
        access_boost = min(0.3, item.access_count * 0.01)
        
        total_relevance = keyword_relevance + confidence_boost + access_boost
        
        return min(1.0, total_relevance)
    
    async def _calculate_document_relevance(
        self,
        document: Document,
        query: str
    ) -> float:
        """Calculate relevance score for document"""
        
        # Search in title, summary, and content
        searchable_text = f"{document.filename} {document.summary or ''} {document.content}".lower()
        
        # Simple keyword matching
        query_words = query.split()
        matches = sum(1 for word in query_words if word in searchable_text)
        
        if not query_words:
            return 0.0
        
        return matches / len(query_words)
    
    async def _generate_document_summary(self, content: str) -> str:
        """Generate summary of document content"""
        
        # Simple summary generation - first few sentences
        sentences = content.split('.')
        summary = '. '.join(sentences[:3])
        
        if len(summary) > 200:
            summary = summary[:197] + "..."
        
        return summary
    
    async def _extract_key_points(self, content: str) -> List[str]:
        """Extract key points from document content"""
        
        # Simple key point extraction - sentences with important keywords
        sentences = content.split('.')
        key_points = []
        
        important_keywords = ["important", "key", "main", "primary", "essential", "critical"]
        
        for sentence in sentences:
            if any(keyword in sentence.lower() for keyword in important_keywords):
                key_points.append(sentence.strip())
                if len(key_points) >= 5:  # Limit to 5 key points
                    break
        
        return key_points
    
    async def _extract_knowledge_from_document(self, user_id: str, document: Document):
        """Extract and store knowledge from document"""
        
        # Simple knowledge extraction - store document summary as knowledge
        if document.summary:
            await self.store_knowledge(
                user_id=user_id,
                title=f"Document: {document.filename}",
                content=document.summary,
                category="document",
                tags=document.tags,
                source="document",
                confidence=0.7
            )
        
        # Store key points as separate knowledge items
        for i, key_point in enumerate(document.key_points):
            await self.store_knowledge(
                user_id=user_id,
                title=f"{document.filename} - Key Point {i+1}",
                content=key_point,
                category="document_key_point",
                tags=document.tags,
                source="document",
                confidence=0.6
            )
    
    async def _learn_from_knowledge(self, user_id: str, knowledge_item: KnowledgeItem):
        """Learn patterns from knowledge item"""
        
        # Extract preferences from knowledge
        if "prefer" in knowledge_item.content.lower() or "like" in knowledge_item.content.lower():
            pattern = LearningPattern(
                pattern_id="",  # Will be set when stored
                user_id=user_id,
                pattern_type="preference",
                description=f"User preference related to {knowledge_item.category}",
                evidence=[knowledge_item.content],
                confidence=0.7,
                created_at=datetime.now(),
                last_updated=datetime.now()
            )
            self.learning_patterns[user_id].append(pattern)
    
    async def _extract_learning_patterns(
        self,
        user_id: str,
        interaction_type: str,
        content: str,
        context: Dict[str, Any]
    ) -> List[LearningPattern]:
        """Extract learning patterns from interaction"""
        
        patterns = []
        
        # Detect preference patterns
        if any(word in content.lower() for word in ["prefer", "like", "love", "hate", "dislike"]):
            pattern = LearningPattern(
                pattern_id="",  # Will be set when stored
                user_id=user_id,
                pattern_type="preference",
                description=f"User preference in {interaction_type}",
                evidence=[content],
                confidence=0.6,
                created_at=datetime.now(),
                last_updated=datetime.now()
            )
            patterns.append(pattern)
        
        # Detect behavior patterns
        if interaction_type in ["repeated_action", "routine"]:
            pattern = LearningPattern(
                pattern_id="",  # Will be set when stored
                user_id=user_id,
                pattern_type="behavior",
                description=f"Behavior pattern in {interaction_type}",
                evidence=[content],
                confidence=0.8,
                created_at=datetime.now(),
                last_updated=datetime.now()
            )
            patterns.append(pattern)
        
        # Detect knowledge gaps
        if any(word in content.lower() for word in ["don't know", "unclear", "confused", "help me understand"]):
            pattern = LearningPattern(
                pattern_id="",  # Will be set when stored
                user_id=user_id,
                pattern_type="knowledge_gap",
                description=f"Knowledge gap in {interaction_type}",
                evidence=[content],
                confidence=0.7,
                created_at=datetime.now(),
                last_updated=datetime.now()
            )
            patterns.append(pattern)
        
        return patterns
    
    def _find_similar_pattern(self, user_id: str, new_pattern: LearningPattern) -> Optional[LearningPattern]:
        """Find similar existing pattern"""
        
        for pattern in self.learning_patterns[user_id]:
            if (pattern.pattern_type == new_pattern.pattern_type and
                pattern.description == new_pattern.description):
                return pattern
        
        return None
    
    async def _update_user_preferences(
        self,
        user_id: str,
        interaction_type: str,
        content: str,
        context: Dict[str, Any]
    ):
        """Update user preferences based on interaction"""
        
        # Simple preference extraction
        preferences = self.user_preferences[user_id]
        
        # Extract communication style preferences
        if "formal" in content.lower():
            preferences["communication_style"] = "formal"
        elif "casual" in content.lower():
            preferences["communication_style"] = "casual"
        
        # Extract topic interests
        if "interested in" in content.lower():
            # Extract topic after "interested in"
            parts = content.lower().split("interested in")
            if len(parts) > 1:
                topic = parts[1].split()[0]  # First word after "interested in"
                if "interests" not in preferences:
                    preferences["interests"] = []
                if topic not in preferences["interests"]:
                    preferences["interests"].append(topic)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of knowledge manager"""
        return {
            "knowledge_manager": True,
            "total_knowledge_items": len(self.knowledge_items),
            "total_documents": len(self.documents),
            "active_users": len(self.user_knowledge),
            "total_learning_patterns": sum(len(patterns) for patterns in self.learning_patterns.values()),
            "indexed_keywords": len(self.knowledge_index)
        }
