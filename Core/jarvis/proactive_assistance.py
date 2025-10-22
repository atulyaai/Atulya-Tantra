"""
Proactive Assistance System for Atulya Tantra AGI JARVIS
Context-aware help, suggestions, and automated assistance
"""

import asyncio
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import json

from ..config.settings import settings
from ..config.logging import get_logger
from ..config.exceptions import AgentError
from ..brain import generate_response, get_llm_router
from ..agents import get_orchestrator, submit_task, AgentPriority
from .personality_engine import get_conversational_ai, ConversationContext

logger = get_logger(__name__)


class AssistanceType(str, Enum):
    """Types of proactive assistance"""
    SUGGESTION = "suggestion"
    REMINDER = "reminder"
    ALERT = "alert"
    RECOMMENDATION = "recommendation"
    AUTOMATION = "automation"
    LEARNING = "learning"


class AssistancePriority(str, Enum):
    """Priority levels for assistance"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ProactiveAssistance:
    """Proactive assistance and context-aware help system"""
    
    def __init__(self):
        self.assistance_rules: List[Dict[str, Any]] = []
        self.user_patterns: Dict[str, Dict[str, Any]] = {}
        self.scheduled_assistance: Dict[str, List[Dict[str, Any]]] = {}
        self.assistance_history: List[Dict[str, Any]] = []
        self.context_monitors: List[Callable] = []
        
        # Initialize default assistance rules
        self._initialize_default_rules()
        
        # Start background monitoring
        self.monitoring_task = None
        self.is_monitoring = False
    
    def _initialize_default_rules(self):
        """Initialize default proactive assistance rules"""
        default_rules = [
            {
                "id": "greeting_new_user",
                "type": AssistanceType.SUGGESTION,
                "condition": lambda ctx: ctx.interaction_count == 1,
                "action": self._suggest_introduction,
                "priority": AssistancePriority.NORMAL,
                "enabled": True
            },
            {
                "id": "suggest_help",
                "type": AssistanceType.SUGGESTION,
                "condition": lambda ctx: "help" in ctx.conversation_history[-1]["content"].lower() if ctx.conversation_history else False,
                "action": self._suggest_capabilities,
                "priority": AssistancePriority.NORMAL,
                "enabled": True
            },
            {
                "id": "detect_frustration",
                "type": AssistanceType.ALERT,
                "condition": lambda ctx: ctx.user_mood.value in ["frustrated", "confused"],
                "action": self._offer_help,
                "priority": AssistancePriority.HIGH,
                "enabled": True
            },
            {
                "id": "suggest_automation",
                "type": AssistanceType.RECOMMENDATION,
                "condition": lambda ctx: self._detect_repetitive_task(ctx),
                "action": self._suggest_automation,
                "priority": AssistancePriority.NORMAL,
                "enabled": True
            },
            {
                "id": "learning_opportunity",
                "type": AssistanceType.LEARNING,
                "condition": lambda ctx: self._detect_learning_opportunity(ctx),
                "action": self._suggest_learning,
                "priority": AssistancePriority.LOW,
                "enabled": True
            }
        ]
        
        self.assistance_rules.extend(default_rules)
        logger.info(f"Initialized {len(default_rules)} default assistance rules")
    
    async def start_monitoring(self):
        """Start background monitoring for proactive assistance"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Proactive assistance monitoring started")
    
    async def stop_monitoring(self):
        """Stop background monitoring"""
        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Proactive assistance monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop for proactive assistance"""
        while self.is_monitoring:
            try:
                # Check scheduled assistance
                await self._check_scheduled_assistance()
                
                # Monitor user patterns
                await self._monitor_user_patterns()
                
                # Check context monitors
                await self._check_context_monitors()
                
                # Wait before next check
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def analyze_context(self, user_id: str, context: ConversationContext) -> List[Dict[str, Any]]:
        """Analyze context and generate proactive assistance"""
        assistance_items = []
        
        try:
            # Check all assistance rules
            for rule in self.assistance_rules:
                if not rule.get("enabled", True):
                    continue
                
                try:
                    # Check if condition is met
                    if rule["condition"](context):
                        # Generate assistance
                        assistance = await rule["action"](user_id, context)
                        
                        if assistance:
                            assistance.update({
                                "rule_id": rule["id"],
                                "type": rule["type"],
                                "priority": rule["priority"],
                                "generated_at": datetime.utcnow().isoformat(),
                                "user_id": user_id
                            })
                            
                            assistance_items.append(assistance)
                            
                except Exception as e:
                    logger.error(f"Error in assistance rule {rule['id']}: {e}")
            
            # Log assistance generation
            if assistance_items:
                self.assistance_history.extend(assistance_items)
                logger.info(f"Generated {len(assistance_items)} assistance items for user {user_id}")
            
            return assistance_items
            
        except Exception as e:
            logger.error(f"Error analyzing context: {e}")
            return []
    
    async def _suggest_introduction(self, user_id: str, context: ConversationContext) -> Dict[str, Any]:
        """Suggest introduction for new users"""
        return {
            "title": "Welcome to JARVIS!",
            "message": "I'm your AI assistant. I can help with coding, research, creative writing, data analysis, and system tasks. What would you like to explore?",
            "suggestions": [
                "Tell me about your capabilities",
                "Help me write some code",
                "Research a topic for me",
                "Analyze some data"
            ],
            "action_type": "suggestion"
        }
    
    async def _suggest_capabilities(self, user_id: str, context: ConversationContext) -> Dict[str, Any]:
        """Suggest JARVIS capabilities"""
        return {
            "title": "Here's what I can help you with:",
            "message": "I have specialized agents for different tasks:",
            "suggestions": [
                "Code Agent: Programming, debugging, testing",
                "Research Agent: Web search, information gathering",
                "Creative Agent: Writing, storytelling, content creation",
                "Data Agent: Analysis, visualization, statistics",
                "System Agent: Monitoring, automation, maintenance"
            ],
            "action_type": "suggestion"
        }
    
    async def _offer_help(self, user_id: str, context: ConversationContext) -> Dict[str, Any]:
        """Offer help when user seems frustrated"""
        return {
            "title": "I'm here to help!",
            "message": "I notice you might be having some difficulty. Let me help you with that.",
            "suggestions": [
                "Break down the problem into smaller steps",
                "Try a different approach",
                "Ask me to explain in simpler terms",
                "Let me search for more information"
            ],
            "action_type": "alert"
        }
    
    async def _suggest_automation(self, user_id: str, context: ConversationContext) -> Dict[str, Any]:
        """Suggest automation for repetitive tasks"""
        return {
            "title": "Automation Opportunity",
            "message": "I noticed you're doing a repetitive task. I can help automate this for you.",
            "suggestions": [
                "Create a script to automate this task",
                "Set up a scheduled job",
                "Build a workflow for this process",
                "Create a template for future use"
            ],
            "action_type": "recommendation"
        }
    
    async def _suggest_learning(self, user_id: str, context: ConversationContext) -> Dict[str, Any]:
        """Suggest learning opportunities"""
        return {
            "title": "Learning Opportunity",
            "message": "I can help you learn more about this topic.",
            "suggestions": [
                "Research related concepts",
                "Find tutorials and resources",
                "Practice with examples",
                "Explore advanced topics"
            ],
            "action_type": "learning"
        }
    
    def _detect_repetitive_task(self, context: ConversationContext) -> bool:
        """Detect if user is doing repetitive tasks"""
        if len(context.conversation_history) < 3:
            return False
        
        # Look for repeated patterns in recent messages
        recent_messages = [msg["content"].lower() for msg in context.conversation_history[-3:]]
        
        # Check for repetitive keywords
        repetitive_keywords = ["again", "repeat", "same", "similar", "another"]
        return any(keyword in " ".join(recent_messages) for keyword in repetitive_keywords)
    
    def _detect_learning_opportunity(self, context: ConversationContext) -> bool:
        """Detect learning opportunities"""
        if not context.conversation_history:
            return False
        
        last_message = context.conversation_history[-1]["content"].lower()
        
        # Check for learning-related keywords
        learning_keywords = ["learn", "understand", "explain", "how does", "what is", "why"]
        return any(keyword in last_message for keyword in learning_keywords)
    
    async def schedule_assistance(
        self, 
        user_id: str, 
        assistance: Dict[str, Any], 
        scheduled_time: datetime
    ) -> str:
        """Schedule assistance for a specific time"""
        assistance_id = f"scheduled_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        if user_id not in self.scheduled_assistance:
            self.scheduled_assistance[user_id] = []
        
        scheduled_item = {
            "id": assistance_id,
            "assistance": assistance,
            "scheduled_time": scheduled_time.isoformat(),
            "created_at": datetime.utcnow().isoformat()
        }
        
        self.scheduled_assistance[user_id].append(scheduled_item)
        
        logger.info(f"Scheduled assistance {assistance_id} for user {user_id} at {scheduled_time}")
        return assistance_id
    
    async def _check_scheduled_assistance(self):
        """Check for scheduled assistance that should be delivered"""
        current_time = datetime.utcnow()
        
        for user_id, scheduled_items in self.scheduled_assistance.items():
            items_to_deliver = []
            
            for item in scheduled_items:
                scheduled_time = datetime.fromisoformat(item["scheduled_time"])
                if current_time >= scheduled_time:
                    items_to_deliver.append(item)
            
            # Deliver scheduled assistance
            for item in items_to_deliver:
                await self._deliver_assistance(user_id, item["assistance"])
                scheduled_items.remove(item)
    
    async def _deliver_assistance(self, user_id: str, assistance: Dict[str, Any]):
        """Deliver assistance to user"""
        try:
            # This would integrate with the notification system
            logger.info(f"Delivering assistance to user {user_id}: {assistance.get('title', 'No title')}")
            
            # Add to assistance history
            self.assistance_history.append({
                "user_id": user_id,
                "assistance": assistance,
                "delivered_at": datetime.utcnow().isoformat(),
                "type": "scheduled"
            })
            
        except Exception as e:
            logger.error(f"Error delivering assistance: {e}")
    
    async def _monitor_user_patterns(self):
        """Monitor user patterns for proactive assistance"""
        # This would analyze user behavior patterns
        # and generate assistance based on usage patterns
        pass
    
    async def _check_context_monitors(self):
        """Check registered context monitors"""
        for monitor in self.context_monitors:
            try:
                await monitor()
            except Exception as e:
                logger.error(f"Error in context monitor: {e}")
    
    def add_assistance_rule(self, rule: Dict[str, Any]):
        """Add a new assistance rule"""
        self.assistance_rules.append(rule)
        logger.info(f"Added assistance rule: {rule.get('id', 'unknown')}")
    
    def remove_assistance_rule(self, rule_id: str) -> bool:
        """Remove an assistance rule"""
        for i, rule in enumerate(self.assistance_rules):
            if rule.get("id") == rule_id:
                del self.assistance_rules[i]
                logger.info(f"Removed assistance rule: {rule_id}")
                return True
        return False
    
    def add_context_monitor(self, monitor: Callable):
        """Add a context monitor"""
        self.context_monitors.append(monitor)
        logger.info("Added context monitor")
    
    async def get_user_assistance_history(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get assistance history for a user"""
        user_history = [
            item for item in self.assistance_history 
            if item.get("user_id") == user_id
        ]
        return user_history[-limit:] if user_history else []
    
    async def get_assistance_statistics(self) -> Dict[str, Any]:
        """Get assistance statistics"""
        total_assistance = len(self.assistance_history)
        
        # Count by type
        type_counts = {}
        for item in self.assistance_history:
            assistance = item.get("assistance", {})
            action_type = assistance.get("action_type", "unknown")
            type_counts[action_type] = type_counts.get(action_type, 0) + 1
        
        # Count by priority
        priority_counts = {}
        for item in self.assistance_history:
            priority = item.get("priority", "unknown")
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        return {
            "total_assistance": total_assistance,
            "type_distribution": type_counts,
            "priority_distribution": priority_counts,
            "active_rules": len([r for r in self.assistance_rules if r.get("enabled", True)]),
            "scheduled_items": sum(len(items) for items in self.scheduled_assistance.values())
        }


class ContextAwareAssistant:
    """Context-aware assistant that provides intelligent help"""
    
    def __init__(self):
        self.proactive_assistance = ProactiveAssistance()
        self.user_contexts: Dict[str, ConversationContext] = {}
        self.assistance_preferences: Dict[str, Dict[str, Any]] = {}
    
    async def process_with_assistance(
        self, 
        user_id: str, 
        message: str, 
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Process message with proactive assistance"""
        try:
            # Get or create user context
            if user_id not in self.user_contexts:
                self.user_contexts[user_id] = ConversationContext(user_id)
            
            context = self.user_contexts[user_id]
            
            # Add message to context
            context.add_message("user", message, metadata)
            
            # Analyze context for proactive assistance
            assistance_items = await self.proactive_assistance.analyze_context(user_id, context)
            
            # Process the message normally
            conversational_ai = await get_conversational_ai()
            response_data = await conversational_ai.process_message(user_id, message, metadata)
            
            # Add assistance to response
            response_data["proactive_assistance"] = assistance_items
            
            return response_data
            
        except Exception as e:
            logger.error(f"Error in context-aware processing: {e}")
            return {
                "response": "I encountered an error processing your message.",
                "error": str(e),
                "proactive_assistance": []
            }
    
    async def start_monitoring(self):
        """Start proactive assistance monitoring"""
        await self.proactive_assistance.start_monitoring()
    
    async def stop_monitoring(self):
        """Stop proactive assistance monitoring"""
        await self.proactive_assistance.stop_monitoring()
    
    async def get_user_assistance_summary(self, user_id: str) -> Dict[str, Any]:
        """Get assistance summary for a user"""
        history = await self.proactive_assistance.get_user_assistance_history(user_id)
        preferences = self.assistance_preferences.get(user_id, {})
        
        return {
            "user_id": user_id,
            "assistance_count": len(history),
            "preferences": preferences,
            "recent_assistance": history[-5:] if history else [],
            "context": self.user_contexts.get(user_id, {}).__dict__ if user_id in self.user_contexts else {}
        }


# Global context-aware assistant instance
_context_assistant: Optional[ContextAwareAssistant] = None


async def get_context_assistant() -> ContextAwareAssistant:
    """Get global context-aware assistant instance"""
    global _context_assistant
    
    if _context_assistant is None:
        _context_assistant = ContextAwareAssistant()
        await _context_assistant.start_monitoring()
    
    return _context_assistant


async def process_with_assistance(
    user_id: str, 
    message: str, 
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Process message with proactive assistance"""
    assistant = await get_context_assistant()
    return await assistant.process_with_assistance(user_id, message, metadata)


async def schedule_assistance(
    user_id: str, 
    assistance: Dict[str, Any], 
    scheduled_time: datetime
) -> str:
    """Schedule assistance for a user"""
    assistant = await get_context_assistant()
    return await assistant.proactive_assistance.schedule_assistance(user_id, assistance, scheduled_time)


async def get_assistance_statistics() -> Dict[str, Any]:
    """Get assistance statistics"""
    assistant = await get_context_assistant()
    return await assistant.proactive_assistance.get_assistance_statistics()


# Export public API
__all__ = [
    "AssistanceType",
    "AssistancePriority",
    "ProactiveAssistance",
    "ContextAwareAssistant",
    "get_context_assistant",
    "process_with_assistance",
    "schedule_assistance",
    "get_assistance_statistics"
]
