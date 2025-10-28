#!/usr/bin/env python3
"""
Simple Working Demo of Atulya Tantra AGI System
A minimal working version that demonstrates the core functionality
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

# Simple mock implementations for demonstration
class SimpleSentimentAnalyzer:
    """Simple sentiment analyzer for demo purposes"""
    
    def __init__(self):
        self.emotion_patterns = {
            "joy": ["happy", "excited", "great", "awesome", "amazing", "fantastic"],
            "sadness": ["sad", "depressed", "down", "disappointed", "upset"],
            "anger": ["angry", "mad", "furious", "frustrated", "annoyed"],
            "fear": ["scared", "afraid", "worried", "anxious", "nervous"],
            "surprise": ["surprised", "shocked", "wow", "unexpected"],
            "neutral": ["okay", "fine", "alright", "normal"]
        }
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of text"""
        text_lower = text.lower()
        
        for emotion, keywords in self.emotion_patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                return {
                    "emotion": emotion,
                    "confidence": 0.8,
                    "intensity": "high" if any(word in text_lower for word in ["very", "really", "so", "extremely"]) else "medium"
                }
        
        return {
            "emotion": "neutral",
            "confidence": 0.5,
            "intensity": "low"
        }

class SimpleLLMProvider:
    """Simple LLM provider for demo purposes"""
    
    def __init__(self):
        self.responses = {
            "greeting": [
                "Hello! I'm JARVIS, your AI assistant. How can I help you today?",
                "Greetings! I'm here to assist you with various tasks.",
                "Hi there! I'm JARVIS, ready to help you with anything you need."
            ],
            "help": [
                "I can help you with various tasks including system control, information retrieval, and general assistance.",
                "I'm equipped to handle system operations, answer questions, and provide helpful information.",
                "I can assist with multiple functions - just let me know what you need help with."
            ],
            "default": [
                "I understand. Let me help you with that.",
                "That's interesting. I can assist you with this.",
                "I see what you're asking about. Here's how I can help."
            ]
        }
    
    async def generate_response(self, prompt: str, max_tokens: int = 200, temperature: float = 0.7) -> str:
        """Generate a response based on the prompt"""
        # Simple keyword-based response selection
        prompt_lower = prompt.lower()
        
        if any(word in prompt_lower for word in ["hello", "hi", "hey", "greetings"]):
            import random
            return random.choice(self.responses["greeting"])
        elif any(word in prompt_lower for word in ["help", "what can you do", "capabilities"]):
            import random
            return random.choice(self.responses["help"])
        else:
            import random
            return random.choice(self.responses["default"])

class SimpleAGICore:
    """Simple AGI core for demo purposes"""
    
    def __init__(self):
        self.sentiment_analyzer = SimpleSentimentAnalyzer()
        self.llm_provider = SimpleLLMProvider()
        self.conversation_history = []
        self.active_goals = []
    
    async def process_request(self, user_input: str, user_id: str = "demo_user") -> Dict[str, Any]:
        """Process a user request"""
        print(f"\n🤖 Processing request: '{user_input}'")
        
        # Analyze sentiment
        sentiment = self.sentiment_analyzer.analyze_sentiment(user_input)
        print(f"😊 Detected emotion: {sentiment['emotion']} (confidence: {sentiment['confidence']})")
        
        # Generate response
        response = await self.llm_provider.generate_response(user_input)
        
        # Add to conversation history
        self.conversation_history.append({
            "user": user_input,
            "assistant": response,
            "timestamp": datetime.now().isoformat(),
            "sentiment": sentiment
        })
        
        return {
            "success": True,
            "response": response,
            "sentiment": sentiment,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status"""
        return {
            "is_active": True,
            "conversation_count": len(self.conversation_history),
            "active_goals": len(self.active_goals),
            "last_activity": self.conversation_history[-1]["timestamp"] if self.conversation_history else None
        }
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get system capabilities"""
        return {
            "sentiment_analysis": "Emotion detection and analysis",
            "conversation": "Natural language processing and response generation",
            "memory": "Conversation history and context awareness",
            "reasoning": "Basic decision making and goal management"
        }

class SimpleAGISystem:
    """Simple unified AGI system for demo"""
    
    def __init__(self):
        self.agi_core = SimpleAGICore()
        self.is_running = False
        self.mode = "conversational"
    
    async def start(self):
        """Start the AGI system"""
        print("🚀 Starting Simple AGI System...")
        self.is_running = True
        print("✅ System started successfully")
    
    async def stop(self):
        """Stop the AGI system"""
        print("🛑 Stopping AGI System...")
        self.is_running = False
        print("✅ System stopped")
    
    async def process_message(self, message: str, user_id: str = "demo_user") -> Dict[str, Any]:
        """Process a user message"""
        if not self.is_running:
            return {"success": False, "error": "System not running"}
        
        return await self.agi_core.process_request(message, user_id)
    
    def get_status(self) -> Dict[str, Any]:
        """Get system status"""
        return {
            "is_running": self.is_running,
            "mode": self.mode,
            "core_status": self.agi_core.get_system_status()
        }

async def run_demo():
    """Run the demo"""
    print("🤖 Simple Atulya Tantra AGI System Demo")
    print("=" * 50)
    
    # Create and start the system
    system = SimpleAGISystem()
    await system.start()
    
    # Show system status
    print("\n📊 System Status:")
    status = system.get_status()
    print(f"   • Running: {status['is_running']}")
    print(f"   • Mode: {status['mode']}")
    print(f"   • Conversations: {status['core_status']['conversation_count']}")
    
    # Show capabilities
    print("\n🔧 System Capabilities:")
    capabilities = system.agi_core.get_capabilities()
    for capability, description in capabilities.items():
        print(f"   • {capability.replace('_', ' ').title()}: {description}")
    
    # Demo conversations
    print("\n💬 Demo Conversations:")
    demo_messages = [
        "Hello JARVIS, how are you today?",
        "I'm feeling really excited about this project!",
        "Can you help me with something?",
        "I'm a bit frustrated with this bug in my code.",
        "What can you do for me?"
    ]
    
    for i, message in enumerate(demo_messages, 1):
        print(f"\n--- Demo {i} ---")
        result = await system.process_message(message, f"demo_user_{i}")
        
        if result["success"]:
            print(f"User: {message}")
            print(f"JARVIS: {result['response']}")
            print(f"Emotion: {result['sentiment']['emotion']} ({result['sentiment']['intensity']})")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
        
        # Small delay between messages
        await asyncio.sleep(1)
    
    # Show final status
    print("\n📈 Final System Status:")
    final_status = system.get_status()
    print(f"   • Total conversations: {final_status['core_status']['conversation_count']}")
    print(f"   • System health: {'✅ Healthy' if final_status['is_running'] else '❌ Stopped'}")
    
    # Stop the system
    await system.stop()
    
    print("\n🎉 Demo completed successfully!")
    print("This demonstrates the basic functionality of the AGI system.")
    print("In a full implementation, this would include:")
    print("  • Real LLM integration (OpenAI, Anthropic, Ollama)")
    print("  • Actual voice recognition and synthesis")
    print("  • Advanced sentiment analysis")
    print("  • Database persistence")
    print("  • Web interface")
    print("  • Real-time streaming")

if __name__ == "__main__":
    asyncio.run(run_demo())
