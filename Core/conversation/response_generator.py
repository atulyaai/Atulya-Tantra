"""
Dynamic Response Generator
Generates contextual and natural responses based on intent and conversation flow
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime

class ResponseGenerator:
    """
    Advanced response generator that creates natural, contextual responses
    based on user intent and conversation flow
    """
    
    def __init__(self, llm_provider):
        self.llm_provider = llm_provider
        self.response_templates = self._load_response_templates()
        self.capability_descriptions = self._load_capability_descriptions()
    
    def generate(self, message: str, intent: Dict[str, Any], actions: List[Any], 
                context, flow_analysis: Dict[str, Any]) -> str:
        """
        Generate dynamic response based on analysis
        """
        intent_type = intent.get('type', 'general_conversation')
        confidence = intent.get('confidence', 0.8)
        
        # Handle greetings
        if intent_type == 'greeting':
            return self._generate_greeting_response(context)
        
        # Handle farewells
        elif intent_type == 'farewell':
            return self._generate_farewell_response(context)
        
        # Handle capability inquiries
        elif intent_type == 'capability_inquiry':
            return self._generate_capability_response()
        
        # Handle action requests
        elif intent_type == 'action_request':
            return self._generate_action_response(intent, actions, context)
        
        # Handle information requests
        elif intent_type == 'information_request':
            return self._generate_information_response(intent, context)
        
        # Handle general conversation
        else:
            return self._generate_general_response(message, intent, context)
    
    def _generate_greeting_response(self, context) -> str:
        """Generate greeting response"""
        user_name = context.user_preferences.get('name', 'there')
        time_of_day = self._get_time_of_day()
        
        greetings = [
            f"Hello {user_name}! {time_of_day} How can I assist you today?",
            f"Hi {user_name}! {time_of_day} What would you like me to help you with?",
            f"Good {time_of_day.lower()}, {user_name}! I'm here to help. What can I do for you?",
            f"Hello! {time_of_day} I'm ready to assist you with any tasks or questions you have."
        ]
        
        return self._select_random_response(greetings)
    
    def _generate_farewell_response(self, context) -> str:
        """Generate farewell response"""
        farewells = [
            "Goodbye! Have a great day!",
            "See you later! Feel free to ask if you need anything else.",
            "Take care! I'll be here whenever you need assistance.",
            "Goodbye! It was nice helping you today."
        ]
        
        return self._select_random_response(farewells)
    
    def _generate_capability_response(self) -> str:
        """Generate capability description response"""
        capabilities = self.capability_descriptions
        
        response = "I'm a professional AI assistant with a wide range of capabilities:\n\n"
        
        for category, features in capabilities.items():
            response += f"**{category.replace('_', ' ').title()}:**\n"
            for feature in features:
                response += f"• {feature}\n"
            response += "\n"
        
        response += "I can help you with system control, web searches, communication, scheduling, and much more. What would you like me to help you with?"
        
        return response
    
    def _generate_action_response(self, intent: Dict[str, Any], actions: List[Any], context) -> str:
        """Generate response for action requests"""
        action = intent.get('action', '')
        parameters = intent.get('parameters', {})
        
        if action == 'application_control':
            app = parameters.get('application', 'application')
            return f"I'll open {app} for you right away."
        
        elif action == 'window_management':
            window_action = parameters.get('action', 'manage')
            return f"I'll {window_action} the window for you."
        
        elif action == 'volume_control':
            volume_action = parameters.get('action', 'adjust')
            return f"I'll {volume_action} the volume for you."
        
        elif action == 'screenshot':
            return "I'll take a screenshot for you."
        
        elif action == 'web_search':
            query = parameters.get('query', 'your search')
            return f"I'll search for '{query}' and provide you with the results."
        
        elif action == 'communication':
            comm_type = parameters.get('type', 'message')
            return f"I'll help you with {comm_type} communication."
        
        elif action == 'scheduling':
            schedule_type = parameters.get('type', 'event')
            return f"I'll help you schedule a {schedule_type}."
        
        else:
            return "I'll help you with that task."
    
    def _generate_information_response(self, intent: Dict[str, Any], context) -> str:
        """Generate response for information requests"""
        info_type = intent.get('parameters', {}).get('type', '')
        
        if info_type == 'weather':
            return "I'll get the current weather information for you."
        
        elif info_type == 'time':
            current_time = datetime.now().strftime('%I:%M %p')
            return f"The current time is {current_time}."
        
        elif info_type == 'date':
            current_date = datetime.now().strftime('%B %d, %Y')
            return f"Today's date is {current_date}."
        
        else:
            return "I'll get that information for you."
    
    def _generate_general_response(self, message: str, intent: Dict[str, Any], context) -> str:
        """Generate general conversation response"""
        # Use LLM for general conversation
        if self.llm_provider:
            try:
                response = self.llm_provider.generate_response(
                    message=message,
                    context=context.conversation_history[-5:] if context.conversation_history else [],
                    max_tokens=150
                )
                return response
            except Exception as e:
                return f"I understand you're asking about '{message}'. Could you provide more details so I can help you better?"
        
        return "I understand. How can I assist you with that?"
    
    def _get_time_of_day(self) -> str:
        """Get appropriate time of day greeting"""
        hour = datetime.now().hour
        
        if 5 <= hour < 12:
            return "Good morning!"
        elif 12 <= hour < 17:
            return "Good afternoon!"
        elif 17 <= hour < 21:
            return "Good evening!"
        else:
            return "Good evening!"
    
    def _select_random_response(self, responses: List[str]) -> str:
        """Select a random response from a list"""
        import random
        return random.choice(responses)
    
    def _load_response_templates(self) -> Dict[str, List[str]]:
        """Load response templates for different scenarios"""
        return {
            "greetings": [
                "Hello! How can I assist you today?",
                "Hi there! What would you like me to help you with?",
                "Good to see you! How can I be of service?",
                "Hello! I'm ready to help. What do you need?"
            ],
            "farewells": [
                "Goodbye! Have a great day!",
                "See you later! Feel free to ask if you need anything.",
                "Take care! I'll be here whenever you need help.",
                "Goodbye! It was nice helping you."
            ],
            "confirmations": [
                "I'll take care of that for you.",
                "Consider it done!",
                "I'm on it right away.",
                "I'll handle that for you."
            ],
            "clarifications": [
                "Could you please provide more details?",
                "I need a bit more information to help you better.",
                "Could you clarify what you'd like me to do?",
                "I want to make sure I understand correctly. Could you elaborate?"
            ]
        }
    
    def _load_capability_descriptions(self) -> Dict[str, List[str]]:
        """Load detailed capability descriptions"""
        return {
            "system_control": [
                "Open and close applications",
                "Manage windows (minimize, maximize, restore)",
                "Control system volume",
                "Take screenshots",
                "Lock screen and system management"
            ],
            "web_services": [
                "Search the internet for information",
                "Get weather forecasts",
                "Find news and current events",
                "Look up definitions and facts",
                "Access real-time data"
            ],
            "communication": [
                "Send emails",
                "Create and send messages",
                "Set up notifications",
                "Manage contacts and communication"
            ],
            "scheduling": [
                "Schedule appointments and meetings",
                "Set reminders and alarms",
                "Manage calendar events",
                "Book reservations",
                "Plan and organize tasks"
            ],
            "information_retrieval": [
                "Answer questions on various topics",
                "Provide explanations and tutorials",
                "Look up specific information",
                "Share knowledge and insights"
            ],
            "creative_tasks": [
                "Help with writing and editing",
                "Generate creative content",
                "Assist with problem-solving",
                "Provide suggestions and recommendations"
            ]
        }
