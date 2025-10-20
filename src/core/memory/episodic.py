"""
Atulya Tantra - Episodic Memory System
Version: 2.5.0
Episodic memory for storing and retrieving specific events and interactions
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import json
import uuid
from collections import defaultdict, deque
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class EpisodicEvent:
    """Episodic memory event"""
    event_id: str
    conversation_id: str
    user_id: str
    event_type: str  # "interaction", "achievement", "milestone", "important"
    content: str
    context: Dict[str, Any]
    importance_score: float  # 0.0 to 1.0
    emotional_weight: float  # 0.0 to 1.0
    timestamp: datetime
    metadata: Dict[str, Any]


@dataclass
class MemoryRetrieval:
    """Memory retrieval result"""
    event: EpisodicEvent
    relevance_score: float
    retrieval_reason: str
    context_match: Dict[str, Any]


class EpisodicMemory:
    """Episodic memory system for storing and retrieving specific events"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.events = {}  # event_id -> EpisodicEvent
        self.user_events = defaultdict(list)  # user_id -> List[event_id]
        self.conversation_events = defaultdict(list)  # conversation_id -> List[event_id]
        self.event_index = defaultdict(set)  # keyword -> Set[event_id]
        self.importance_threshold = 0.3  # Minimum importance to store
        self.max_events_per_user = 1000  # Maximum events to keep per user
        
        logger.info("EpisodicMemory initialized")
    
    async def store_event(
        self,
        conversation_id: str,
        user_id: str,
        event_type: str,
        content: str,
        context: Dict[str, Any],
        importance_score: float,
        emotional_weight: float = 0.5,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Store an episodic event"""
        
        # Only store if importance is above threshold
        if importance_score < self.importance_threshold:
            return None
        
        event_id = str(uuid.uuid4())
        
        event = EpisodicEvent(
            event_id=event_id,
            conversation_id=conversation_id,
            user_id=user_id,
            event_type=event_type,
            content=content,
            context=context,
            importance_score=importance_score,
            emotional_weight=emotional_weight,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        # Store event
        self.events[event_id] = event
        self.user_events[user_id].append(event_id)
        self.conversation_events[conversation_id].append(event_id)
        
        # Index by keywords
        await self._index_event(event)
        
        # Cleanup old events if needed
        await self._cleanup_user_events(user_id)
        
        logger.info(f"Stored episodic event {event_id} for user {user_id} (importance: {importance_score:.2f})")
        return event_id
    
    async def retrieve_relevant_events(
        self,
        user_id: str,
        query: str,
        event_types: Optional[List[str]] = None,
        limit: int = 5,
        min_importance: float = 0.3
    ) -> List[MemoryRetrieval]:
        """Retrieve relevant episodic events for a query"""
        
        relevant_events = []
        query_lower = query.lower()
        query_keywords = set(query_lower.split())
        
        # Get user's events
        user_event_ids = self.user_events.get(user_id, [])
        
        for event_id in user_event_ids:
            if event_id not in self.events:
                continue
            
            event = self.events[event_id]
            
            # Filter by event type if specified
            if event_types and event.event_type not in event_types:
                continue
            
            # Filter by importance
            if event.importance_score < min_importance:
                continue
            
            # Calculate relevance score
            relevance_score = await self._calculate_relevance(event, query_keywords)
            
            if relevance_score > 0.1:  # Minimum relevance threshold
                retrieval = MemoryRetrieval(
                    event=event,
                    relevance_score=relevance_score,
                    retrieval_reason=f"Keyword match: {query_keywords.intersection(set(event.content.lower().split()))}",
                    context_match=event.context
                )
                relevant_events.append(retrieval)
        
        # Sort by relevance and importance
        relevant_events.sort(
            key=lambda x: (x.relevance_score * 0.7 + x.event.importance_score * 0.3),
            reverse=True
        )
        
        return relevant_events[:limit]
    
    async def get_recent_events(
        self,
        user_id: str,
        limit: int = 10,
        event_types: Optional[List[str]] = None
    ) -> List[EpisodicEvent]:
        """Get recent events for a user"""
        
        user_event_ids = self.user_events.get(user_id, [])
        recent_events = []
        
        # Get events in reverse chronological order
        for event_id in reversed(user_event_ids):
            if event_id not in self.events:
                continue
            
            event = self.events[event_id]
            
            # Filter by event type if specified
            if event_types and event.event_type not in event_types:
                continue
            
            recent_events.append(event)
            
            if len(recent_events) >= limit:
                break
        
        return recent_events
    
    async def get_important_events(
        self,
        user_id: str,
        min_importance: float = 0.7,
        limit: int = 10
    ) -> List[EpisodicEvent]:
        """Get important events for a user"""
        
        user_event_ids = self.user_events.get(user_id, [])
        important_events = []
        
        for event_id in user_event_ids:
            if event_id not in self.events:
                continue
            
            event = self.events[event_id]
            
            if event.importance_score >= min_importance:
                important_events.append(event)
        
        # Sort by importance and timestamp
        important_events.sort(
            key=lambda x: (x.importance_score, x.timestamp),
            reverse=True
        )
        
        return important_events[:limit]
    
    async def get_conversation_events(
        self,
        conversation_id: str
    ) -> List[EpisodicEvent]:
        """Get all events for a conversation"""
        
        conversation_event_ids = self.conversation_events.get(conversation_id, [])
        events = []
        
        for event_id in conversation_event_ids:
            if event_id in self.events:
                events.append(self.events[event_id])
        
        # Sort by timestamp
        events.sort(key=lambda x: x.timestamp)
        
        return events
    
    async def update_event_importance(
        self,
        event_id: str,
        new_importance: float
    ):
        """Update importance score of an event"""
        
        if event_id in self.events:
            self.events[event_id].importance_score = new_importance
            logger.info(f"Updated importance of event {event_id} to {new_importance:.2f}")
    
    async def create_memory_summary(
        self,
        user_id: str,
        timeframe_days: int = 30
    ) -> Dict[str, Any]:
        """Create a memory summary for a user"""
        
        cutoff_date = datetime.now() - timedelta(days=timeframe_days)
        user_event_ids = self.user_events.get(user_id, [])
        
        recent_events = []
        important_events = []
        event_type_counts = defaultdict(int)
        
        for event_id in user_event_ids:
            if event_id not in self.events:
                continue
            
            event = self.events[event_id]
            
            if event.timestamp >= cutoff_date:
                recent_events.append(event)
                event_type_counts[event.event_type] += 1
                
                if event.importance_score >= 0.7:
                    important_events.append(event)
        
        # Sort by timestamp
        recent_events.sort(key=lambda x: x.timestamp, reverse=True)
        important_events.sort(key=lambda x: x.importance_score, reverse=True)
        
        return {
            "user_id": user_id,
            "timeframe_days": timeframe_days,
            "total_events": len(recent_events),
            "important_events": len(important_events),
            "event_types": dict(event_type_counts),
            "recent_events": [
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "content": event.content[:100] + "..." if len(event.content) > 100 else event.content,
                    "importance_score": event.importance_score,
                    "timestamp": event.timestamp.isoformat()
                }
                for event in recent_events[:10]
            ],
            "top_important_events": [
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "content": event.content[:100] + "..." if len(event.content) > 100 else event.content,
                    "importance_score": event.importance_score,
                    "timestamp": event.timestamp.isoformat()
                }
                for event in important_events[:5]
            ]
        }
    
    async def _index_event(self, event: EpisodicEvent):
        """Index event by keywords for retrieval"""
        
        # Extract keywords from content
        content_lower = event.content.lower()
        keywords = set(content_lower.split())
        
        # Remove common stop words
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "is", "are", "was", "were", "be", "been", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should"}
        keywords = keywords - stop_words
        
        # Index by keywords
        for keyword in keywords:
            self.event_index[keyword].add(event.event_id)
    
    async def _calculate_relevance(
        self,
        event: EpisodicEvent,
        query_keywords: set
    ) -> float:
        """Calculate relevance score for an event given query keywords"""
        
        event_keywords = set(event.content.lower().split())
        
        # Calculate keyword overlap
        overlap = len(query_keywords.intersection(event_keywords))
        total_keywords = len(query_keywords.union(event_keywords))
        
        if total_keywords == 0:
            return 0.0
        
        # Base relevance from keyword overlap
        keyword_relevance = overlap / total_keywords
        
        # Boost relevance based on importance and recency
        importance_boost = event.importance_score * 0.3
        
        # Recency boost (events from last 7 days get boost)
        days_old = (datetime.now() - event.timestamp).days
        recency_boost = max(0, (7 - days_old) / 7) * 0.2
        
        total_relevance = keyword_relevance + importance_boost + recency_boost
        
        return min(1.0, total_relevance)
    
    async def _cleanup_user_events(self, user_id: str):
        """Clean up old events for a user"""
        
        user_event_ids = self.user_events.get(user_id, [])
        
        if len(user_event_ids) <= self.max_events_per_user:
            return
        
        # Sort events by importance and timestamp
        events_with_scores = []
        for event_id in user_event_ids:
            if event_id in self.events:
                event = self.events[event_id]
                # Combined score: importance * 0.7 + recency * 0.3
                days_old = (datetime.now() - event.timestamp).days
                recency_score = max(0, (30 - days_old) / 30)  # 30-day window
                combined_score = event.importance_score * 0.7 + recency_score * 0.3
                events_with_scores.append((event_id, combined_score))
        
        # Sort by combined score (descending)
        events_with_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Keep top events
        events_to_keep = events_with_scores[:self.max_events_per_user]
        events_to_remove = events_with_scores[self.max_events_per_user:]
        
        # Remove events
        for event_id, _ in events_to_remove:
            await self._remove_event(event_id)
        
        # Update user events list
        self.user_events[user_id] = [event_id for event_id, _ in events_to_keep]
        
        logger.info(f"Cleaned up {len(events_to_remove)} old events for user {user_id}")
    
    async def _remove_event(self, event_id: str):
        """Remove an event and its references"""
        
        if event_id not in self.events:
            return
        
        event = self.events[event_id]
        
        # Remove from main storage
        del self.events[event_id]
        
        # Remove from user events
        if event.user_id in self.user_events:
            if event_id in self.user_events[event.user_id]:
                self.user_events[event.user_id].remove(event_id)
        
        # Remove from conversation events
        if event.conversation_id in self.conversation_events:
            if event_id in self.conversation_events[event.conversation_id]:
                self.conversation_events[event.conversation_id].remove(event_id)
        
        # Remove from index
        for keyword, event_ids in self.event_index.items():
            if event_id in event_ids:
                event_ids.remove(event_id)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of episodic memory"""
        return {
            "episodic_memory": True,
            "total_events": len(self.events),
            "active_users": len(self.user_events),
            "active_conversations": len(self.conversation_events),
            "indexed_keywords": len(self.event_index),
            "importance_threshold": self.importance_threshold,
            "max_events_per_user": self.max_events_per_user
        }
