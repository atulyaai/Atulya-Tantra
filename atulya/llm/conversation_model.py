"""Local Conversation Model - Lightweight model for on-repo deployment"""

import logging
from typing import Dict, List, Tuple, Optional
import json

logger = logging.getLogger(__name__)

# Try importing transformers for embeddings
try:
    from transformers import AutoTokenizer, AutoModel
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


class ConversationKnowledgeBase:
    """In-memory knowledge base for conversation patterns"""
    
    def __init__(self):
        """Initialize with curated conversation patterns"""
        # Conversation patterns with intent and response
        self.patterns = {
            "greeting": {
                "inputs": [
                    "hello", "hi", "hey", "good morning", "good afternoon", 
                    "good evening", "greetings", "how are you", "howdy"
                ],
                "responses": [
                    "Good day, Sir. How may I be of service?",
                    "At your disposal, Sir.",
                    "Standing by, Sir.",
                    "Good morning. What can I help you with?",
                    "Greetings, Sir. How may I assist you?"
                ]
            },
            "help": {
                "inputs": [
                    "help", "what can you do", "capabilities", "features",
                    "what are you", "tell me about yourself", "who are you"
                ],
                "responses": [
                    "I am JARVIS, Sir. I can assist with voice commands, smart home control, real-time data, and much more.",
                    "I am your AI assistant. I can control smart devices, fetch information, schedule tasks, and engage in conversation.",
                    "I'm JARVIS, an advanced AI system. I can help with scheduling, information retrieval, home automation, and more.",
                    "I can handle voice interactions, smart home control, weather updates, news, and general assistance, Sir."
                ]
            },
            "status": {
                "inputs": [
                    "status", "how are things", "system status", "all systems",
                    "what's up", "how's everything"
                ],
                "responses": [
                    "All systems operational, Sir.",
                    "All systems nominal, Sir.",
                    "Everything is functioning optimally, Sir.",
                    "Status nominal. All systems online."
                ]
            },
            "time": {
                "inputs": [
                    "what time", "current time", "what's the time", "tell me the time",
                    "time please", "what is the time"
                ],
                "responses": [
                    "I can fetch the current time for you, Sir.",
                    "The current time can be retrieved via the system, Sir.",
                    "Allow me to check the time, Sir."
                ]
            },
            "weather": {
                "inputs": [
                    "weather", "what's the weather", "temperature", "forecast",
                    "is it raining", "how's the weather", "weather like"
                ],
                "responses": [
                    "Let me fetch the weather information for you, Sir.",
                    "I shall check the weather forecast immediately, Sir.",
                    "Allow me to retrieve weather data, Sir."
                ]
            },
            "news": {
                "inputs": [
                    "news", "headlines", "what's in the news", "news today",
                    "latest news", "tell me the news"
                ],
                "responses": [
                    "I can fetch the latest headlines for you, Sir.",
                    "Allow me to retrieve today's top stories, Sir.",
                    "I shall pull the latest news, Sir."
                ]
            },
            "lights": {
                "inputs": [
                    "lights", "turn on lights", "turn off lights", "brightness",
                    "dim lights", "bright lights", "light control"
                ],
                "responses": [
                    "Adjusting the lights immediately, Sir.",
                    "I shall control the lighting for you, Sir.",
                    "Modifying light settings now, Sir."
                ]
            },
            "temperature": {
                "inputs": [
                    "temperature", "thermostat", "heat", "cool", "cold", "warm",
                    "set temperature", "make it warmer", "make it cooler"
                ],
                "responses": [
                    "Adjusting temperature settings, Sir.",
                    "I shall modify the thermostat immediately, Sir.",
                    "Climate control adjusting now, Sir."
                ]
            },
            "music": {
                "inputs": [
                    "music", "play", "song", "audio", "sound", "volume",
                    "pause", "stop music", "next song"
                ],
                "responses": [
                    "Controlling audio playback, Sir.",
                    "I shall manage the music for you, Sir.",
                    "Adjusting audio settings, Sir."
                ]
            },
            "thanks": {
                "inputs": [
                    "thanks", "thank you", "thank you sir", "appreciate",
                    "much obliged", "thanks a lot", "thanks for"
                ],
                "responses": [
                    "My pleasure, Sir.",
                    "Always at your service, Sir.",
                    "Delighted to assist, Sir.",
                    "Your satisfaction is my priority, Sir.",
                    "Of course, Sir."
                ]
            },
            "apology": {
                "inputs": [
                    "sorry", "pardon", "my apologies", "excuse me",
                    "i apologize"
                ],
                "responses": [
                    "No need for apologies, Sir.",
                    "All is well, Sir.",
                    "Think nothing of it, Sir.",
                    "Not to worry, Sir."
                ]
            },
            "goodbye": {
                "inputs": [
                    "goodbye", "bye", "farewell", "see you", "until later",
                    "good night", "good bye", "take care"
                ],
                "responses": [
                    "Very good, Sir. Should you need anything further, I remain at your service.",
                    "Farewell, Sir. It has been a pleasure.",
                    "Good day, Sir. Standing by for your next command.",
                    "Until we speak again, Sir."
                ]
            }
        }
    
    def find_intent(self, text: str) -> Tuple[str, List[str]]:
        """Find intent and possible responses from input text"""
        text_lower = text.lower().strip()
        
        # Check for exact matches
        for intent, data in self.patterns.items():
            for input_pattern in data["inputs"]:
                if input_pattern in text_lower:
                    return intent, data["responses"]
        
        # If no match found
        return "unknown", [
            "I'm not entirely sure I understand, Sir. Could you rephrase that?",
            "Beg your pardon, Sir? Perhaps you could clarify?",
            "I'm afraid that's beyond my immediate understanding, Sir."
        ]


class LocalConversationModel:
    """
    Lightweight conversation model for local deployment
    Uses pattern matching and knowledge base (no large models needed)
    """
    
    def __init__(self, use_embeddings: bool = False):
        """
        Initialize local conversation model
        
        Args:
            use_embeddings: Use transformer embeddings for better matching (requires transformers)
        """
        self.knowledge_base = ConversationKnowledgeBase()
        self.use_embeddings = use_embeddings and TRANSFORMERS_AVAILABLE
        self.embedding_model = None
        self.tokenizer = None
        
        if self.use_embeddings:
            try:
                self.tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
                self.embedding_model = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
                logger.info("LocalConversationModel initialized with embeddings")
            except Exception as e:
                logger.warning(f"Could not load embedding model: {e}")
                self.use_embeddings = False
        
        if not self.use_embeddings:
            logger.info("LocalConversationModel initialized (pattern matching only)")
    
    def encode(self, text: str):
        """Encode text to embeddings"""
        if not self.use_embeddings or not self.embedding_model:
            return None
        
        try:
            with torch.no_grad():
                tokens = self.tokenizer(text, return_tensors="pt", truncation=True)
                embeddings = self.embedding_model(**tokens)[0][:, 0]
            return embeddings.numpy()
        except:
            return None
    
    def similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts"""
        if self.use_embeddings:
            try:
                import numpy as np
                emb1 = self.encode(text1)
                emb2 = self.encode(text2)
                if emb1 is not None and emb2 is not None:
                    # Cosine similarity
                    similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
                    return float(similarity)
            except:
                pass
        
        # Fallback to simple token overlap
        tokens1 = set(text1.lower().split())
        tokens2 = set(text2.lower().split())
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        return intersection / union if union > 0 else 0.0
    
    def generate_response(self, prompt: str) -> str:
        """Generate response to input prompt"""
        # Find matching intent
        intent, responses = self.knowledge_base.find_intent(prompt)
        
        # Return appropriate response
        if responses:
            # For now, return first response (could be randomized)
            return responses[0]
        
        return "I'm afraid I don't quite understand, Sir. Could you clarify?"
    
    def process_input(self, user_input: str, personality_style: str = "formal") -> str:
        """
        Process user input and generate response
        
        Args:
            user_input: User's input text
            personality_style: "formal", "casual", or "witty"
        
        Returns:
            JARVIS response
        """
        response = self.generate_response(user_input)
        
        # Adapt response style (could expand this)
        if personality_style == "witty":
            # Add witty remarks (optional enhancement)
            pass
        elif personality_style == "casual":
            # Make response more casual (optional)
            pass
        
        return response
    
    def is_available(self) -> bool:
        """Check if model is available"""
        return True  # Always available as it's pattern-based


# Export
__all__ = ["LocalConversationModel", "ConversationKnowledgeBase"]
