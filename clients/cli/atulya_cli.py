"""
CLI Client for Atulya Tantra Server
Connect to server from command line (cross-platform)
"""

import requests
import sys
import time
from typing import Optional

SERVER_URL = "http://localhost:8000"

class AtulyaCLI:
    """Command-line client for Atulya server"""
    
    def __init__(self, server_url: str = SERVER_URL):
        self.server_url = server_url
        self.conversation_id = f"cli_{int(time.time())}"
        self.conversation_history = []
    
    def check_server(self) -> bool:
        """Check if server is running"""
        try:
            response = requests.get(f"{self.server_url}/", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def send_message(self, message: str, model: str = "phi3:mini") -> Optional[str]:
        """Send message to server and get response"""
        try:
            response = requests.post(
                f"{self.server_url}/api/chat",
                json={
                    "message": message,
                    "model": model,
                    "conversation_id": self.conversation_id
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("response")
            else:
                return f"Error: {response.status_code}"
                
        except requests.exceptions.Timeout:
            return "⚠️  Request timed out"
        except Exception as e:
            return f"⚠️  Error: {e}"
    
    def list_models(self):
        """List available models"""
        try:
            response = requests.get(f"{self.server_url}/api/models", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get("models", [])
            return []
        except:
            return []
    
    def interactive_mode(self):
        """Run interactive chat mode"""
        print("🤖 Atulya Tantra - CLI Client")
        print("=" * 60)
        
        # Check server
        print("Checking server connection...")
        if not self.check_server():
            print("❌ Cannot connect to server!")
            print(f"   Make sure server is running: cd server && python main.py")
            return
        
        print("✅ Connected to server!")
        
        # List models
        models = self.list_models()
        if models:
            print(f"📋 Available models: {', '.join([m['name'] for m in models])}")
        
        print()
        print("💬 Type your messages (or 'quit' to exit)")
        print("   Commands: /model <name>, /models, /status")
        print("=" * 60)
        print()
        
        current_model = "phi3:mini"
        
        while True:
            try:
                # Get user input
                user_input = input("\n💭 You: ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.lower() == 'quit':
                    print("\n👋 Goodbye!")
                    break
                
                if user_input.startswith('/model '):
                    current_model = user_input.split(' ', 1)[1]
                    print(f"✅ Switched to model: {current_model}")
                    continue
                
                if user_input == '/models':
                    models = self.list_models()
                    print("\n📋 Available models:")
                    for m in models:
                        status = "✅ Installed" if m.get('installed') else "❌ Not installed"
                        print(f"  • {m['name']} - {status}")
                    continue
                
                if user_input == '/status':
                    if self.check_server():
                        print("✅ Server online")
                        print(f"📋 Model: {current_model}")
                        print(f"💾 Conversation ID: {self.conversation_id}")
                    else:
                        print("❌ Server offline")
                    continue
                
                # Send to AI
                print("🧠 Atulya: ", end="", flush=True)
                start_time = time.time()
                
                response = self.send_message(user_input, current_model)
                
                elapsed = time.time() - start_time
                
                if response:
                    print(response)
                    print(f"⏱️  Response time: {elapsed:.1f}s")
                    
                    # Store in history
                    self.conversation_history.append({
                        "user": user_input,
                        "assistant": response,
                        "model": current_model
                    })
                else:
                    print("⚠️  No response received")
                
            except KeyboardInterrupt:
                print("\n\n👋 Interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\n⚠️  Error: {e}")

def main():
    """Main entry point"""
    cli = AtulyaCLI()
    cli.interactive_mode()

if __name__ == "__main__":
    main()

