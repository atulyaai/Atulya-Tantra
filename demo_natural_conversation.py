#!/usr/bin/env python3
"""
Natural Conversation Demo
Demonstrates human-like conversations without hardcoded responses
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from Core.conversation.natural_conversation import get_natural_conversation_engine, chat_with_ai


class ConversationDemo:
    """Interactive conversation demo"""
    
    def __init__(self):
        self.engine = get_natural_conversation_engine()
        self.user_id = "demo_user"
        self.session_id = f"session_{int(asyncio.get_event_loop().time())}"
    
    async def run_demo(self):
        """Run the conversation demo"""
        print("🤖 Natural Conversation Demo")
        print("=" * 50)
        print("This AI can have natural, human-like conversations without hardcoded responses!")
        print("Type 'quit' to exit, 'insights' for conversation insights, 'stats' for statistics")
        print("=" * 50)
        
        while True:
            try:
                # Get user input
                user_input = input("\n👤 You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    print("\n🤖 AI: Goodbye! It was great talking with you! 👋")
                    break
                
                if user_input.lower() == 'insights':
                    await self._show_insights()
                    continue
                
                if user_input.lower() == 'stats':
                    await self._show_statistics()
                    continue
                
                if not user_input:
                    continue
                
                # Get AI response
                print("🤖 AI: ", end="", flush=True)
                response = await self.engine.process_message(
                    user_id=self.user_id,
                    message=user_input,
                    session_id=self.session_id
                )
                print(response)
                
            except KeyboardInterrupt:
                print("\n\n🤖 AI: Goodbye! Thanks for chatting! 👋")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
    
    async def _show_insights(self):
        """Show conversation insights"""
        insights = await self.engine.get_conversation_insights(self.user_id)
        
        print("\n📊 Conversation Insights:")
        print("-" * 30)
        print(f"Total conversations: {insights.get('total_conversations', 0)}")
        print(f"Most common context: {insights.get('most_common_context', 'N/A')}")
        print(f"Most common emotional tone: {insights.get('most_common_emotional_tone', 'N/A')}")
        
        top_topics = insights.get('top_topics', [])
        if top_topics:
            print("Top topics discussed:")
            for topic, count in top_topics:
                print(f"  - {topic}: {count} times")
        
        frequency = insights.get('conversation_frequency', 0)
        print(f"Conversation frequency: {frequency:.2f} per day")
    
    async def _show_statistics(self):
        """Show conversation statistics"""
        stats = self.engine.get_conversation_statistics()
        
        print("\n📈 System Statistics:")
        print("-" * 30)
        print(f"Total users: {stats.get('total_users', 0)}")
        print(f"Total conversations: {stats.get('total_conversations', 0)}")
        print(f"Active sessions: {stats.get('active_sessions', 0)}")
        print(f"Average conversations per user: {stats.get('average_conversations_per_user', 0):.2f}")


async def demo_conversation_examples():
    """Demo various conversation examples"""
    print("🎭 Conversation Examples")
    print("=" * 50)
    
    examples = [
        "Hello! How are you today?",
        "I'm feeling a bit frustrated with my work. Can you help?",
        "What's the weather like?",
        "Can you help me write a poem about the ocean?",
        "I'm excited about my new project!",
        "I don't understand how this works.",
        "Tell me a joke!",
        "I'm sad because my pet is sick.",
        "What can you do to help me?",
        "I need help with coding a Python function."
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n--- Example {i} ---")
        print(f"👤 User: {example}")
        
        response = await chat_with_ai(example, f"demo_user_{i}")
        print(f"🤖 AI: {response}")
        
        # Small delay between examples
        await asyncio.sleep(1)


async def main():
    """Main function"""
    print("Choose demo mode:")
    print("1. Interactive conversation")
    print("2. Conversation examples")
    print("3. Both")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        demo = ConversationDemo()
        await demo.run_demo()
    elif choice == "2":
        await demo_conversation_examples()
    elif choice == "3":
        await demo_conversation_examples()
        print("\n" + "=" * 50)
        demo = ConversationDemo()
        await demo.run_demo()
    else:
        print("Invalid choice. Running interactive demo...")
        demo = ConversationDemo()
        await demo.run_demo()


if __name__ == "__main__":
    asyncio.run(main())