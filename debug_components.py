#!/usr/bin/env python3
"""
Debug script to test individual components
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def debug_components():
    """Debug individual components"""
    print("🔍 Debugging Atulya Tantra Components")
    print("=" * 50)
    
    try:
        # Test 1: Configuration
        print("1. Testing configuration...")
        from src.config.settings import get_settings
        settings = get_settings()
        print(f"   ✅ Config loaded: {settings.app_name} v{settings.app_version}")
        
        # Test 2: Dependencies
        print("\n2. Testing dependencies...")
        from src.api.dependencies import get_chat_service
        chat_service = get_chat_service()
        print(f"   ✅ Chat service created: {type(chat_service).__name__}")
        
        # Test 3: Chat Service Methods
        print("\n3. Testing chat service methods...")
        try:
            stats = await chat_service.get_conversation_stats()
            print(f"   ✅ Conversation stats: {stats}")
        except Exception as e:
            print(f"   ❌ Conversation stats error: {e}")
        
        try:
            health = await chat_service.health_check()
            print(f"   ✅ Health check: {health}")
        except Exception as e:
            print(f"   ❌ Health check error: {e}")
        
        # Test 4: AI Service
        print("\n4. Testing AI service...")
        from src.api.dependencies import get_ai_service
        ai_service = get_ai_service()
        print(f"   ✅ AI service created: {type(ai_service).__name__}")
        
        try:
            ai_health = await ai_service.health_check()
            print(f"   ✅ AI health check: {ai_health}")
        except Exception as e:
            print(f"   ❌ AI health check error: {e}")
        
        # Test 5: Process Message
        print("\n5. Testing message processing...")
        try:
            response = await chat_service.process_message(
                message="Hello, this is a test message",
                conversation_id="test-conversation",
                user_id="test-user",
                model="ollama"
            )
            print(f"   ✅ Message processed: {response.response[:50]}...")
            print(f"   📊 Metadata: {response.metadata}")
        except Exception as e:
            print(f"   ❌ Message processing error: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n🎉 Debug completed!")
        
    except Exception as e:
        print(f"\n❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_components())
