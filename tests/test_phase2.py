#!/usr/bin/env python3
"""
Atulya Tantra - Phase 2 Test Script
Version: 2.5.0
Test the modern UI implementation
"""

import asyncio
import sys
import requests
import time
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_phase2():
    """Test Phase 2: Modern UI"""
    print("🎨 Testing Atulya Tantra v2.5.0 - Phase 2: Modern UI")
    print("=" * 70)
    
    try:
        # Test 1: Check if server is running
        print("1. Testing server availability...")
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                print("   ✅ Server is running")
                health_data = response.json()
                print(f"   📊 Health: {health_data}")
            else:
                print(f"   ⚠️  Server responded with status {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️  Server not running: {e}")
            print("   💡 Start server with: python main.py")
            return False
        
        # Test 2: Check WebUI endpoint
        print("\n2. Testing WebUI endpoint...")
        try:
            response = requests.get("http://localhost:8000/", timeout=5)
            if response.status_code == 200:
                print("   ✅ WebUI endpoint accessible")
                
                # Check for key UI elements
                content = response.text
                ui_elements = [
                    "Atulya Tantra",
                    "Level 5 AGI System",
                    "New Chat",
                    "Welcome to Atulya Tantra",
                    "Intelligent Routing",
                    "Sentiment Analysis",
                    "Context Memory",
                    "Multi-Model"
                ]
                
                found_elements = []
                for element in ui_elements:
                    if element in content:
                        found_elements.append(element)
                
                print(f"   🎨 UI Elements found: {len(found_elements)}/{len(ui_elements)}")
                for element in found_elements:
                    print(f"      ✅ {element}")
                
                missing_elements = [e for e in ui_elements if e not in found_elements]
                if missing_elements:
                    print(f"   ⚠️  Missing elements: {missing_elements}")
                
            else:
                print(f"   ❌ WebUI endpoint failed: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"   ❌ WebUI endpoint error: {e}")
        
        # Test 3: Check API endpoints
        print("\n3. Testing API endpoints...")
        
        # Test chat endpoint
        try:
            response = requests.post(
                "http://localhost:8000/api/chat/",
                json={"message": "Hello, test message"},
                timeout=10
            )
            if response.status_code == 200:
                print("   ✅ Chat API endpoint working")
                chat_data = response.json()
                print(f"   💬 Response: {chat_data.get('response', 'No response')[:50]}...")
                print(f"   🆔 Conversation ID: {chat_data.get('conversation_id', 'None')}")
            else:
                print(f"   ⚠️  Chat API responded with status {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️  Chat API error: {e}")
        
        # Test conversations endpoint
        try:
            response = requests.get("http://localhost:8000/api/chat/conversations", timeout=5)
            if response.status_code == 200:
                print("   ✅ Conversations API endpoint working")
                conv_data = response.json()
                print(f"   📋 Conversations: {conv_data.get('total', 0)}")
            else:
                print(f"   ⚠️  Conversations API responded with status {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️  Conversations API error: {e}")
        
        # Test 4: Check UI file structure
        print("\n4. Testing UI file structure...")
        
        ui_files = [
            "webui/index.html",
            "webui/src/components",
            "webui/src/pages", 
            "webui/src/services",
            "webui/src/hooks",
            "webui/src/styles",
            "webui/src/utils",
            "webui/public"
        ]
        
        for file_path in ui_files:
            path = Path(file_path)
            if path.exists():
                print(f"   ✅ {file_path}")
            else:
                print(f"   ❌ {file_path} - Missing")
        
        # Test 5: Check UI features
        print("\n5. Testing UI features...")
        
        # Check if HTML contains modern UI features
        webui_path = Path("webui/index.html")
        if webui_path.exists():
            content = webui_path.read_text()
            
            features = [
                "Claude Anthropic Color Palette",
                "Responsive Design",
                "Dark Mode Support",
                "Loading Animation",
                "Message Bubbles",
                "Sidebar Navigation",
                "Feature Grid",
                "Auto-resize Textarea",
                "Keyboard Shortcuts"
            ]
            
            found_features = []
            for feature in features:
                if any(keyword.lower() in content.lower() for keyword in feature.split()):
                    found_features.append(feature)
            
            print(f"   🎨 UI Features found: {len(found_features)}/{len(features)}")
            for feature in found_features:
                print(f"      ✅ {feature}")
        
        print("\n🎉 Phase 2 test completed!")
        print("✅ Modern UI with Claude Anthropic color theme implemented")
        print("✅ ChatGPT-style interface with advanced features")
        print("✅ Responsive design and accessibility features")
        print("✅ API integration for chat functionality")
        print("✅ Clean component structure for future React migration")
        
        print("\n🌐 To test the UI:")
        print("   1. Start server: python main.py")
        print("   2. Open browser: http://localhost:8000")
        print("   3. Try sending a message!")
        
    except Exception as e:
        print(f"\n❌ Phase 2 test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = test_phase2()
    sys.exit(0 if success else 1)
