"""
Action Analyzer
Analyzes user messages to extract actionable commands and parameters
"""

import re
from typing import Dict, List, Any, Optional
from ..assistant_core import ActionRequest, ActionType

class ActionAnalyzer:
    """
    Analyzes user messages to extract actionable commands and create action requests
    """
    
    def __init__(self):
        self.action_patterns = self._load_action_patterns()
        self.parameter_extractors = self._load_parameter_extractors()
    
    def extract_actions(self, message: str, intent: Dict[str, Any], context) -> List[ActionRequest]:
        """
        Extract actionable commands from user message
        """
        actions = []
        
        if intent.get('type') != 'action_request':
            return actions
        
        action_type = intent.get('action', '')
        parameters = intent.get('parameters', {})
        
        # Map intent actions to ActionType enums
        action_type_mapping = {
            'application_control': ActionType.APPLICATION_CONTROL,
            'window_management': ActionType.SYSTEM_COMMAND,
            'volume_control': ActionType.SYSTEM_COMMAND,
            'screenshot': ActionType.SYSTEM_COMMAND,
            'web_search': ActionType.WEB_SEARCH,
            'communication': ActionType.COMMUNICATION,
            'scheduling': ActionType.SCHEDULING,
            'get_information': ActionType.INFORMATION_RETRIEVAL
        }
        
        mapped_action_type = action_type_mapping.get(action_type)
        if mapped_action_type:
            action_request = ActionRequest(
                action_type=mapped_action_type,
                command=action_type,
                parameters=parameters,
                context=message,
                priority=self._calculate_priority(action_type, parameters),
                requires_confirmation=self._requires_confirmation(action_type, parameters)
            )
            actions.append(action_request)
        
        return actions
    
    def _calculate_priority(self, action_type: str, parameters: Dict[str, Any]) -> int:
        """
        Calculate priority for action execution
        """
        # High priority actions
        high_priority = ['screenshot', 'volume_control', 'window_management']
        if action_type in high_priority:
            return 1
        
        # Medium priority actions
        medium_priority = ['application_control', 'web_search', 'get_information']
        if action_type in medium_priority:
            return 2
        
        # Low priority actions
        low_priority = ['communication', 'scheduling']
        if action_type in low_priority:
            return 3
        
        return 2  # Default medium priority
    
    def _requires_confirmation(self, action_type: str, parameters: Dict[str, Any]) -> bool:
        """
        Determine if action requires user confirmation
        """
        # Actions that require confirmation
        confirmation_required = [
            'screenshot',  # May capture sensitive information
            'communication',  # Sending messages/emails
            'scheduling'  # Creating calendar events
        ]
        
        if action_type in confirmation_required:
            return True
        
        # Check for destructive actions
        destructive_keywords = ['delete', 'remove', 'close', 'shutdown', 'restart']
        for keyword in destructive_keywords:
            if keyword in str(parameters).lower():
                return True
        
        return False
    
    def _load_action_patterns(self) -> Dict[str, List[str]]:
        """
        Load action recognition patterns
        """
        return {
            "application_control": [
                r'\b(open|launch|start)\b.*\b(chrome|browser|notepad|calculator|explorer|youtube|spotify)\b',
                r'\b(run|execute)\b.*\b(application|app|program)\b'
            ],
            "window_management": [
                r'\b(close|minimize|maximize|restore)\b.*\b(window|tab|app|application)\b',
                r'\b(hide|show)\b.*\b(window|application)\b'
            ],
            "volume_control": [
                r'\b(volume|sound|audio)\b.*\b(up|down|mute|unmute|increase|decrease)\b',
                r'\b(turn up|turn down|turn off|turn on)\b.*\b(volume|sound)\b'
            ],
            "screenshot": [
                r'\b(screenshot|capture|screen)\b',
                r'\b(take a picture|snapshot)\b.*\b(screen|desktop)\b'
            ],
            "web_search": [
                r'\b(search|find|look up|google)\b',
                r'\b(what is|who is|where is|when is|how is)\b'
            ],
            "communication": [
                r'\b(email|send message|message|notify)\b',
                r'\b(write|compose)\b.*\b(email|message)\b'
            ],
            "scheduling": [
                r'\b(schedule|appointment|meeting|reminder|calendar)\b',
                r'\b(book|reserve|set up)\b.*\b(appointment|meeting|event)\b'
            ],
            "information_retrieval": [
                r'\b(weather|temperature|forecast)\b',
                r'\b(time|date|current time)\b',
                r'\b(tell me|what\'s the|show me)\b'
            ]
        }
    
    def _load_parameter_extractors(self) -> Dict[str, Any]:
        """
        Load parameter extraction patterns
        """
        return {
            "time_patterns": [
                r'\b(\d{1,2}:\d{2})\b',  # HH:MM
                r'\b(\d{1,2}\s*(am|pm))\b',  # 12 hour format
                r'\b(today|tomorrow|yesterday)\b'
            ],
            "date_patterns": [
                r'\b(today|tomorrow|yesterday)\b',
                r'\b(\d{1,2}/\d{1,2}/\d{4})\b',  # MM/DD/YYYY
                r'\b(\d{1,2}-\d{1,2}-\d{4})\b',  # MM-DD-YYYY
            ],
            "number_patterns": [
                r'\b(\d+)\b',  # Any number
            ],
            "email_patterns": [
                r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'  # Email format
            ],
            "url_patterns": [
                r'\b(https?://[^\s]+)\b',  # URLs
                r'\b(www\.[^\s]+)\b'  # www URLs
            ]
        }
