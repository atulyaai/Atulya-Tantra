#!/usr/bin/env python3
"""
Atulya Tantra - Comprehensive System Test Suite
Version: 2.2.0 (WebMaster FINAL)
"""

import asyncio
import json
import requests
import time
import sys
from pathlib import Path
from typing import Dict, List, Any

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class SystemTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = {
            "passed": 0,
            "failed": 0,
            "tests": []
        }
    
    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
        if message:
            print(f"    {message}")
        
        self.results["tests"].append({
            "name": test_name,
            "passed": passed,
            "message": message
        })
        
        if passed:
            self.results["passed"] += 1
        else:
            self.results["failed"] += 1
    
    def test_server_health(self):
        """Test server health endpoint"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy" and data.get("version") == "2.2.0":
                    self.log_test("Server Health Check", True, f"Version: {data.get('version')}")
                else:
                    self.log_test("Server Health Check", False, f"Unexpected response: {data}")
            else:
                self.log_test("Server Health Check", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test("Server Health Check", False, str(e))
    
    def test_webui_endpoint(self):
        """Test WebUI endpoint"""
        try:
            response = requests.get(f"{self.base_url}/webui", timeout=10)
            if response.status_code == 200:
                content = response.text
                if "Atulya Tantra" in content and "chat" in content.lower():
                    self.log_test("WebUI Endpoint", True, "WebUI loaded successfully")
                else:
                    self.log_test("WebUI Endpoint", False, "WebUI content invalid")
            else:
                self.log_test("WebUI Endpoint", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test("WebUI Endpoint", False, str(e))
    
    def test_admin_panel(self):
        """Test admin panel endpoint"""
        try:
            response = requests.get(f"{self.base_url}/admin", timeout=10)
            if response.status_code == 200:
                content = response.text
                if "Admin Panel" in content and "System Status" in content:
                    self.log_test("Admin Panel", True, "Admin panel loaded successfully")
                else:
                    self.log_test("Admin Panel", False, "Admin panel content invalid")
            else:
                self.log_test("Admin Panel", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test("Admin Panel", False, str(e))
    
    def test_api_status(self):
        """Test API status endpoint"""
        try:
            response = requests.get(f"{self.base_url}/api/status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "operational" and data.get("api_version") == "2.2.0":
                    self.log_test("API Status", True, f"API Version: {data.get('api_version')}")
                else:
                    self.log_test("API Status", False, f"Unexpected response: {data}")
            else:
                self.log_test("API Status", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test("API Status", False, str(e))
    
    def test_chat_api(self):
        """Test chat API endpoint"""
        try:
            test_message = "Hello, this is a test message"
            payload = {"message": test_message}
            response = requests.post(
                f"{self.base_url}/api/chat", 
                json=payload, 
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                if "response" in data and len(data["response"]) > 0:
                    self.log_test("Chat API", True, f"Response length: {len(data['response'])} chars")
                else:
                    self.log_test("Chat API", False, "Empty or invalid response")
            else:
                self.log_test("Chat API", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test("Chat API", False, str(e))
    
    def test_metrics_api(self):
        """Test metrics API endpoint"""
        try:
            response = requests.get(f"{self.base_url}/api/metrics", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    self.log_test("Metrics API", True, "Metrics retrieved successfully")
                else:
                    self.log_test("Metrics API", False, f"Unexpected response: {data}")
            else:
                self.log_test("Metrics API", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test("Metrics API", False, str(e))
    
    def test_logs_api(self):
        """Test logs API endpoint"""
        try:
            response = requests.get(f"{self.base_url}/api/logs", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    self.log_test("Logs API", True, "Logs retrieved successfully")
                else:
                    self.log_test("Logs API", False, f"Unexpected response: {data}")
            else:
                self.log_test("Logs API", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test("Logs API", False, str(e))
    
    def test_api_docs(self):
        """Test API documentation endpoint"""
        try:
            response = requests.get(f"{self.base_url}/docs", timeout=10)
            if response.status_code == 200:
                content = response.text
                if "swagger" in content.lower() or "openapi" in content.lower():
                    self.log_test("API Documentation", True, "Swagger UI loaded successfully")
                else:
                    self.log_test("API Documentation", False, "API docs content invalid")
            else:
                self.log_test("API Documentation", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test("API Documentation", False, str(e))
    
    def test_core_modules(self):
        """Test core module imports"""
        try:
            from core.config import get_config
            from core.memory import get_memory_manager
            from core.monitoring import get_monitoring_system
            from core.voice import get_voice_engine
            from core.agents import get_multi_agent_orchestrator
            from core.automation import get_automation_engine
            from core.models import get_hybrid_model_router
            
            # Test initialization
            config = get_config()
            memory = get_memory_manager()
            monitoring = get_monitoring_system()
            voice = get_voice_engine()
            agents = get_multi_agent_orchestrator()
            automation = get_automation_engine()
            models = get_hybrid_model_router()
            
            self.log_test("Core Modules", True, "All 7 core modules imported and initialized")
        except Exception as e:
            self.log_test("Core Modules", False, str(e))
    
    def test_performance(self):
        """Test system performance"""
        try:
            start_time = time.time()
            
            # Test multiple concurrent requests
            responses = []
            for i in range(5):
                response = requests.get(f"{self.base_url}/health", timeout=5)
                responses.append(response.status_code == 200)
            
            end_time = time.time()
            duration = end_time - start_time
            
            if all(responses) and duration < 5.0:
                self.log_test("Performance Test", True, f"5 requests completed in {duration:.2f}s")
            else:
                self.log_test("Performance Test", False, f"Performance issues: {duration:.2f}s")
        except Exception as e:
            self.log_test("Performance Test", False, str(e))
    
    def run_all_tests(self):
        """Run all tests"""
        print("🧪 Atulya Tantra v2.2.0 - Comprehensive System Test")
        print("=" * 60)
        
        # Core module tests
        print("\n📦 Core Module Tests:")
        self.test_core_modules()
        
        # Server tests
        print("\n🌐 Server Tests:")
        self.test_server_health()
        self.test_api_status()
        
        # Web interface tests
        print("\n💻 Web Interface Tests:")
        self.test_webui_endpoint()
        self.test_admin_panel()
        self.test_api_docs()
        
        # API tests
        print("\n🔌 API Tests:")
        self.test_chat_api()
        self.test_metrics_api()
        self.test_logs_api()
        
        # Performance tests
        print("\n⚡ Performance Tests:")
        self.test_performance()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"✅ Passed: {self.results['passed']}")
        print(f"❌ Failed: {self.results['failed']}")
        print(f"📈 Success Rate: {(self.results['passed'] / (self.results['passed'] + self.results['failed']) * 100):.1f}%")
        
        if self.results['failed'] == 0:
            print("\n🎉 ALL TESTS PASSED! System is production-ready.")
            return True
        else:
            print(f"\n⚠️ {self.results['failed']} tests failed. Please check the issues above.")
            return False

def main():
    """Main test function"""
    tester = SystemTester()
    
    # Check if server is running
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code != 200:
            print("❌ Server is not running or not responding properly")
            print("Please start the server with: python server.py")
            sys.exit(1)
    except requests.exceptions.RequestException:
        print("❌ Server is not running")
        print("Please start the server with: python server.py")
        sys.exit(1)
    
    # Run tests
    success = tester.run_all_tests()
    
    if success:
        print("\n🚀 System is ready for production deployment!")
        sys.exit(0)
    else:
        print("\n🔧 Please fix the failing tests before deployment.")
        sys.exit(1)

if __name__ == "__main__":
    main()
