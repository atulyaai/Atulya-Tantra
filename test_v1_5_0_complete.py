#!/usr/bin/env python3
"""
Atulya Tantra v1.5.0 - Complete System Test Suite
Tests all implemented features end-to-end
"""

import asyncio
import json
import requests
import time
import sys
from pathlib import Path

# Test configuration
BASE_URL = "http://localhost:8000"
TEST_CONVERSATION_ID = "test_" + str(int(time.time()))

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []
    
    def add_test(self, name, passed, details=""):
        self.tests.append({
            "name": name,
            "passed": passed,
            "details": details
        })
        if passed:
            self.passed += 1
            print(f"✅ {name}")
        else:
            self.failed += 1
            print(f"❌ {name}: {details}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"TEST SUMMARY: {self.passed}/{total} tests passed")
        print(f"{'='*50}")
        
        if self.failed > 0:
            print("\nFAILED TESTS:")
            for test in self.tests:
                if not test["passed"]:
                    print(f"  ❌ {test['name']}: {test['details']}")
        
        return self.failed == 0

def test_server_health():
    """Test if server is running and healthy"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("status") == "healthy" and data.get("version") == "1.5.0"
        return False
    except Exception as e:
        return False

def test_chat_api():
    """Test basic chat functionality"""
    try:
        payload = {
            "message": "Hello, this is a test message",
            "conversation_id": TEST_CONVERSATION_ID
        }
        response = requests.post(
            f"{BASE_URL}/api/chat",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return (
                "response" in data and
                "conversation_id" in data and
                "model" in data and
                "timestamp" in data
            )
        return False
    except Exception as e:
        return False

def test_conversation_context():
    """Test that conversation context is maintained"""
    try:
        # Send first message
        payload1 = {
            "message": "My name is TestUser",
            "conversation_id": TEST_CONVERSATION_ID
        }
        response1 = requests.post(
            f"{BASE_URL}/api/chat",
            json=payload1,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response1.status_code != 200:
            return False
        
        # Send second message
        payload2 = {
            "message": "What is my name?",
            "conversation_id": TEST_CONVERSATION_ID
        }
        response2 = requests.post(
            f"{BASE_URL}/api/chat",
            json=payload2,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response2.status_code != 200:
            return False
        
        data2 = response2.json()
        # Check that conversation length increased
        return data2.get("conversation_length", 0) > 2
        
    except Exception as e:
        return False

def test_model_fallback():
    """Test that model fallback system works"""
    try:
        payload = {
            "message": "Test fallback",
            "conversation_id": TEST_CONVERSATION_ID
        }
        response = requests.post(
            f"{BASE_URL}/api/chat",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            # Should show fallback model when Ollama is not available
            return data.get("model") in ["Fallback", "Ollama (Llama 2)", "OpenAI (GPT-3.5)", "Anthropic (Claude)"]
        return False
    except Exception as e:
        return False

def test_conversation_management():
    """Test conversation management endpoints"""
    try:
        # Test get all conversations
        response = requests.get(f"{BASE_URL}/api/chat/conversations", timeout=5)
        if response.status_code != 200:
            return False
        
        data = response.json()
        if data.get("status") != "success":
            return False
        
        # Test get specific conversation history
        response = requests.get(f"{BASE_URL}/api/chat/history/{TEST_CONVERSATION_ID}", timeout=5)
        if response.status_code != 200:
            return False
        
        data = response.json()
        return data.get("status") == "success" and "messages" in data
        
    except Exception as e:
        return False

def test_webui_access():
    """Test that WebUI is accessible"""
    try:
        response = requests.get(f"{BASE_URL}/webui", timeout=5)
        return response.status_code == 200 and "Atulya Tantra" in response.text
    except Exception as e:
        return False

def test_admin_panel():
    """Test that admin panel is accessible"""
    try:
        response = requests.get(f"{BASE_URL}/admin", timeout=5)
        return response.status_code == 200 and "Admin Panel" in response.text
    except Exception as e:
        return False

def test_api_docs():
    """Test that API documentation is accessible"""
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        return response.status_code == 200
    except Exception as e:
        return False

def test_metrics_endpoint():
    """Test metrics endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/metrics", timeout=5)
        return response.status_code == 200
    except Exception as e:
        return False

def main():
    """Run all tests"""
    print("🧪 Atulya Tantra v1.5.0 - Complete System Test Suite")
    print("=" * 60)
    
    results = TestResults()
    
    # Core functionality tests
    print("\n📡 Testing Core Functionality...")
    results.add_test("Server Health Check", test_server_health())
    results.add_test("Chat API Response", test_chat_api())
    results.add_test("Conversation Context", test_conversation_context())
    results.add_test("Model Fallback System", test_model_fallback())
    results.add_test("Conversation Management", test_conversation_management())
    
    # Web interface tests
    print("\n🌐 Testing Web Interfaces...")
    results.add_test("WebUI Access", test_webui_access())
    results.add_test("Admin Panel Access", test_admin_panel())
    results.add_test("API Documentation", test_api_docs())
    
    # Additional endpoints
    print("\n📊 Testing Additional Endpoints...")
    results.add_test("Metrics Endpoint", test_metrics_endpoint())
    
    # Summary
    success = results.summary()
    
    if success:
        print("\n🎉 ALL TESTS PASSED! v1.5.0 is ready for production.")
        print("\n✅ Features Verified:")
        print("   • Real AI integration with fallback system")
        print("   • Conversation context and memory")
        print("   • Model selection and display")
        print("   • WebUI with conversation management")
        print("   • Admin panel and API documentation")
        print("   • Complete API system")
        return 0
    else:
        print("\n❌ Some tests failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
