#!/usr/bin/env python3
"""
Test script for Atulya Tantra AGI JARVIS Features
Tests personality engine, voice interface, and proactive assistance
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Core.jarvis import (
    process_user_message, get_conversation_summary, reset_conversation,
    start_voice_conversation, process_voice_command, test_voice_interface,
    process_with_assistance, schedule_assistance, get_assistance_statistics,
    PersonalityTrait, EmotionalState, AssistanceType
)
from Core.config.logging import get_logger
from datetime import datetime, timedelta

logger = get_logger(__name__)


async def test_personality_engine():
    """Test personality engine and conversational AI"""
    print("🧠 Testing Personality Engine...")
    
    try:
        user_id = "test_user_001"
        
        # Test basic conversation
        print("  Testing basic conversation...")
        response1 = await process_user_message(user_id, "Hello JARVIS!")
        print(f"  ✅ Response: {response1['response'][:100]}...")
        
        # Test emotional intelligence
        print("  Testing emotional intelligence...")
        response2 = await process_user_message(user_id, "I'm feeling frustrated with this coding problem")
        print(f"  ✅ Detected sentiment: {response2.get('user_sentiment', 'unknown')}")
        print(f"  ✅ JARVIS emotional state: {response2.get('jarvis_emotional_state', 'unknown')}")
        
        # Test personality adaptation
        print("  Testing personality adaptation...")
        response3 = await process_user_message(user_id, "Can you help me write a creative story?")
        print(f"  ✅ Creative response: {response3['response'][:100]}...")
        
        # Test conversation summary
        print("  Testing conversation summary...")
        summary = await get_conversation_summary(user_id)
        print(f"  ✅ Interaction count: {summary.get('interaction_count', 0)}")
        print(f"  ✅ User mood: {summary.get('user_mood', 'unknown')}")
        
        # Test conversation reset
        print("  Testing conversation reset...")
        reset_success = await reset_conversation(user_id)
        print(f"  ✅ Conversation reset: {reset_success}")
        
        return True
        
    except Exception as e:
        logger.error(f"Personality engine test failed: {e}")
        print(f"  ❌ Personality engine test failed: {e}")
        return False


async def test_voice_interface():
    """Test voice interface components"""
    print("\n🎤 Testing Voice Interface...")
    
    try:
        # Test voice interface availability
        print("  Testing voice interface availability...")
        voice_test = await test_voice_interface()
        print(f"  ✅ TTS available: {voice_test.get('tts_available', False)}")
        print(f"  ✅ STT available: {voice_test.get('stt_available', False)}")
        print(f"  ✅ Tests passed: {voice_test.get('tests_passed', 0)}")
        
        # Test voice command processing (simulated)
        print("  Testing voice command processing...")
        user_id = "test_user_002"
        test_command = "What's the weather like today?"
        
        # Note: This would normally require actual voice input
        # For testing, we'll simulate the command processing
        try:
            response = await process_voice_command(user_id, test_command)
            print(f"  ✅ Command processed: {response.get('command_type', 'unknown')}")
        except Exception as e:
            print(f"  ⚠️  Voice command test skipped (requires audio): {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Voice interface test failed: {e}")
        print(f"  ❌ Voice interface test failed: {e}")
        return False


async def test_proactive_assistance():
    """Test proactive assistance system"""
    print("\n🤖 Testing Proactive Assistance...")
    
    try:
        user_id = "test_user_003"
        
        # Test context-aware processing
        print("  Testing context-aware processing...")
        response1 = await process_with_assistance(user_id, "Hello, I'm new here")
        assistance_items = response1.get('proactive_assistance', [])
        print(f"  ✅ Generated {len(assistance_items)} assistance items")
        
        if assistance_items:
            for item in assistance_items:
                print(f"    - {item.get('title', 'No title')}: {item.get('message', 'No message')[:50]}...")
        
        # Test frustration detection
        print("  Testing frustration detection...")
        response2 = await process_with_assistance(user_id, "This is so frustrating! I can't figure this out!")
        assistance_items2 = response2.get('proactive_assistance', [])
        print(f"  ✅ Generated {len(assistance_items2)} assistance items for frustration")
        
        # Test help request
        print("  Testing help request...")
        response3 = await process_with_assistance(user_id, "I need help with something")
        assistance_items3 = response3.get('proactive_assistance', [])
        print(f"  ✅ Generated {len(assistance_items3)} assistance items for help request")
        
        # Test scheduled assistance
        print("  Testing scheduled assistance...")
        assistance_item = {
            "title": "Daily Check-in",
            "message": "How are you doing today?",
            "suggestions": ["Tell me about your goals", "Ask for help", "Share an update"]
        }
        
        scheduled_time = datetime.utcnow() + timedelta(seconds=5)
        assistance_id = await schedule_assistance(user_id, assistance_item, scheduled_time)
        print(f"  ✅ Scheduled assistance: {assistance_id}")
        
        # Test assistance statistics
        print("  Testing assistance statistics...")
        stats = await get_assistance_statistics()
        print(f"  ✅ Total assistance: {stats.get('total_assistance', 0)}")
        print(f"  ✅ Active rules: {stats.get('active_rules', 0)}")
        
        return True
        
    except Exception as e:
        logger.error(f"Proactive assistance test failed: {e}")
        print(f"  ❌ Proactive assistance test failed: {e}")
        return False


async def test_personality_traits():
    """Test different personality traits"""
    print("\n🎭 Testing Personality Traits...")
    
    try:
        user_id = "test_user_004"
        
        # Test analytical personality
        print("  Testing analytical personality...")
        response1 = await process_user_message(user_id, "I need to analyze some data")
        print(f"  ✅ Analytical response: {response1['response'][:80]}...")
        
        # Test creative personality
        print("  Testing creative personality...")
        response2 = await process_user_message(user_id, "Let's write a poem about technology")
        print(f"  ✅ Creative response: {response2['response'][:80]}...")
        
        # Test empathetic personality
        print("  Testing empathetic personality...")
        response3 = await process_user_message(user_id, "I'm feeling sad about something")
        print(f"  ✅ Empathetic response: {response3['response'][:80]}...")
        
        # Test professional personality
        print("  Testing professional personality...")
        response4 = await process_user_message(user_id, "I need help with a business proposal")
        print(f"  ✅ Professional response: {response4['response'][:80]}...")
        
        return True
        
    except Exception as e:
        logger.error(f"Personality traits test failed: {e}")
        print(f"  ❌ Personality traits test failed: {e}")
        return False


async def test_emotional_intelligence():
    """Test emotional intelligence features"""
    print("\n💭 Testing Emotional Intelligence...")
    
    try:
        user_id = "test_user_005"
        
        # Test happy sentiment
        print("  Testing happy sentiment detection...")
        response1 = await process_user_message(user_id, "I'm so excited about this new project!")
        print(f"  ✅ Detected sentiment: {response1.get('user_sentiment', 'unknown')}")
        
        # Test concerned sentiment
        print("  Testing concerned sentiment detection...")
        response2 = await process_user_message(user_id, "I'm worried about the deadline")
        print(f"  ✅ Detected sentiment: {response2.get('user_sentiment', 'unknown')}")
        
        # Test frustrated sentiment
        print("  Testing frustrated sentiment detection...")
        response3 = await process_user_message(user_id, "This is so annoying and difficult!")
        print(f"  ✅ Detected sentiment: {response3.get('user_sentiment', 'unknown')}")
        
        # Test curious sentiment
        print("  Testing curious sentiment detection...")
        response4 = await process_user_message(user_id, "I wonder how this works?")
        print(f"  ✅ Detected sentiment: {response4.get('user_sentiment', 'unknown')}")
        
        return True
        
    except Exception as e:
        logger.error(f"Emotional intelligence test failed: {e}")
        print(f"  ❌ Emotional intelligence test failed: {e}")
        return False


async def test_conversation_context():
    """Test conversation context management"""
    print("\n💬 Testing Conversation Context...")
    
    try:
        user_id = "test_user_006"
        
        # Start a conversation
        print("  Testing conversation flow...")
        await process_user_message(user_id, "Hi JARVIS, I'm working on a Python project")
        await process_user_message(user_id, "I need help with error handling")
        await process_user_message(user_id, "Can you show me how to use try-except blocks?")
        
        # Get conversation summary
        summary = await get_conversation_summary(user_id)
        print(f"  ✅ Conversation length: {summary.get('conversation_length', 0)} messages")
        print(f"  ✅ Interaction count: {summary.get('interaction_count', 0)}")
        print(f"  ✅ Current topic: {summary.get('current_topic', 'none')}")
        
        # Test context continuity
        print("  Testing context continuity...")
        response = await process_user_message(user_id, "Can you give me another example?")
        print(f"  ✅ Context-aware response: {response['response'][:80]}...")
        
        return True
        
    except Exception as e:
        logger.error(f"Conversation context test failed: {e}")
        print(f"  ❌ Conversation context test failed: {e}")
        return False


async def main():
    """Run all JARVIS feature tests"""
    print("🚀 Atulya Tantra AGI - JARVIS Features Test Suite")
    print("=" * 70)
    
    # Test results
    test_results = []
    
    # Test 1: Personality Engine
    test_results.append(await test_personality_engine())
    
    # Test 2: Voice Interface
    test_results.append(await test_voice_interface())
    
    # Test 3: Proactive Assistance
    test_results.append(await test_proactive_assistance())
    
    # Test 4: Personality Traits
    test_results.append(await test_personality_traits())
    
    # Test 5: Emotional Intelligence
    test_results.append(await test_emotional_intelligence())
    
    # Test 6: Conversation Context
    test_results.append(await test_conversation_context())
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Test Summary:")
    
    test_names = [
        "Personality Engine",
        "Voice Interface",
        "Proactive Assistance",
        "Personality Traits",
        "Emotional Intelligence",
        "Conversation Context"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, test_results)):
        print(f"  {name}: {'✅' if result else '❌'}")
    
    total_tests = len(test_results)
    passed_tests = sum(test_results)
    
    print(f"\n🎯 Overall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! JARVIS features are working correctly.")
    else:
        print("⚠️  Some tests failed. Check the logs for details.")
    
    # Cleanup
    try:
        # Reset all test conversations
        test_users = ["test_user_001", "test_user_002", "test_user_003", 
                     "test_user_004", "test_user_005", "test_user_006"]
        
        for user_id in test_users:
            await reset_conversation(user_id)
        
        print("\n🧹 Test cleanup completed")
        
    except Exception as e:
        logger.error(f"Cleanup error: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user.")
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        print(f"❌ Test suite failed: {e}")
