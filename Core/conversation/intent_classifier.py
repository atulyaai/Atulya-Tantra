"""
Intent Classification System
Analyzes user messages to determine intent and extract parameters
"""

import re
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

class IntentClassifier:
    """
    Advanced intent classification system that understands user intentions
    and extracts relevant parameters for action execution
    """
    
    def __init__(self):
        self.intent_patterns = self._load_intent_patterns()
        self.parameter_extractors = self._load_parameter_extractors()
    
    def classify(self, message: str, context) -> Dict[str, Any]:
        """
        Classify user message intent and extract parameters
        """
        message_lower = message.lower().strip()
        
        # Check for greetings
        if self._is_greeting(message_lower):
            return {
                "type": "greeting",
                "confidence": 0.9,
                "parameters": {},
                "action": None
            }
        
        # Check for farewells
        if self._is_farewell(message_lower):
            return {
                "type": "farewell",
                "confidence": 0.9,
                "parameters": {},
                "action": None
            }
        
        # Check for capability questions
        if self._is_capability_question(message_lower):
            return {
                "type": "capability_inquiry",
                "confidence": 0.9,
                "parameters": {},
                "action": None
            }
        
        # Check for system control commands
        system_intent = self._classify_system_control(message_lower)
        if system_intent:
            return system_intent
        
        # Check for web search
        search_intent = self._classify_search(message_lower)
        if search_intent:
            return search_intent
        
        # Check for communication
        comm_intent = self._classify_communication(message_lower)
        if comm_intent:
            return comm_intent
        
        # Check for scheduling
        schedule_intent = self._classify_scheduling(message_lower)
        if schedule_intent:
            return schedule_intent
        
        # Check for information requests
        info_intent = self._classify_information_request(message_lower)
        if info_intent:
            return info_intent
        
        # Default to general conversation
        return {
            "type": "general_conversation",
            "confidence": 0.6,
            "parameters": {},
            "action": None
        }
    
    def _is_greeting(self, message: str) -> bool:
        """Check if message is a greeting"""
        greeting_patterns = [
            r'\b(hello|hi|hey|good morning|good afternoon|good evening)\b',
            r'\b(how are you|how\'s it going|what\'s up)\b'
        ]
        
        for pattern in greeting_patterns:
            if re.search(pattern, message):
                return True
        return False
    
    def _is_farewell(self, message: str) -> bool:
        """Check if message is a farewell"""
        farewell_patterns = [
            r'\b(goodbye|bye|see you|talk to you later|have a good day)\b',
            r'\b(thanks|thank you|that\'s all|that\'s it)\b'
        ]
        
        for pattern in farewell_patterns:
            if re.search(pattern, message):
                return True
        return False
    
    def _is_capability_question(self, message: str) -> bool:
        """Check if message is asking about capabilities"""
        capability_patterns = [
            r'\b(what can you do|what are your capabilities|help|features)\b',
            r'\b(what tasks|what functions|what services)\b'
        ]
        
        for pattern in capability_patterns:
            if re.search(pattern, message):
                return True
        return False
    
    def _classify_system_control(self, message: str) -> Optional[Dict[str, Any]]:
        """Classify system control commands"""
        # Window management
        if re.search(r'\b(close|minimize|maximize|restore)\b.*\b(window|tab|app|application)\b', message):
            action = "window_management"
            parameters = self._extract_window_parameters(message)
            return {
                "type": "action_request",
                "confidence": 0.8,
                "action": action,
                "parameters": parameters
            }
        
        # Application control
        if re.search(r'\b(open|launch|start)\b', message):
            action = "application_control"
            parameters = self._extract_application_parameters(message)
            return {
                "type": "action_request",
                "confidence": 0.8,
                "action": action,
                "parameters": parameters
            }
        
        # Volume control
        if re.search(r'\b(volume|sound|audio)\b', message):
            action = "volume_control"
            parameters = self._extract_volume_parameters(message)
            return {
                "type": "action_request",
                "confidence": 0.8,
                "action": action,
                "parameters": parameters
            }
        
        # Screenshot
        if re.search(r'\b(screenshot|capture|screen)\b', message):
            return {
                "type": "action_request",
                "confidence": 0.9,
                "action": "screenshot",
                "parameters": {}
            }
        
        return None
    
    def _classify_search(self, message: str) -> Optional[Dict[str, Any]]:
        """Classify search requests"""
        search_patterns = [
            r'\b(search|find|look up|google)\b',
            r'\b(what is|who is|where is|when is|how is)\b',
            r'\b(information about|details about|tell me about)\b'
        ]
        
        for pattern in search_patterns:
            if re.search(pattern, message):
                query = self._extract_search_query(message)
                return {
                    "type": "action_request",
                    "confidence": 0.8,
                    "action": "web_search",
                    "parameters": {"query": query}
                }
        
        return None
    
    def _classify_communication(self, message: str) -> Optional[Dict[str, Any]]:
        """Classify communication requests"""
        if re.search(r'\b(email|send message|message|notify)\b', message):
            return {
                "type": "action_request",
                "confidence": 0.8,
                "action": "communication",
                "parameters": self._extract_communication_parameters(message)
            }
        
        return None
    
    def _classify_scheduling(self, message: str) -> Optional[Dict[str, Any]]:
        """Classify scheduling requests"""
        schedule_patterns = [
            r'\b(schedule|appointment|meeting|reminder|calendar)\b',
            r'\b(book|reserve|set up)\b.*\b(appointment|meeting|event)\b'
        ]
        
        for pattern in schedule_patterns:
            if re.search(pattern, message):
                return {
                    "type": "action_request",
                    "confidence": 0.8,
                    "action": "scheduling",
                    "parameters": self._extract_scheduling_parameters(message)
                }
        
        return None
    
    def _classify_information_request(self, message: str) -> Optional[Dict[str, Any]]:
        """Classify information requests"""
        info_patterns = [
            r'\b(weather|temperature|forecast)\b',
            r'\b(time|date|current time)\b',
            r'\b(what\'s the|tell me the)\b'
        ]
        
        for pattern in info_patterns:
            if re.search(pattern, message):
                return {
                    "type": "information_request",
                    "confidence": 0.8,
                    "action": "get_information",
                    "parameters": self._extract_information_parameters(message)
                }
        
        return None
    
    def _extract_window_parameters(self, message: str) -> Dict[str, Any]:
        """Extract window management parameters"""
        params = {}
        
        if 'close' in message:
            params['action'] = 'close'
        elif 'minimize' in message:
            params['action'] = 'minimize'
        elif 'maximize' in message:
            params['action'] = 'maximize'
        elif 'restore' in message:
            params['action'] = 'restore'
        
        return params
    
    def _extract_application_parameters(self, message: str) -> Dict[str, Any]:
        """Extract application control parameters"""
        params = {}
        
        # Extract application name
        app_patterns = {
            'chrome': r'\b(chrome|browser|web browser)\b',
            'notepad': r'\b(notepad|text editor)\b',
            'calculator': r'\b(calculator|calc)\b',
            'explorer': r'\b(file explorer|files|explorer)\b',
            'youtube': r'\b(youtube|video)\b',
            'spotify': r'\b(spotify|music)\b'
        }
        
        for app, pattern in app_patterns.items():
            if re.search(pattern, message):
                params['application'] = app
                break
        
        return params
    
    def _extract_volume_parameters(self, message: str) -> Dict[str, Any]:
        """Extract volume control parameters"""
        params = {}
        
        if 'up' in message or 'increase' in message:
            params['action'] = 'increase'
        elif 'down' in message or 'decrease' in message:
            params['action'] = 'decrease'
        elif 'mute' in message:
            params['action'] = 'mute'
        elif 'unmute' in message:
            params['action'] = 'unmute'
        
        return params
    
    def _extract_search_query(self, message: str) -> str:
        """Extract search query from message"""
        # Remove common search trigger words
        query = re.sub(r'\b(search|find|look up|google|information about|details about|tell me about)\b', '', message)
        return query.strip()
    
    def _extract_communication_parameters(self, message: str) -> Dict[str, Any]:
        """Extract communication parameters"""
        params = {}
        
        if 'email' in message:
            params['type'] = 'email'
        elif 'message' in message:
            params['type'] = 'message'
        
        return params
    
    def _extract_scheduling_parameters(self, message: str) -> Dict[str, Any]:
        """Extract scheduling parameters"""
        params = {}
        
        if 'appointment' in message:
            params['type'] = 'appointment'
        elif 'meeting' in message:
            params['type'] = 'meeting'
        elif 'reminder' in message:
            params['type'] = 'reminder'
        
        return params
    
    def _extract_information_parameters(self, message: str) -> Dict[str, Any]:
        """Extract information request parameters"""
        params = {}
        
        if 'weather' in message:
            params['type'] = 'weather'
        elif 'time' in message:
            params['type'] = 'time'
        elif 'date' in message:
            params['type'] = 'date'
        
        return params
    
    def _load_intent_patterns(self) -> Dict[str, List[str]]:
        """Load intent classification patterns"""
        return {
            "greetings": [
                "hello", "hi", "hey", "good morning", "good afternoon", "good evening"
            ],
            "farewells": [
                "goodbye", "bye", "see you later", "talk to you later"
            ],
            "capabilities": [
                "what can you do", "help", "features", "capabilities"
            ],
            "system_control": [
                "open", "close", "minimize", "maximize", "screenshot", "volume"
            ],
            "search": [
                "search", "find", "look up", "google", "information about"
            ],
            "communication": [
                "email", "send message", "notify", "message"
            ],
            "scheduling": [
                "schedule", "appointment", "meeting", "reminder", "calendar"
            ]
        }
    
    def _load_parameter_extractors(self) -> Dict[str, Any]:
        """Load parameter extraction patterns"""
        return {
            "time_patterns": [
                r'\b(\d{1,2}:\d{2})\b',  # HH:MM
                r'\b(\d{1,2}\s*(am|pm))\b',  # 12 hour format
            ],
            "date_patterns": [
                r'\b(today|tomorrow|yesterday)\b',
                r'\b(\d{1,2}/\d{1,2}/\d{4})\b',  # MM/DD/YYYY
                r'\b(\d{1,2}-\d{1,2}-\d{4})\b',  # MM-DD-YYYY
            ],
            "number_patterns": [
                r'\b(\d+)\b',  # Any number
            ]
        }
