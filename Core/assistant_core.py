"""
Assistant Core - Core classes and interfaces for the AGI system
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

class ConversationContext:
    """Context for conversation state and history"""
    
    def __init__(self, user_id: str, session_id: str = None):
        self.user_id = user_id
        self.session_id = session_id or f"session_{datetime.now().timestamp()}"
        self.messages: List[Dict[str, Any]] = []
        self.current_topic: str = ""
        self.user_preferences: Dict[str, Any] = {}
        self.conversation_history: List[Dict[str, Any]] = []
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.emotional_state: str = "neutral"
        self.context_data: Dict[str, Any] = {}
    
    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None):
        """Add a message to the conversation"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(),
            "metadata": metadata or {}
        }
        self.messages.append(message)
        self.last_activity = datetime.now()
    
    def get_recent_messages(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent messages"""
        return self.messages[-count:] if self.messages else []
    
    def update_topic(self, topic: str):
        """Update current conversation topic"""
        self.current_topic = topic
    
    def set_preference(self, key: str, value: Any):
        """Set user preference"""
        self.user_preferences[key] = value
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get user preference"""
        return self.user_preferences.get(key, default)

class ActionRequest:
    """Request for action execution"""
    
    def __init__(self, action_type: str, parameters: Dict[str, Any], 
                 user_id: str, context: ConversationContext = None):
        self.action_type = action_type
        self.parameters = parameters
        self.user_id = user_id
        self.context = context
        self.timestamp = datetime.now()
        self.request_id = f"req_{datetime.now().timestamp()}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "action_type": self.action_type,
            "parameters": self.parameters,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "request_id": self.request_id
        }

class ActionResponse:
    """Response from action execution"""
    
    def __init__(self, success: bool, result: Any = None, error: str = None):
        self.success = success
        self.result = result
        self.error = error
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp.isoformat()
        }

class ActionType(str, Enum):
    """Types of actions that can be performed"""
    SYSTEM_CONTROL = "system_control"
    WEB_SEARCH = "web_search"
    COMMUNICATION = "communication"
    SCHEDULING = "scheduling"
    APPLICATION = "application"
    FILE_OPERATION = "file_operation"
    DATA_ANALYSIS = "data_analysis"
    CREATIVE_TASK = "creative_task"

class BaseAction:
    """Base class for all actions"""
    
    def __init__(self, action_type: ActionType):
        self.action_type = action_type
    
    def execute(self, action_request: ActionRequest, context: ConversationContext) -> ActionResponse:
        """Execute the action"""
        raise NotImplementedError("Subclasses must implement execute method")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Validate action parameters"""
        return True
    
    def get_required_parameters(self) -> List[str]:
        """Get list of required parameters"""
        return []

class AssistantCore:
    """Core assistant functionality"""
    
    def __init__(self):
        self.actions: Dict[ActionType, BaseAction] = {}
        self.conversation_contexts: Dict[str, ConversationContext] = {}
    
    def register_action(self, action: BaseAction):
        """Register an action"""
        self.actions[action.action_type] = action
    
    def get_context(self, user_id: str) -> ConversationContext:
        """Get or create conversation context"""
        if user_id not in self.conversation_contexts:
            self.conversation_contexts[user_id] = ConversationContext(user_id)
        return self.conversation_contexts[user_id]
    
    def execute_action(self, action_request: ActionRequest) -> ActionResponse:
        """Execute an action"""
        if action_request.action_type not in self.actions:
            return ActionResponse(False, error=f"Unknown action type: {action_request.action_type}")
        
        action = self.actions[action_request.action_type]
        context = self.get_context(action_request.user_id)
        
        try:
            return action.execute(action_request, context)
        except Exception as e:
            return ActionResponse(False, error=str(e))

# Global instance
_assistant_core = None

def get_assistant_core() -> AssistantCore:
    """Get global assistant core instance"""
    global _assistant_core
    if _assistant_core is None:
        _assistant_core = AssistantCore()
    return _assistant_core
