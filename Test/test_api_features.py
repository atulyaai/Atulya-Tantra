#!/usr/bin/env python3
"""
Test script for Atulya Tantra AGI Web API
Tests FastAPI backend, JWT authentication, and real-time streaming
"""

import asyncio
import sys
import os
import json
import httpx
import websockets
from typing import Dict, Any

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Core.api import (
    UserCreate, UserLogin, ChatMessage, TaskRequest,
    stream_chat_response, stream_task_updates, send_notification,
    get_real_time_stats
)
from Core.config.logging import get_logger

logger = get_logger(__name__)

# Test configuration
API_BASE_URL = "http://localhost:8000"
WS_BASE_URL = "ws://localhost:8000"

class APITester:
    """API testing client"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.access_token = None
        self.user_id = None
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def test_root_endpoint(self) -> bool:
        """Test root endpoint"""
        print("🌐 Testing Root Endpoint...")
        
        try:
            response = await self.client.get(f"{API_BASE_URL}/")
            data = response.json()
            
            print(f"  ✅ Status: {response.status_code}")
            print(f"  ✅ Message: {data.get('message', 'No message')}")
            print(f"  ✅ Version: {data.get('version', 'No version')}")
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Root endpoint test failed: {e}")
            print(f"  ❌ Root endpoint test failed: {e}")
            return False
    
    async def test_health_endpoint(self) -> bool:
        """Test health endpoint"""
        print("\n🏥 Testing Health Endpoint...")
        
        try:
            response = await self.client.get(f"{API_BASE_URL}/health")
            data = response.json()
            
            print(f"  ✅ Status: {response.status_code}")
            print(f"  ✅ Health Status: {data.get('status', 'unknown')}")
            
            system_health = data.get('system_health', {})
            print(f"  ✅ System Health: {system_health.get('overall_status', 'unknown')}")
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Health endpoint test failed: {e}")
            print(f"  ❌ Health endpoint test failed: {e}")
            return False
    
    async def test_user_registration(self) -> bool:
        """Test user registration"""
        print("\n👤 Testing User Registration...")
        
        try:
            user_data = UserCreate(
                username=f"testuser_{int(asyncio.get_event_loop().time())}",
                email=f"test_{int(asyncio.get_event_loop().time())}@example.com",
                password="testpassword123",
                full_name="Test User"
            )
            
            response = await self.client.post(
                f"{API_BASE_URL}/api/auth/register",
                json=user_data.dict()
            )
            
            if response.status_code == 200:
                data = response.json()
                self.user_id = data.get('user_id')
                print(f"  ✅ User registered successfully")
                print(f"  ✅ User ID: {self.user_id}")
                return True
            else:
                print(f"  ❌ Registration failed: {response.status_code}")
                print(f"  ❌ Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"User registration test failed: {e}")
            print(f"  ❌ User registration test failed: {e}")
            return False
    
    async def test_user_login(self) -> bool:
        """Test user login"""
        print("\n🔐 Testing User Login...")
        
        try:
            login_data = UserLogin(
                username="testuser",
                password="testpassword123"
            )
            
            response = await self.client.post(
                f"{API_BASE_URL}/api/auth/login",
                json=login_data.dict()
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get('access_token')
                print(f"  ✅ Login successful")
                print(f"  ✅ Token type: {data.get('token_type', 'unknown')}")
                print(f"  ✅ Expires in: {data.get('expires_in', 'unknown')} seconds")
                return True
            else:
                print(f"  ❌ Login failed: {response.status_code}")
                print(f"  ❌ Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"User login test failed: {e}")
            print(f"  ❌ User login test failed: {e}")
            return False
    
    async def test_authenticated_endpoint(self) -> bool:
        """Test authenticated endpoint"""
        print("\n🔒 Testing Authenticated Endpoint...")
        
        if not self.access_token:
            print("  ⚠️  No access token available, skipping test")
            return False
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            response = await self.client.get(
                f"{API_BASE_URL}/api/auth/me",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ Authenticated request successful")
                print(f"  ✅ Username: {data.get('username', 'unknown')}")
                print(f"  ✅ Email: {data.get('email', 'unknown')}")
                return True
            else:
                print(f"  ❌ Authenticated request failed: {response.status_code}")
                print(f"  ❌ Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Authenticated endpoint test failed: {e}")
            print(f"  ❌ Authenticated endpoint test failed: {e}")
            return False
    
    async def test_chat_endpoint(self) -> bool:
        """Test chat endpoint"""
        print("\n💬 Testing Chat Endpoint...")
        
        if not self.access_token:
            print("  ⚠️  No access token available, skipping test")
            return False
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            chat_data = ChatMessage(
                message="Hello JARVIS! How are you today?",
                conversation_id="test_conversation_001"
            )
            
            response = await self.client.post(
                f"{API_BASE_URL}/api/chat/send",
                json=chat_data.dict(),
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ Chat request successful")
                print(f"  ✅ Response: {data.get('response', 'No response')[:100]}...")
                print(f"  ✅ User Sentiment: {data.get('user_sentiment', 'unknown')}")
                print(f"  ✅ JARVIS Emotional State: {data.get('jarvis_emotional_state', 'unknown')}")
                return True
            else:
                print(f"  ❌ Chat request failed: {response.status_code}")
                print(f"  ❌ Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Chat endpoint test failed: {e}")
            print(f"  ❌ Chat endpoint test failed: {e}")
            return False
    
    async def test_task_endpoint(self) -> bool:
        """Test task submission endpoint"""
        print("\n🤖 Testing Task Endpoint...")
        
        if not self.access_token:
            print("  ⚠️  No access token available, skipping test")
            return False
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            task_data = TaskRequest(
                agent_type="CodeAgent",
                task_type="code_generation",
                description="Write a simple Python function to calculate fibonacci numbers",
                priority="normal",
                timeout_seconds=60
            )
            
            response = await self.client.post(
                f"{API_BASE_URL}/api/agents/task",
                json=task_data.dict(),
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ Task submission successful")
                print(f"  ✅ Task ID: {data.get('task_id', 'unknown')}")
                print(f"  ✅ Status: {data.get('status', 'unknown')}")
                return True
            else:
                print(f"  ❌ Task submission failed: {response.status_code}")
                print(f"  ❌ Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Task endpoint test failed: {e}")
            print(f"  ❌ Task endpoint test failed: {e}")
            return False
    
    async def test_system_endpoints(self) -> bool:
        """Test system monitoring endpoints"""
        print("\n📊 Testing System Endpoints...")
        
        if not self.access_token:
            print("  ⚠️  No access token available, skipping test")
            return False
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            # Test system health
            response = await self.client.get(
                f"{API_BASE_URL}/api/system/health",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ System health retrieved")
                print(f"  ✅ Overall Status: {data.get('overall_status', 'unknown')}")
                
                checks = data.get('checks', {})
                print(f"  ✅ Health Checks: {len(checks)} checks")
                
                alerts = data.get('alerts', {})
                print(f"  ✅ Alerts: {alerts.get('total', 0)} total, {alerts.get('unresolved', 0)} unresolved")
                
                return True
            else:
                print(f"  ❌ System health request failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"System endpoints test failed: {e}")
            print(f"  ❌ System endpoints test failed: {e}")
            return False


class WebSocketTester:
    """WebSocket testing client"""
    
    async def test_websocket_connection(self) -> bool:
        """Test WebSocket connection"""
        print("\n🔌 Testing WebSocket Connection...")
        
        try:
            connection_id = f"test_connection_{int(asyncio.get_event_loop().time())}"
            uri = f"{WS_BASE_URL}/ws/{connection_id}"
            
            async with websockets.connect(uri) as websocket:
                print(f"  ✅ WebSocket connected: {connection_id}")
                
                # Send ping message
                ping_message = {
                    "type": "ping",
                    "timestamp": asyncio.get_event_loop().time()
                }
                
                await websocket.send(json.dumps(ping_message))
                print(f"  ✅ Ping message sent")
                
                # Wait for pong response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(response)
                    
                    if data.get("type") == "pong":
                        print(f"  ✅ Pong response received")
                        return True
                    else:
                        print(f"  ❌ Unexpected response type: {data.get('type')}")
                        return False
                        
                except asyncio.TimeoutError:
                    print(f"  ❌ No response received within timeout")
                    return False
                
        except Exception as e:
            logger.error(f"WebSocket test failed: {e}")
            print(f"  ❌ WebSocket test failed: {e}")
            return False
    
    async def test_chat_websocket(self) -> bool:
        """Test chat over WebSocket"""
        print("\n💬 Testing Chat WebSocket...")
        
        try:
            connection_id = f"chat_test_{int(asyncio.get_event_loop().time())}"
            uri = f"{WS_BASE_URL}/ws/{connection_id}"
            
            async with websockets.connect(uri) as websocket:
                print(f"  ✅ Chat WebSocket connected: {connection_id}")
                
                # Send chat message
                chat_message = {
                    "type": "chat",
                    "user_id": "test_user_001",
                    "message": "Hello JARVIS! This is a WebSocket test."
                }
                
                await websocket.send(json.dumps(chat_message))
                print(f"  ✅ Chat message sent")
                
                # Wait for response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    data = json.loads(response)
                    
                    if data.get("type") == "chat_response":
                        print(f"  ✅ Chat response received")
                        print(f"  ✅ Response: {data.get('response', 'No response')[:100]}...")
                        return True
                    else:
                        print(f"  ❌ Unexpected response type: {data.get('type')}")
                        return False
                        
                except asyncio.TimeoutError:
                    print(f"  ❌ No chat response received within timeout")
                    return False
                
        except Exception as e:
            logger.error(f"Chat WebSocket test failed: {e}")
            print(f"  ❌ Chat WebSocket test failed: {e}")
            return False


async def test_streaming_functions():
    """Test streaming functions directly"""
    print("\n🌊 Testing Streaming Functions...")
    
    try:
        # Test chat streaming
        print("  Testing chat streaming...")
        user_id = "test_user_streaming"
        message = "Hello JARVIS! This is a streaming test."
        
        event_count = 0
        async for event in stream_chat_response(user_id, message):
            event_count += 1
            print(f"    Event {event_count}: {event.event_type}")
            
            if event_count >= 3:  # Limit to first 3 events
                break
        
        print(f"  ✅ Chat streaming test completed: {event_count} events")
        
        # Test real-time stats
        print("  Testing real-time stats...")
        stats = await get_real_time_stats()
        print(f"  ✅ Real-time stats retrieved")
        print(f"  ✅ Total connections: {stats.get('connection_manager', {}).get('total_connections', 0)}")
        
        # Test notification
        print("  Testing notification...")
        await send_notification(
            user_id="test_user",
            title="Test Notification",
            message="This is a test notification",
            notification_type="info"
        )
        print(f"  ✅ Notification sent")
        
        return True
        
    except Exception as e:
        logger.error(f"Streaming functions test failed: {e}")
        print(f"  ❌ Streaming functions test failed: {e}")
        return False


async def main():
    """Run all API tests"""
    print("🚀 Atulya Tantra AGI - Web API Test Suite")
    print("=" * 70)
    
    # Test results
    test_results = []
    
    # Test 1: HTTP API Tests
    api_tester = APITester()
    try:
        test_results.append(await api_tester.test_root_endpoint())
        test_results.append(await api_tester.test_health_endpoint())
        test_results.append(await api_tester.test_user_registration())
        test_results.append(await api_tester.test_user_login())
        test_results.append(await api_tester.test_authenticated_endpoint())
        test_results.append(await api_tester.test_chat_endpoint())
        test_results.append(await api_tester.test_task_endpoint())
        test_results.append(await api_tester.test_system_endpoints())
    finally:
        await api_tester.close()
    
    # Test 2: WebSocket Tests
    ws_tester = WebSocketTester()
    test_results.append(await ws_tester.test_websocket_connection())
    test_results.append(await ws_tester.test_chat_websocket())
    
    # Test 3: Streaming Functions
    test_results.append(await test_streaming_functions())
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Test Summary:")
    
    test_names = [
        "Root Endpoint",
        "Health Endpoint",
        "User Registration",
        "User Login",
        "Authenticated Endpoint",
        "Chat Endpoint",
        "Task Endpoint",
        "System Endpoints",
        "WebSocket Connection",
        "Chat WebSocket",
        "Streaming Functions"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, test_results)):
        print(f"  {name}: {'✅' if result else '❌'}")
    
    total_tests = len(test_results)
    passed_tests = sum(test_results)
    
    print(f"\n🎯 Overall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Web API is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the logs for details.")
    
    # Note about server requirement
    print("\n📝 Note: These tests require the FastAPI server to be running.")
    print("   Start the server with: python -m Core.api.main")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user.")
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        print(f"❌ Test suite failed: {e}")
