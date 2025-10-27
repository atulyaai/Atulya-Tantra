#!/usr/bin/env python3
"""
Simple Model Test for GitHub Actions
Tests basic AGI system functionality without heavy dependencies
"""

import asyncio
import sys
import os
import json
from datetime import datetime
from typing import Dict, Any

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all core modules can be imported"""
    print("🔍 Testing imports...")
    
    try:
        from Core.config.settings import settings
        print("  ✅ Settings imported")
    except Exception as e:
        print(f"  ❌ Settings import failed: {e}")
        return False
    
    try:
        from Core.config.logging import get_logger
        logger = get_logger(__name__)
        print("  ✅ Logging imported")
    except Exception as e:
        print(f"  ❌ Logging import failed: {e}")
        return False
    
    try:
        from Core.jarvis.sentiment_analyzer import get_sentiment_analyzer
        analyzer = get_sentiment_analyzer()
        print("  ✅ Sentiment analyzer imported")
    except Exception as e:
        print(f"  ❌ Sentiment analyzer import failed: {e}")
        return False
    
    try:
        from Core.agi_core import get_agi_core
        agi_core = get_agi_core()
        print("  ✅ AGI core imported")
    except Exception as e:
        print(f"  ❌ AGI core import failed: {e}")
        return False
    
    try:
        from Core.unified_agi_system import get_agi_system
        agi_system = get_agi_system()
        print("  ✅ Unified AGI system imported")
    except Exception as e:
        print(f"  ❌ Unified AGI system import failed: {e}")
        return False
    
    return True

async def test_basic_functionality():
    """Test basic functionality without heavy dependencies"""
    print("\n🧪 Testing basic functionality...")
    
    try:
        # Test sentiment analysis
        from Core.jarvis.sentiment_analyzer import analyze_user_sentiment
        
        test_text = "I'm feeling happy today!"
        result = await analyze_user_sentiment(test_text, "test_user")
        
        if result and hasattr(result, 'current_emotion'):
            print(f"  ✅ Sentiment analysis: {result.current_emotion}")
        else:
            print("  ⚠️  Sentiment analysis returned unexpected result")
        
    except Exception as e:
        print(f"  ❌ Sentiment analysis test failed: {e}")
        return False
    
    try:
        # Test AGI core
        from Core.agi_core import get_agi_core
        
        agi_core = get_agi_core()
        status = agi_core.get_status()
        
        if status and isinstance(status, dict):
            print(f"  ✅ AGI core status: {len(status)} metrics")
        else:
            print("  ⚠️  AGI core returned unexpected status")
        
    except Exception as e:
        print(f"  ❌ AGI core test failed: {e}")
        return False
    
    try:
        # Test unified system
        from Core.unified_agi_system import get_agi_system
        
        agi_system = get_agi_system()
        system_status = agi_system.get_system_status()
        
        if system_status and isinstance(system_status, dict):
            print(f"  ✅ System status: {system_status.get('status', 'unknown')}")
        else:
            print("  ⚠️  System returned unexpected status")
        
    except Exception as e:
        print(f"  ❌ System test failed: {e}")
        return False
    
    return True

def test_configuration():
    """Test configuration system"""
    print("\n⚙️  Testing configuration...")
    
    try:
        from Core.config.settings import settings
        
        # Test basic settings
        print(f"  ✅ Primary AI Provider: {settings.PRIMARY_AI_PROVIDER}")
        print(f"  ✅ Database Type: {settings.DATABASE_TYPE}")
        print(f"  ✅ Voice Enabled: {settings.VOICE_ENABLED}")
        print(f"  ✅ Streaming Enabled: {settings.STREAMING_ENABLED}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Configuration test failed: {e}")
        return False

def test_database_connection():
    """Test database connection"""
    print("\n🗄️  Testing database connection...")
    
    try:
        from Core.database.database import get_database
        
        db = get_database()
        if db:
            print("  ✅ Database connection established")
            return True
        else:
            print("  ⚠️  Database connection returned None")
            return False
            
    except Exception as e:
        print(f"  ❌ Database test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🚀 Atulya Tantra AGI - Simple Model Test")
    print("=" * 50)
    
    test_results = []
    
    # Test 1: Imports
    test_results.append(test_imports())
    
    # Test 2: Configuration
    test_results.append(test_configuration())
    
    # Test 3: Database
    test_results.append(test_database_connection())
    
    # Test 4: Basic functionality
    test_results.append(await test_basic_functionality())
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    
    test_names = [
        "Imports",
        "Configuration", 
        "Database",
        "Basic Functionality"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, test_results)):
        print(f"  {name}: {'✅' if result else '❌'}")
    
    total_tests = len(test_results)
    passed_tests = sum(test_results)
    
    print(f"\n🎯 Overall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! System is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        sys.exit(1)