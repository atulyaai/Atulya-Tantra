"""
Atulya Tantra - JARVIS Conversational Memory
Version: 2.5.0
Enhanced memory system for JARVIS personality and conversational intelligence
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import uuid
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


@dataclass
class PersonalDetail:
    """Personal detail about user"""
    key: str
    value: str
    confidence: float
    source: str  # "explicit", "inferred", "context"
    timestamp: datetime
    conversation_id: str


@dataclass
class RelationshipContext:
    """Relationship context between JARVIS and user"""
    user_id: str
    relationship_stage: str  # "new", "acquaintance", "friend", "close"
    interaction_count: int
    last_interaction: datetime
    trust_level: float  # 0.0 to 1.0
    familiarity_topics: List[str]
    personal_details: Dict[str, PersonalDetail]


@dataclass
class ConversationInsight:
    """Insight extracted from conversation"""
    insight_type: str  # "preference", "goal", "concern", "achievement"
    content: str
    confidence: float
    timestamp: datetime
    conversation_id: str
    metadata: Dict[str, Any]


class ConversationalMemory:
    """Enhanced conversational memory for JARVIS personality"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.relationship_contexts = {}  # user_id -> RelationshipContext
        self.personal_details = defaultdict(list)  # user_id -> List[PersonalDetail]
        self.conversation_insights = defaultdict(list)  # user_id -> List[ConversationInsight]
        self.interaction_patterns = defaultdict(list)  # user_id -> List[interaction_data]
        self.memory_decay_factor = 0.95  # How quickly memories fade
        
        logger.info("ConversationalMemory initialized")
    
    async def update_relationship_context(
        self,
        user_id: str,
        conversation_id: str,
        interaction_type: str,
        sentiment: str,
        topics: List[str]
    ):
        """Update relationship context based on interaction"""
        
        if user_id not in self.relationship_contexts:
            self.relationship_contexts[user_id] = RelationshipContext(
                user_id=user_id,
                relationship_stage="new",
                interaction_count=0,
                last_interaction=datetime.now(),
                trust_level=0.5,
                familiarity_topics=[],
                personal_details={}
            )
        
        context = self.relationship_contexts[user_id]
        
        # Update interaction count
        context.interaction_count += 1
        context.last_interaction = datetime.now()
        
        # Update relationship stage based on interaction count
        if context.interaction_count > 50:
            context.relationship_stage = "close"
        elif context.interaction_count > 20:
            context.relationship_stage = "friend"
        elif context.interaction_count > 5:
            context.relationship_stage = "acquaintance"
        
        # Update trust level based on sentiment
        trust_adjustment = 0.01
        if sentiment == "positive":
            context.trust_level = min(1.0, context.trust_level + trust_adjustment)
        elif sentiment == "frustrated":
            context.trust_level = max(0.0, context.trust_level - trust_adjustment * 2)
        
        # Update familiarity topics
        for topic in topics:
            if topic not in context.familiarity_topics:
                context.familiarity_topics.append(topic)
        
        # Keep only recent topics (last 20)
        if len(context.familiarity_topics) > 20:
            context.familiarity_topics = context.familiarity_topics[-20:]
        
        logger.info(f"Updated relationship context for user {user_id}: stage={context.relationship_stage}, trust={context.trust_level:.2f}")
    
    async def store_personal_detail(
        self,
        user_id: str,
        key: str,
        value: str,
        confidence: float,
        source: str,
        conversation_id: str
    ):
        """Store personal detail about user"""
        
        # Check if this detail already exists
        existing_detail = None
        for detail in self.personal_details[user_id]:
            if detail.key == key:
                existing_detail = detail
                break
        
        if existing_detail:
            # Update existing detail if confidence is higher
            if confidence > existing_detail.confidence:
                existing_detail.value = value
                existing_detail.confidence = confidence
                existing_detail.source = source
                existing_detail.timestamp = datetime.now()
                existing_detail.conversation_id = conversation_id
        else:
            # Create new detail
            detail = PersonalDetail(
                key=key,
                value=value,
                confidence=confidence,
                source=source,
                timestamp=datetime.now(),
                conversation_id=conversation_id
            )
            self.personal_details[user_id].append(detail)
        
        # Update relationship context
        if user_id in self.relationship_contexts:
            self.relationship_contexts[user_id].personal_details[key] = detail
        
        logger.info(f"Stored personal detail for user {user_id}: {key} = {value} (confidence: {confidence:.2f})")
    
    async def extract_personal_details(
        self,
        user_id: str,
        message: str,
        conversation_id: str
    ) -> List[PersonalDetail]:
        """Extract personal details from user message"""
        
        extracted_details = []
        
        # Simple pattern matching for personal details
        # In production, this would use NLP models
        
        # Name patterns
        name_patterns = [
            "my name is", "i'm called", "call me", "i am"
        ]
        
        # Location patterns
        location_patterns = [
            "i live in", "i'm from", "i work in", "i'm based in"
        ]
        
        # Job patterns
        job_patterns = [
            "i work as", "i'm a", "my job is", "i do"
        ]
        
        # Interest patterns
        interest_patterns = [
            "i like", "i enjoy", "i'm interested in", "i love"
        ]
        
        message_lower = message.lower()
        
        # Extract name
        for pattern in name_patterns:
            if pattern in message_lower:
                # Simple extraction - in production, use proper NLP
                parts = message_lower.split(pattern)
                if len(parts) > 1:
                    name = parts[1].split()[0].strip()
                    if name and len(name) > 1:
                        await self.store_personal_detail(
                            user_id, "name", name.title(), 0.7, "inferred", conversation_id
                        )
                        extracted_details.append(PersonalDetail(
                            key="name", value=name.title(), confidence=0.7,
                            source="inferred", timestamp=datetime.now(),
                            conversation_id=conversation_id
                        ))
        
        # Extract location
        for pattern in location_patterns:
            if pattern in message_lower:
                parts = message_lower.split(pattern)
                if len(parts) > 1:
                    location = parts[1].split()[0].strip()
                    if location and len(location) > 1:
                        await self.store_personal_detail(
                            user_id, "location", location.title(), 0.6, "inferred", conversation_id
                        )
                        extracted_details.append(PersonalDetail(
                            key="location", value=location.title(), confidence=0.6,
                            source="inferred", timestamp=datetime.now(),
                            conversation_id=conversation_id
                        ))
        
        return extracted_details
    
    async def store_conversation_insight(
        self,
        user_id: str,
        insight_type: str,
        content: str,
        confidence: float,
        conversation_id: str,
        metadata: Dict[str, Any] = None
    ):
        """Store insight extracted from conversation"""
        
        insight = ConversationInsight(
            insight_type=insight_type,
            content=content,
            confidence=confidence,
            timestamp=datetime.now(),
            conversation_id=conversation_id,
            metadata=metadata or {}
        )
        
        self.conversation_insights[user_id].append(insight)
        
        # Keep only recent insights (last 50)
        if len(self.conversation_insights[user_id]) > 50:
            self.conversation_insights[user_id] = self.conversation_insights[user_id][-50:]
        
        logger.info(f"Stored insight for user {user_id}: {insight_type} - {content}")
    
    async def get_user_context(
        self,
        user_id: str,
        conversation_id: str
    ) -> Dict[str, Any]:
        """Get comprehensive user context for personalization"""
        
        context = {
            "user_id": user_id,
            "relationship_stage": "new",
            "trust_level": 0.5,
            "personal_details": {},
            "recent_insights": [],
            "familiarity_topics": [],
            "interaction_count": 0
        }
        
        # Get relationship context
        if user_id in self.relationship_contexts:
            rel_context = self.relationship_contexts[user_id]
            context.update({
                "relationship_stage": rel_context.relationship_stage,
                "trust_level": rel_context.trust_level,
                "familiarity_topics": rel_context.familiarity_topics,
                "interaction_count": rel_context.interaction_count
            })
        
        # Get personal details
        if user_id in self.personal_details:
            for detail in self.personal_details[user_id]:
                # Apply memory decay
                age_days = (datetime.now() - detail.timestamp).days
                decayed_confidence = detail.confidence * (self.memory_decay_factor ** age_days)
                
                if decayed_confidence > 0.3:  # Only include if confidence is still reasonable
                    context["personal_details"][detail.key] = {
                        "value": detail.value,
                        "confidence": decayed_confidence,
                        "source": detail.source
                    }
        
        # Get recent insights
        if user_id in self.conversation_insights:
            recent_insights = self.conversation_insights[user_id][-5:]  # Last 5 insights
            context["recent_insights"] = [
                {
                    "type": insight.insight_type,
                    "content": insight.content,
                    "confidence": insight.confidence
                }
                for insight in recent_insights
            ]
        
        return context
    
    async def generate_personalized_context(
        self,
        user_id: str,
        conversation_id: str,
        current_message: str
    ) -> str:
        """Generate personalized context string for AI prompt"""
        
        user_context = await self.get_user_context(user_id, conversation_id)
        context_parts = []
        
        # Add relationship context
        if user_context["relationship_stage"] != "new":
            context_parts.append(f"Relationship: {user_context['relationship_stage']} (trust level: {user_context['trust_level']:.1f})")
        
        # Add personal details
        if user_context["personal_details"]:
            details_text = "Known details: " + ", ".join([
                f"{key}: {detail['value']}" 
                for key, detail in user_context["personal_details"].items()
                if detail["confidence"] > 0.5
            ])
            context_parts.append(details_text)
        
        # Add familiarity topics
        if user_context["familiarity_topics"]:
            topics_text = f"Familiar topics: {', '.join(user_context['familiarity_topics'][-5:])}"
            context_parts.append(topics_text)
        
        # Add recent insights
        if user_context["recent_insights"]:
            insights_text = "Recent insights: " + "; ".join([
                f"{insight['type']}: {insight['content']}"
                for insight in user_context["recent_insights"]
            ])
            context_parts.append(insights_text)
        
        return " | ".join(context_parts) if context_parts else "New user interaction"
    
    async def suggest_follow_up_actions(
        self,
        user_id: str,
        conversation_id: str,
        current_message: str,
        ai_response: str
    ) -> List[str]:
        """Suggest proactive follow-up actions based on context"""
        
        suggestions = []
        user_context = await self.get_user_context(user_id, conversation_id)
        
        # Check if user mentioned a problem or goal
        problem_keywords = ["problem", "issue", "trouble", "help", "stuck", "confused"]
        goal_keywords = ["want", "need", "goal", "plan", "achieve", "accomplish"]
        
        message_lower = current_message.lower()
        
        if any(keyword in message_lower for keyword in problem_keywords):
            suggestions.append("Offer to help break down the problem into smaller steps")
            suggestions.append("Ask if they need additional resources or guidance")
        
        if any(keyword in message_lower for keyword in goal_keywords):
            suggestions.append("Suggest creating a plan or timeline")
            suggestions.append("Offer to help track progress")
        
        # Relationship-based suggestions
        if user_context["relationship_stage"] == "new":
            suggestions.append("Ask about their background or interests to build rapport")
        
        elif user_context["relationship_stage"] == "friend":
            suggestions.append("Reference previous conversations or shared experiences")
            suggestions.append("Ask about updates on previously discussed topics")
        
        # Trust-level based suggestions
        if user_context["trust_level"] > 0.8:
            suggestions.append("Be more direct and honest in recommendations")
            suggestions.append("Share personal insights or experiences")
        
        return suggestions[:3]  # Return top 3 suggestions
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of conversational memory"""
        return {
            "conversational_memory": True,
            "active_users": len(self.relationship_contexts),
            "total_personal_details": sum(len(details) for details in self.personal_details.values()),
            "total_insights": sum(len(insights) for insights in self.conversation_insights.values()),
            "memory_decay_factor": self.memory_decay_factor
        }
