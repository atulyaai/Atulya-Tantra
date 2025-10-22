"""
Test Tantra's Context System
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the TantraBrain class directly
import requests
import threading
import time
import re

class TantraBrain:
    """Keeps Gemma2 model loaded and responsive"""
    def __init__(self, model="gemma2:2b", base_url="http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.session = requests.Session()
        self.model_loaded = False
        self.conversation_history = []  # Store conversation context
        self.load_model()
        # Keep brain alive
        threading.Thread(target=self.keep_alive, daemon=True).start()
    
    def load_model(self):
        """Pre-load model"""
        try:
            print("🧠 Initializing Tantra's brain...")
            response = self.session.post(f"{self.base_url}/api/generate",
                json={
                    'model': self.model,
                    'prompt': "Hello",
                    'stream': False,
                    'options': {'max_tokens': 5}
                }, timeout=30)
            
            if response.status_code == 200:
                self.model_loaded = True
                print("✅ Tantra's brain is ready")
            else:
                print("❌ Brain initialization failed")
        except Exception as e:
            print(f"❌ Brain error: {e}")
    
    def generate_response(self, message, max_tokens=50):
        """Generate AI response with emoji removal"""
        if not self.model_loaded:
            return "Brain not ready"
        
        try:
            # Detect if user wants detailed response
            detail_keywords = ['explain', 'tell me about', 'describe', 'how does', 'what is', 'why', 'detailed', 'more info']
            wants_detail = any(keyword in message.lower() for keyword in detail_keywords)
            
            # Adjust tokens based on detail request
            tokens = 100 if wants_detail else 30
            
            # Create context-aware prompt
            context_prompt = self.build_context_prompt(message)
            
            response = self.session.post(f"{self.base_url}/api/generate",
                json={
                    'model': self.model,
                    'prompt': context_prompt,
                    'stream': False,
                    'options': {
                        'temperature': 0.3,
                        'max_tokens': tokens,
                        'num_predict': tokens
                    }
                }, timeout=8)
            
            if response.status_code == 200:
                data = response.json()
                response_text = data['response'].strip()
                
                # Remove ALL emojis completely
                emoji_pattern = re.compile("["
                    u"\U0001F600-\U0001F64F"  # emoticons
                    u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                    u"\U0001F680-\U0001F6FF"  # transport & map symbols
                    u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                    u"\U00002702-\U000027B0"  # dingbats
                    u"\U000024C2-\U0001F251"  # enclosed characters
                    "]+", flags=re.UNICODE)
                
                clean_response = emoji_pattern.sub('', response_text).strip()
                
                # Add response to conversation history
                self.add_response_to_history(clean_response)
                
                return clean_response
            else:
                return "Brain error"
                
        except Exception as e:
            return f"Error: {e}"
    
    def build_context_prompt(self, message):
        """Build context-aware prompt with conversation history"""
        # Add current message to history
        self.conversation_history.append({"role": "user", "content": message})
        
        # Keep only last 6 exchanges (3 user + 3 assistant) for context
        if len(self.conversation_history) > 12:
            self.conversation_history = self.conversation_history[-12:]
        
        # Build context string
        context = "You are Tantra, a helpful AI assistant. You are NOT Gemma. Your name is Tantra.\n\n"
        
        # Add recent conversation context
        if len(self.conversation_history) > 1:
            context += "Recent conversation:\n"
            for i in range(max(0, len(self.conversation_history) - 6), len(self.conversation_history) - 1):
                if self.conversation_history[i]["role"] == "user":
                    context += f"User: {self.conversation_history[i]['content']}\n"
                else:
                    context += f"Tantra: {self.conversation_history[i]['content']}\n"
            context += "\n"
        
        # Add current question
        context += f"User asks: {message}\n"
        context += "Tantra responds:"
        
        return context
    
    def add_response_to_history(self, response):
        """Add Tantra's response to conversation history"""
        self.conversation_history.append({"role": "assistant", "content": response})
    
    def keep_alive(self):
        """Ping model every minute to keep loaded"""
        while True:
            time.sleep(60)
            try:
                self.generate_response("ping", 1)
            except:
                pass

def test_context_system():
    print("🧪 Testing Tantra's context system...")
    
    brain = TantraBrain()
    
    # Test 1: Name identification
    print("\n1. Testing name identification:")
    response1 = brain.generate_response("What's your name?")
    print(f"Response: {response1}")
    
    # Test 2: Context awareness
    print("\n2. Testing context awareness:")
    response2 = brain.generate_response("I like pizza")
    print(f"Response: {response2}")
    
    response3 = brain.generate_response("What do I like?")
    print(f"Response: {response3}")
    
    # Test 3: Conversation flow
    print("\n3. Testing conversation flow:")
    response4 = brain.generate_response("Hello")
    print(f"Response: {response4}")
    
    response5 = brain.generate_response("How are you?")
    print(f"Response: {response5}")
    
    print("\n✅ Context test completed!")

if __name__ == "__main__":
    test_context_system()
