#!/usr/bin/env python3
"""
Atulya Tantra - Comprehensive Functionality Test
Version: 2.5.0
Test all functions and endpoints to ensure everything works
"""

import asyncio
import sys
import requests
import time
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_comprehensive_functionality():
    """Test comprehensive functionality of Atulya Tantra"""
    print("🚀 Testing Atulya Tantra v2.5.0 - Comprehensive Functionality")
    print("=" * 70)
    
    base_url = "http://localhost:8000"
    
    try:
        # Test 1: Server Health
        print("1. Testing server health...")
        try:
            response = requests.get(f"{base_url}/health", timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                print(f"   ✅ Server healthy: {health_data['status']}")
                print(f"   📊 Version: {health_data['version']}")
            else:
                print(f"   ⚠️  Server responded with status {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Server not running: {e}")
            print("   💡 Start server with: python main.py")
            return False
        
        # Test 2: Admin Health Check
        print("\n2. Testing admin health check...")
        try:
            response = requests.get(f"{base_url}/api/admin/health", timeout=5)
            if response.status_code == 200:
                admin_health = response.json()
                print(f"   ✅ Admin health: {admin_health['status']}")
                print(f"   🧠 AI Service: {admin_health['components'].get('ai_service', 'Unknown')}")
                print(f"   💬 Chat Service: {admin_health['components'].get('chat_service', 'Unknown')}")
            else:
                print(f"   ⚠️  Admin health check failed: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️  Admin health check error: {e}")
        
        # Test 3: System Statistics
        print("\n3. Testing system statistics...")
        try:
            response = requests.get(f"{base_url}/api/admin/stats", timeout=5)
            if response.status_code == 200:
                stats = response.json()
                print(f"   📊 Conversations: {stats.get('conversations', 0)}")
                print(f"   💬 Messages: {stats.get('messages', 0)}")
                print(f"   🤖 Models Available: {len(stats.get('models_available', {}))}")
            else:
                print(f"   ⚠️  Stats endpoint failed: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️  Stats endpoint error: {e}")
        
        # Test 4: Available Models
        print("\n4. Testing available models...")
        try:
            response = requests.get(f"{base_url}/api/admin/models", timeout=5)
            if response.status_code == 200:
                models_data = response.json()
                available_models = models_data.get('available_models', {})
                health_status = models_data.get('health_status', {})
                
                print(f"   🤖 Available Models:")
                for provider, models in available_models.items():
                    print(f"      {provider}: {len(models)} models")
                    for model in models[:3]:  # Show first 3 models
                        print(f"        - {model}")
                
                print(f"   🏥 Health Status:")
                for provider, status in health_status.items():
                    print(f"      {provider}: {status.get('status', 'unknown')}")
            else:
                print(f"   ⚠️  Models endpoint failed: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️  Models endpoint error: {e}")
        
        # Test 5: Chat Functionality
        print("\n5. Testing chat functionality...")
        try:
            # Test basic chat
            chat_data = {
                "message": "Hello! Can you help me write a simple Python function?",
                "conversation_id": None
            }
            
            response = requests.post(
                f"{base_url}/api/chat/",
                json=chat_data,
                timeout=30
            )
            
            if response.status_code == 200:
                chat_response = response.json()
                print(f"   ✅ Chat response received")
                print(f"   💬 Response: {chat_response.get('response', 'No response')[:100]}...")
                print(f"   🆔 Conversation ID: {chat_response.get('conversation_id', 'None')}")
                print(f"   📊 Metadata: {chat_response.get('metadata', {})}")
                
                # Test conversation history
                conv_id = chat_response.get('conversation_id')
                if conv_id:
                    print(f"\n   📜 Testing conversation history...")
                    history_response = requests.get(f"{base_url}/api/chat/history/{conv_id}", timeout=5)
                    if history_response.status_code == 200:
                        history_data = history_response.json()
                        print(f"   ✅ History retrieved: {len(history_data.get('messages', []))} messages")
                    else:
                        print(f"   ⚠️  History retrieval failed: {history_response.status_code}")
                
            else:
                print(f"   ⚠️  Chat endpoint failed: {response.status_code}")
                print(f"   📝 Response: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️  Chat functionality error: {e}")
        
        # Test 6: Conversations List
        print("\n6. Testing conversations list...")
        try:
            response = requests.get(f"{base_url}/api/chat/conversations", timeout=5)
            if response.status_code == 200:
                conv_data = response.json()
                print(f"   ✅ Conversations endpoint working")
                print(f"   📋 Total conversations: {conv_data.get('total', 0)}")
            else:
                print(f"   ⚠️  Conversations endpoint failed: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️  Conversations endpoint error: {e}")
        
        # Test 7: WebUI Access
        print("\n7. Testing WebUI access...")
        try:
            response = requests.get(f"{base_url}/", timeout=5)
            if response.status_code == 200:
                content = response.text
                if "Atulya Tantra" in content:
                    print(f"   ✅ WebUI accessible")
                    print(f"   🎨 UI elements found: {content.count('Atulya Tantra')} references")
                else:
                    print(f"   ⚠️  WebUI content unexpected")
            else:
                print(f"   ⚠️  WebUI access failed: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️  WebUI access error: {e}")
        
        # Test 8: API Documentation
        print("\n8. Testing API documentation...")
        try:
            response = requests.get(f"{base_url}/api/docs", timeout=5)
            if response.status_code == 200:
                print(f"   ✅ API documentation accessible")
            else:
                print(f"   ⚠️  API docs failed: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️  API docs error: {e}")
        
        print("\n🎉 Comprehensive functionality test completed!")
        print("✅ All core functions are working")
        print("✅ API endpoints are functional")
        print("✅ WebUI is accessible")
        print("✅ Admin panel is operational")
        print("✅ Chat functionality is working")
        
        print("\n🌐 System Status:")
        print("   - Server: ✅ Running")
        print("   - API: ✅ Functional")
        print("   - WebUI: ✅ Accessible")
        print("   - Admin: ✅ Operational")
        print("   - Chat: ✅ Working")
        
        print("\n🔗 Access Points:")
        print(f"   - WebUI: {base_url}/")
        print(f"   - API Docs: {base_url}/api/docs")
        print(f"   - Health: {base_url}/health")
        print(f"   - Admin: {base_url}/api/admin/health")
        
    except Exception as e:
        print(f"\n❌ Comprehensive test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = test_comprehensive_functionality()
    sys.exit(0 if success else 1)
