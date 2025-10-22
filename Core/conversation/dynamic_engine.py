"""
Dynamic Conversation Engine
Handles natural conversation flow with context awareness and follow-up questions
"""

import re
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from .intent_classifier import IntentClassifier
from .response_generator import ResponseGenerator
from .action_analyzer import ActionAnalyzer

class DynamicConversationEngine:
    """
    Advanced conversation engine that provides dynamic, context-aware responses
    and intelligent action execution
    """
    
    def __init__(self, llm_provider, memory_system):
        self.llm_provider = llm_provider
        self.memory_system = memory_system
        self.intent_classifier = IntentClassifier()
        self.response_generator = ResponseGenerator(llm_provider)
        self.action_analyzer = ActionAnalyzer()
        
        # Conversation patterns and responses
        self.conversation_patterns = self._load_conversation_patterns()
    
    def analyze_message(self, message: str, context) -> Dict[str, Any]:
        """
        Analyze user message for intent, actions, and conversation flow
        """
        # Classify intent
        intent = self.intent_classifier.classify(message, context)
        
        # Analyze for actions
        actions = self.action_analyzer.extract_actions(message, intent, context)
        
        # Determine conversation flow
        flow_analysis = self._analyze_conversation_flow(message, context, intent)
        
        return {
            "intent": intent,
            "actions": actions,
            "flow_analysis": flow_analysis,
            "follow_up_questions": flow_analysis.get('follow_up_questions', []),
            "requires_clarification": flow_analysis.get('requires_clarification', False),
            "confidence": intent.get('confidence', 0.8)
        }
    
    def generate_response(self, message: str, analysis: Dict[str, Any], context) -> str:
        """
        Generate dynamic response based on analysis and context
        """
        intent = analysis['intent']
        actions = analysis['actions']
        flow_analysis = analysis['flow_analysis']
        
        # Generate base response
        response = self.response_generator.generate(
            message=message,
            intent=intent,
            actions=actions,
            context=context,
            flow_analysis=flow_analysis
        )
        
        # Add follow-up questions if needed
        if flow_analysis.get('follow_up_questions'):
            response += self._format_follow_up_questions(flow_analysis['follow_up_questions'])
        
        return response
    
    def _analyze_conversation_flow(self, message: str, context, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze conversation flow and determine if follow-up is needed
        """
        flow_analysis = {
            "follow_up_questions": [],
            "requires_clarification": False,
            "conversation_continuation": True
        }
        
        # Check if clarification is needed
        if intent.get('confidence', 1.0) < 0.7:
            flow_analysis['requires_clarification'] = True
            flow_analysis['follow_up_questions'].append(
                "Could you please clarify what you'd like me to help you with?"
            )
        
        # Check for incomplete requests
        if intent.get('type') == 'action_request' and not intent.get('parameters'):
            flow_analysis['requires_clarification'] = True
            flow_analysis['follow_up_questions'].append(
                f"I understand you want to {intent.get('action', 'do something')}, but I need more details. What specifically would you like me to do?"
            )
        
        # Check for multi-step tasks
        if intent.get('type') == 'complex_task':
            flow_analysis['follow_up_questions'].extend(
                self._generate_task_follow_ups(intent, context)
            )
        
        return flow_analysis
    
    def _generate_task_follow_ups(self, intent: Dict[str, Any], context) -> List[str]:
        """
        Generate follow-up questions for complex tasks
        """
        follow_ups = []
        task_type = intent.get('task_type', '')
        
        if task_type == 'booking':
            follow_ups.extend([
                "What date and time would you prefer?",
                "How many people will be attending?",
                "Do you have any special requirements?"
            ])
        elif task_type == 'email':
            follow_ups.extend([
                "Who should I send this email to?",
                "What's the subject line?",
                "What's the main message you'd like to convey?"
            ])
        elif task_type == 'search':
            follow_ups.extend([
                "What specific information are you looking for?",
                "Do you have any preferences for the search results?",
                "Should I search for recent information or historical data?"
            ])
        
        return follow_ups
    
    def _format_follow_up_questions(self, questions: List[str]) -> str:
        """
        Format follow-up questions for display
        """
        if not questions:
            return ""
        
        formatted = "\n\nI have a few questions to help you better:"
        for i, question in enumerate(questions, 1):
            formatted += f"\n{i}. {question}"
        
        return formatted
    
    def _load_conversation_patterns(self) -> Dict[str, Any]:
        """
        Load conversation patterns and responses
        """
        return {
            "greetings": [
                "hello", "hi", "hey", "good morning", "good afternoon", "good evening"
            ],
            "farewells": [
                "goodbye", "bye", "see you later", "talk to you later", "have a good day"
            ],
            "capabilities": [
                "what can you do", "what are your capabilities", "help", "features"
            ],
            "weather": [
                "weather", "temperature", "forecast", "rain", "sunny", "cloudy"
            ],
            "time": [
                "time", "what time", "current time", "clock"
            ],
            "search": [
                "search", "find", "look up", "google", "information about"
            ],
            "system_control": [
                "open", "close", "minimize", "maximize", "screenshot", "volume"
            ],
            "communication": [
                "email", "send message", "call", "text", "notify"
            ],
            "scheduling": [
                "schedule", "appointment", "meeting", "reminder", "calendar"
            ]
        }
