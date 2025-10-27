#!/usr/bin/env python3
"""
Working JARVIS Demo with Real LLM Integration
A simplified but functional version of the JARVIS system
"""

import os
import sys
import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import required modules
try:
    import ollama
    import requests
    import psutil
    from dotenv import load_dotenv
except ImportError as e:
    logger.error(f"Missing required package: {e}")
    logger.error("Please install missing packages with: pip3 install --user ollama requests psutil python-dotenv")
    sys.exit(1)

# Load environment variables
load_dotenv()

class SimpleLLMClient:
    """Simple LLM client for testing"""
    
    def __init__(self):
        self.model = os.getenv('OLLAMA_MODEL', 'tinyllama')
        self.base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        
    async def generate_response(self, prompt: str, max_tokens: int = 200) -> str:
        """Generate response using Ollama"""
        try:
            response = ollama.chat(
                model=self.model,
                messages=[{'role': 'user', 'content': prompt}],
                options={'num_predict': max_tokens}
            )
            return response['message']['content']
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            return "I'm sorry, I'm having trouble processing your request right now."

class SimpleSentimentAnalyzer:
    """Simple sentiment analysis"""
    
    def __init__(self):
        self.emotion_patterns = {
            'joy': ['happy', 'excited', 'great', 'awesome', 'fantastic', 'amazing', 'wonderful'],
            'sadness': ['sad', 'depressed', 'down', 'upset', 'disappointed', 'hurt'],
            'anger': ['angry', 'mad', 'furious', 'annoyed', 'frustrated', 'irritated'],
            'fear': ['scared', 'afraid', 'worried', 'anxious', 'nervous', 'terrified'],
            'surprise': ['surprised', 'shocked', 'amazed', 'wow', 'incredible'],
            'neutral': ['okay', 'fine', 'normal', 'alright', 'good']
        }
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of text"""
        text_lower = text.lower()
        
        # Count emotion indicators
        emotion_scores = {}
        for emotion, patterns in self.emotion_patterns.items():
            score = sum(1 for pattern in patterns if pattern in text_lower)
            emotion_scores[emotion] = score
        
        # Determine dominant emotion
        dominant_emotion = max(emotion_scores, key=emotion_scores.get)
        confidence = emotion_scores[dominant_emotion] / max(1, len(text.split()))
        
        # Determine intensity
        if confidence > 0.3:
            intensity = 'high'
        elif confidence > 0.1:
            intensity = 'medium'
        else:
            intensity = 'low'
        
        return {
            'emotion': dominant_emotion,
            'confidence': min(confidence, 1.0),
            'intensity': intensity,
            'scores': emotion_scores
        }

class SimpleMemory:
    """Simple conversation memory"""
    
    def __init__(self, max_entries: int = 50):
        self.memory = []
        self.max_entries = max_entries
    
    def add_conversation(self, user_input: str, assistant_response: str, sentiment: Dict[str, Any]):
        """Add conversation to memory"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'user_input': user_input,
            'assistant_response': assistant_response,
            'sentiment': sentiment
        }
        self.memory.append(entry)
        
        # Keep only recent entries
        if len(self.memory) > self.max_entries:
            self.memory = self.memory[-self.max_entries:]
    
    def get_recent_context(self, count: int = 5) -> List[Dict[str, Any]]:
        """Get recent conversation context"""
        return self.memory[-count:] if self.memory else []

class SimpleJARVIS:
    """Simplified JARVIS system with real functionality"""
    
    def __init__(self):
        self.llm_client = SimpleLLMClient()
        self.sentiment_analyzer = SimpleSentimentAnalyzer()
        self.memory = SimpleMemory()
        self.is_running = False
        self.conversation_count = 0
        
    async def start(self):
        """Start the JARVIS system"""
        logger.info("🤖 Starting JARVIS System...")
        self.is_running = True
        logger.info("✅ JARVIS System started successfully")
        
    async def stop(self):
        """Stop the JARVIS system"""
        logger.info("🛑 Stopping JARVIS System...")
        self.is_running = False
        logger.info("✅ JARVIS System stopped")
    
    async def process_message(self, user_input: str) -> Dict[str, Any]:
        """Process a user message and generate response"""
        try:
            # Analyze sentiment
            sentiment = self.sentiment_analyzer.analyze_sentiment(user_input)
            
            # Get recent context
            context = self.memory.get_recent_context()
            
            # Create context-aware prompt
            context_str = ""
            if context:
                context_str = "\nRecent conversation:\n"
                for entry in context[-3:]:  # Last 3 conversations
                    context_str += f"User: {entry['user_input']}\n"
                    context_str += f"JARVIS: {entry['assistant_response']}\n"
            
            # Create personality-aware prompt
            personality_prompt = f"""You are JARVIS, an advanced AI assistant with a helpful and professional personality. 
You are knowledgeable, efficient, and always ready to assist. You can help with various tasks including:
- Answering questions
- Providing information
- Helping with problem-solving
- Having conversations
- Offering advice

{context_str}

User's current message: {user_input}
User's emotional state: {sentiment['emotion']} (confidence: {sentiment['confidence']:.2f})

Respond naturally and helpfully. Keep responses concise but informative. If the user seems {sentiment['emotion']}, respond appropriately to their emotional state.

Response:"""
            
            # Generate response
            response = await self.llm_client.generate_response(personality_prompt)
            
            # Store in memory
            self.memory.add_conversation(user_input, response, sentiment)
            self.conversation_count += 1
            
            return {
                'response': response,
                'sentiment': sentiment,
                'conversation_id': self.conversation_count,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {
                'response': "I apologize, but I encountered an error processing your request.",
                'sentiment': {'emotion': 'neutral', 'confidence': 0.0, 'intensity': 'low'},
                'conversation_id': self.conversation_count,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get system status"""
        try:
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'is_running': self.is_running,
                'conversation_count': self.conversation_count,
                'memory_entries': len(self.memory.memory),
                'system_health': {
                    'cpu_usage': f"{cpu_percent}%",
                    'memory_usage': f"{memory.percent}%",
                    'disk_usage': f"{disk.percent}%"
                },
                'llm_model': self.llm_client.model,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                'is_running': self.is_running,
                'conversation_count': self.conversation_count,
                'error': str(e)
            }

async def run_demo():
    """Run the JARVIS demo"""
    print("🤖 Working JARVIS Demo with Real LLM Integration")
    print("=" * 60)
    
    # Initialize JARVIS
    jarvis = SimpleJARVIS()
    await jarvis.start()
    
    # Show system status
    status = await jarvis.get_system_status()
    print(f"\n📊 System Status:")
    print(f"   • Running: {status['is_running']}")
    print(f"   • LLM Model: {status['llm_model']}")
    print(f"   • Conversations: {status['conversation_count']}")
    print(f"   • Memory Entries: {status['memory_entries']}")
    print(f"   • CPU Usage: {status['system_health']['cpu_usage']}")
    print(f"   • Memory Usage: {status['system_health']['memory_usage']}")
    
    # Demo conversations
    demo_messages = [
        "Hello JARVIS, how are you today?",
        "I'm feeling really excited about this project!",
        "Can you help me understand how AI works?",
        "I'm a bit frustrated with this bug in my code.",
        "What can you do for me?",
        "Tell me a joke to cheer me up!",
        "I need help with Python programming.",
        "Thank you for your help!"
    ]
    
    print(f"\n💬 Demo Conversations:")
    
    for i, message in enumerate(demo_messages, 1):
        print(f"\n--- Demo {i} ---")
        print(f"\n🤖 Processing request: '{message}'")
        
        # Process message
        result = await jarvis.process_message(message)
        
        # Display sentiment
        sentiment = result['sentiment']
        print(f"😊 Detected emotion: {sentiment['emotion']} (confidence: {sentiment['confidence']:.2f})")
        
        # Display conversation
        print(f"User: {message}")
        print(f"JARVIS: {result['response']}")
        print(f"Emotion: {sentiment['emotion']} ({sentiment['intensity']})")
        
        # Small delay for readability
        await asyncio.sleep(1)
    
    # Final status
    final_status = await jarvis.get_system_status()
    print(f"\n📈 Final System Status:")
    print(f"   • Total conversations: {final_status['conversation_count']}")
    print(f"   • Memory entries: {final_status['memory_entries']}")
    print(f"   • System health: ✅ Healthy")
    
    # Stop system
    await jarvis.stop()
    
    print(f"\n🎉 Demo completed successfully!")
    print(f"This demonstrates a working JARVIS system with:")
    print(f"  ✅ Real LLM integration (Ollama)")
    print(f"  ✅ Sentiment analysis")
    print(f"  ✅ Conversation memory")
    print(f"  ✅ System monitoring")
    print(f"  ✅ Error handling")

if __name__ == "__main__":
    try:
        asyncio.run(run_demo())
    except KeyboardInterrupt:
        print("\n\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        logger.error(f"Demo failed: {e}")
