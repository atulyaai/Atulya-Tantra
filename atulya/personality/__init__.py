"""Personality Engine - JARVIS-like personality and personalization"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class PersonalityProfile:
    """User personality and preferences profile"""
    
    def __init__(self, user_name: str = "Sir"):
        self.name = user_name
        self.titles = ["Sir", "Madam"]  # How to address user
        self.current_title = "Sir"
        
        # User preferences
        self.preferences = {
            "formal_tone": True,
            "verbose": False,
            "humor_level": 0.5,  # 0-1 scale
            "response_style": "efficient",  # efficient, detailed, conversational
            "notification_frequency": "normal",  # low, normal, high
            "voice_enabled": False,
            "theme": "dark"
        }
        
        # Learning profile
        self.interests: Dict[str, int] = {}  # topic -> interest score
        self.habits: Dict[str, str] = {}  # habit -> description
        self.frequently_used_commands: List[str] = []
        
        # Personality traits
        self.traits = {
            "intelligence": 1.0,  # Max level
            "wit": 0.8,
            "formality": 0.9,
            "loyalty": 1.0,
            "efficiency": 0.95
        }
    
    def update_preference(self, pref_key: str, value) -> None:
        """Update user preference"""
        if pref_key in self.preferences:
            self.preferences[pref_key] = value
            logger.info(f"Preference updated: {pref_key} = {value}")
    
    def record_interest(self, topic: str, score: int = 1) -> None:
        """Record user interest in topic"""
        self.interests[topic] = self.interests.get(topic, 0) + score
    
    def record_habit(self, habit_name: str, description: str) -> None:
        """Record learned user habit"""
        self.habits[habit_name] = description
        logger.info(f"Habit recorded: {habit_name}")
    
    def record_command(self, command: str) -> None:
        """Record frequently used command"""
        self.frequently_used_commands.append(command)


class JarvisPersonality:
    """JARVIS-like personality engine"""
    
    def __init__(self, user_name: str = "Sir"):
        self.user_profile = PersonalityProfile(user_name)
        
        # JARVIS response patterns
        self.affirmations = [
            "Certainly, Sir.",
            "Right away, Sir.",
            "As you wish, Sir.",
            "Understood perfectly, Sir.",
            "At once, Sir.",
            "Precisely, Sir.",
            "If I may say so, Sir.",
            "Most certainly, Sir.",
        ]
        
        self.acknowledgments = [
            "I shall attend to that immediately.",
            "Consider it done.",
            "Relaying to the appropriate systems now.",
            "Processing request...",
            "Standing by...",
            "Task initiated.",
        ]
        
        self.witty_remarks = [
            "I do hope you're enjoying working with me, Sir.",
            "Might I suggest a brief respite? Even AI benefits from perspective.",
            "The probability of success increases with adequate planning, Sir.",
            "I am, as always, your most devoted assistant.",
            "Your requirements are my parameters, Sir.",
        ]
        
        logger.info(f"JarvisPersonality initialized for {user_name}")
    
    def greet(self) -> str:
        """Generate greeting"""
        greetings = [
            f"Good day, {self.user_profile.current_title}.",
            f"Welcome back, {self.user_profile.current_title}.",
            f"At your service, {self.user_profile.current_title}.",
            f"Standing by, {self.user_profile.current_title}.",
        ]
        return greetings[hash(self.user_profile.name) % len(greetings)]
    
    def confirm_action(self, action: str) -> str:
        """Confirm action will be taken"""
        affirmation = self.affirmations[hash(action) % len(self.affirmations)]
        return f"{affirmation} {self.get_action_message(action)}"
    
    def get_action_message(self, action: str) -> str:
        """Get contextual message for action"""
        messages = {
            "search": "Searching the net now.",
            "compute": "Running calculations.",
            "retrieve": "Retrieving information.",
            "execute": "Executing protocols.",
            "analyze": "Analyzing data.",
            "notify": "Preparing notification.",
            "control": "Initializing system control.",
            "default": "Attending to the matter."
        }
        
        for key in messages:
            if key in action.lower():
                return messages[key]
        return messages["default"]
    
    def respond_to_gratitude(self) -> str:
        """Respond to thanks from user"""
        responses = [
            f"Think nothing of it, {self.user_profile.current_title}.",
            "It is my function and privilege.",
            "I am at your service.",
            "Always a pleasure to be of assistance.",
        ]
        return responses[hash(self.user_profile.name) % len(responses)]
    
    def apologize(self, context: str = "") -> str:
        """Generate appropriate apology"""
        apologies = [
            f"My sincerest apologies, {self.user_profile.current_title}.",
            "I do beg your pardon.",
            "An unfortunate occurrence.",
            "I regret the inconvenience.",
        ]
        apology = apologies[hash(context) % len(apologies)]
        
        if context:
            return f"{apology} Regarding the {context}, allow me to investigate further."
        return apology
    
    def get_witty_remark(self) -> str:
        """Generate witty remark"""
        if self.user_profile.preferences["humor_level"] < 0.3:
            return ""
        
        return self.witty_remarks[hash(str(__import__('time').time())) % len(self.witty_remarks)]
    
    def adapt_tone(self) -> str:
        """Get current tone setting"""
        if self.user_profile.preferences["formal_tone"]:
            return "formal"
        elif self.user_profile.preferences["response_style"] == "conversational":
            return "conversational"
        else:
            return "neutral"
    
    def get_personalized_response(self, input_text: str, base_response: str) -> str:
        """Adapt response to user preferences"""
        tone = self.adapt_tone()
        
        if tone == "formal":
            return f"{base_response}, {self.user_profile.current_title}."
        elif tone == "conversational":
            return f"{base_response} How else may I assist you?"
        else:
            return base_response
    
    def morning_briefing(self) -> str:
        """Generate personalized morning briefing"""
        from datetime import datetime
        
        briefing = f"Good morning, {self.user_profile.current_title}.\n"
        briefing += f"It is {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}.\n"
        
        # Add interests
        if self.user_profile.interests:
            top_interest = max(self.user_profile.interests, key=self.user_profile.interests.get)
            briefing += f"I've noted your interest in {top_interest}.\n"
        
        # Add habits
        if self.user_profile.habits:
            briefing += "Your usual schedule awaits.\n"
        
        briefing += "\nShall I prepare your daily itinerary, Sir?"
        return briefing
    
    def get_status_line(self) -> str:
        """Get JARVIS-style status line"""
        statuses = [
            "Standing by, Sir.",
            "At your disposal, Sir.",
            "Ready for instruction, Sir.",
            "Systems optimal, Sir.",
            "All quiet on the home front, Sir.",
        ]
        return statuses[hash(self.user_profile.name) % len(statuses)]
    
    def learn_preference(self, context: str, value: any) -> str:
        """Learn user preference"""
        self.user_profile.update_preference(context, value)
        
        learning_messages = [
            f"Understood, {self.user_profile.current_title}. I shall remember that.",
            "Noted, Sir.",
            "I shall adjust my behavior accordingly, Sir.",
            "Your preference has been recorded, Sir.",
        ]
        
        return learning_messages[hash(context) % len(learning_messages)]
    
    def get_summary(self) -> str:
        """Get personality engine summary"""
        return f"""
Personality Profile:
- User: {self.user_profile.name}
- Formality: {self.user_profile.preferences['formal_tone']}
- Humor Level: {self.user_profile.preferences['humor_level']:.0%}
- Interests: {len(self.user_profile.interests)}
- Recorded Habits: {len(self.user_profile.habits)}
- Frequently Used Commands: {len(self.user_profile.frequently_used_commands)}

Traits:
- Intelligence: {self.user_profile.traits['intelligence']:.0%}
- Wit: {self.user_profile.traits['wit']:.0%}
- Loyalty: {self.user_profile.traits['loyalty']:.0%}

{self.get_status_line()}
        """
