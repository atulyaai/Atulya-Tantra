#!/usr/bin/env python3
"""
Simple test script to verify the AGI system components work
"""

import sys
import os
import asyncio

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_sentiment_analysis():
    """Test sentiment analysis"""
    print("Testing sentiment analysis...")
    try:
        from Core.jarvis.sentiment_analyzer import get_sentiment_analyzer, analyze_user_sentiment
        
        analyzer = get_sentiment_analyzer()
        print(f"✅ Sentiment analyzer created: {type(analyzer).__name__}")
        
        # Test emotion detection
        test_text = "I'm so happy and excited about this!"
        context = await analyze_user_sentiment(test_text, "test_user")
        print(f"✅ Emotion detected: {context.current_emotion} ({context.intensity})")
        
        return True
    except Exception as e:
        print(f"❌ Sentiment analysis test failed: {e}")
        return False

async def test_voice_interface():
    """Test voice interface"""
    print("Testing voice interface...")
    try:
        from Core.jarvis.enhanced_voice_interface import get_enhanced_voice_interface
        
        interface = get_enhanced_voice_interface()
        print(f"✅ Voice interface created: {type(interface).__name__}")
        
        # Test state
        state = interface.get_current_state()
        print(f"✅ Voice state: {state['state']}")
        
        return True
    except Exception as e:
        print(f"❌ Voice interface test failed: {e}")
        return False

async def test_agi_core():
    """Test AGI core"""
    print("Testing AGI core...")
    try:
        from Core.agi_core import get_agi_core, process_agi_request
        
        agi_core = get_agi_core()
        print(f"✅ AGI core created: {type(agi_core).__name__}")
        
        # Test simple request
        result = await process_agi_request("Hello, how are you?", "test_user")
        print(f"✅ AGI request processed: {result['success']}")
        
        return True
    except Exception as e:
        print(f"❌ AGI core test failed: {e}")
        return False

async def test_unified_system():
    """Test unified AGI system"""
    print("Testing unified AGI system...")
    try:
        from Core.unified_agi_system import get_agi_system, process_with_agi
        
        system = get_agi_system()
        print(f"✅ Unified AGI system created: {type(system).__name__}")
        
        # Test system status
        status = system.get_system_status()
        print(f"✅ System status retrieved: {status['is_initialized']}")
        
        return True
    except Exception as e:
        print(f"❌ Unified system test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🤖 Testing JARVIS-Skynet AGI System Components")
    print("=" * 50)
    
    tests = [
        test_sentiment_analysis,
        test_voice_interface,
        test_agi_core,
        test_unified_system
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            result = await test()
            if result:
                passed += 1
            print()
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            print()
    
    print("=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The AGI system is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
