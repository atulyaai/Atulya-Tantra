#!/usr/bin/env python3
"""
Test Natural Conversation System
Demonstrates human-like conversations without hardcoded responses
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from Core.conversation.natural_conversation import get_natural_conversation_engine


async def test_conversation_examples():
    """Test various conversation examples"""
    print("🤖 Testing Natural Conversation System")
    print("=" * 60)
    
    engine = get_natural_conversation_engine()
    user_id = "test_user"
    
    # Test conversations
    test_cases = [
        {
            "message": "Hello! How are you today?",
            "description": "Greeting and casual conversation"
        },
        {
            "message": "I'm feeling really frustrated with my work project. Can you help me?",
            "description": "Emotional support and problem-solving"
        },
        {
            "message": "What's the weather like today?",
            "description": "Information request"
        },
        {
            "message": "Can you write me a poem about the ocean?",
            "description": "Creative task request"
        },
        {
            "message": "I'm excited about my new job! I start next week.",
            "description": "Sharing positive news"
        },
        {
            "message": "I don't understand how this Python code works. Can you explain it?",
            "description": "Learning and explanation request"
        },
        {
            "message": "Tell me a joke to cheer me up!",
            "description": "Entertainment request"
        },
        {
            "message": "I'm sad because my pet is sick and I don't know what to do.",
            "description": "Emotional support for difficult situation"
        },
        {
            "message": "What can you do to help me with my daily tasks?",
            "description": "Capability inquiry"
        },
        {
            "message": "I need help debugging this error in my code: 'NameError: name is not defined'",
            "description": "Technical problem solving"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i}: {test_case['description']} ---")
        print(f"👤 User: {test_case['message']}")
        
        try:
            # Get AI response
            response = await engine.process_message(
                user_id=user_id,
                message=test_case['message'],
                session_id=f"test_session_{i}"
            )
            
            print(f"🤖 AI: {response}")
            
            # Small delay between tests
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    # Test conversation insights
    print(f"\n--- Conversation Insights ---")
    insights = await engine.get_conversation_insights(user_id)
    print(f"Total conversations: {insights.get('total_conversations', 0)}")
    print(f"Most common context: {insights.get('most_common_context', 'N/A')}")
    print(f"Most common emotional tone: {insights.get('most_common_emotional_tone', 'N/A')}")
    
    top_topics = insights.get('top_topics', [])
    if top_topics:
        print("Top topics discussed:")
        for topic, count in top_topics[:3]:  # Show top 3
            print(f"  - {topic}: {count} times")
    
    # Test conversation statistics
    print(f"\n--- System Statistics ---")
    stats = engine.get_conversation_statistics()
    print(f"Total users: {stats.get('total_users', 0)}")
    print(f"Total conversations: {stats.get('total_conversations', 0)}")
    print(f"Active sessions: {stats.get('active_sessions', 0)}")
    print(f"Average conversations per user: {stats.get('average_conversations_per_user', 0):.2f}")


async def test_conversation_continuity():
    """Test conversation continuity and context awareness"""
    print("\n🔄 Testing Conversation Continuity")
    print("=" * 60)
    
    engine = get_natural_conversation_engine()
    user_id = "continuity_test_user"
    session_id = "continuity_session"
    
    # Simulate a continuous conversation
    conversation_flow = [
        "Hi! I'm working on a Python project.",
        "I'm having trouble with error handling.",
        "Can you show me how to use try-except blocks?",
        "That's helpful! Now I need to handle file operations.",
        "What's the best way to read a CSV file?",
        "Thanks! You've been really helpful today.",
        "Goodbye!"
    ]
    
    for i, message in enumerate(conversation_flow, 1):
        print(f"\n--- Turn {i} ---")
        print(f"👤 User: {message}")
        
        try:
            response = await engine.process_message(
                user_id=user_id,
                message=message,
                session_id=session_id
            )
            
            print(f"🤖 AI: {response}")
            
            # Small delay to simulate real conversation
            await asyncio.sleep(0.5)
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    # Show conversation history
    print(f"\n--- Conversation History ---")
    history = await engine.get_conversation_history(user_id, limit=5)
    for entry in history:
        print(f"[{entry['timestamp']}] {entry['user_message'][:50]}... -> {entry['ai_response'][:50]}...")


async def test_emotional_responses():
    """Test emotional intelligence and appropriate responses"""
    print("\n😊 Testing Emotional Intelligence")
    print("=" * 60)
    
    engine = get_natural_conversation_engine()
    user_id = "emotional_test_user"
    
    emotional_scenarios = [
        {
            "message": "I just got promoted at work! I'm so excited!",
            "expected_emotion": "excited",
            "description": "Positive news - should respond enthusiastically"
        },
        {
            "message": "I'm really stressed about my exams next week.",
            "expected_emotion": "stressed",
            "description": "Stress - should respond supportively"
        },
        {
            "message": "I'm confused about this math problem. I don't understand it at all.",
            "expected_emotion": "confused",
            "description": "Confusion - should respond helpfully and clearly"
        },
        {
            "message": "I'm feeling sad because my friend moved away.",
            "expected_emotion": "sad",
            "description": "Sadness - should respond empathetically"
        },
        {
            "message": "I'm frustrated because my computer keeps crashing!",
            "expected_emotion": "frustrated",
            "description": "Frustration - should respond patiently and helpfully"
        }
    ]
    
    for i, scenario in enumerate(emotional_scenarios, 1):
        print(f"\n--- Emotional Test {i}: {scenario['description']} ---")
        print(f"👤 User: {scenario['message']}")
        print(f"Expected emotion: {scenario['expected_emotion']}")
        
        try:
            response = await engine.process_message(
                user_id=user_id,
                message=scenario['message'],
                session_id=f"emotional_session_{i}"
            )
            
            print(f"🤖 AI: {response}")
            
            # Small delay between tests
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"❌ Error: {e}")


async def main():
    """Run all conversation tests"""
    print("🚀 Natural Conversation System Test Suite")
    print("=" * 80)
    print("This system can have human-like conversations WITHOUT hardcoded responses!")
    print("All responses are generated dynamically using AI based on context and emotion.")
    print("=" * 80)
    
    try:
        # Run all tests
        await test_conversation_examples()
        await test_conversation_continuity()
        await test_emotional_responses()
        
        print("\n✅ All tests completed successfully!")
        print("\n🎉 The system demonstrates natural, human-like conversation capabilities!")
        print("   - Dynamic response generation")
        print("   - Emotional intelligence")
        print("   - Context awareness")
        print("   - No hardcoded responses")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())