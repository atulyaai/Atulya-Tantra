"""
Complete System Integration Test for Atulya Tantra AGI
Tests all major components and their integration
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any, List

# Import core components
from Core.agi_core import AGICore, SystemMode, TaskType
from Core.unified_agi_system import UnifiedAGISystem
from Core.brain.llm_provider import LLMProvider
from Core.agents.agent_factory import get_agent_factory
from Core.memory.vector_store import get_vector_store
from Core.memory.knowledge_graph import get_knowledge_graph
from Core.conversation.natural_conversation import get_conversation_engine
from Core.skynet.auto_healer import get_auto_healer
from Core.monitoring.alerting import get_alert_manager
from Core.auth import create_access_token, hash_password, verify_password
from Core.api.main import app
from Core.config.logging import get_logger

logger = get_logger(__name__)


class SystemIntegrationTest:
    """Complete system integration test"""
    
    def __init__(self):
        self.test_results = []
        self.start_time = None
        self.end_time = None
        
    async def run_all_tests(self):
        """Run all integration tests"""
        print("🚀 Starting Atulya Tantra AGI System Integration Tests")
        print("=" * 60)
        
        self.start_time = time.time()
        
        # Test core components
        await self.test_agi_core()
        await self.test_unified_system()
        await self.test_llm_providers()
        await self.test_agent_factory()
        await self.test_memory_systems()
        await self.test_conversation_engine()
        await self.test_skynet_system()
        await self.test_monitoring_system()
        await self.test_auth_system()
        await self.test_api_endpoints()
        
        self.end_time = time.time()
        
        # Print results
        self.print_test_results()
        
    async def test_agi_core(self):
        """Test AGI Core functionality"""
        print("\n🧠 Testing AGI Core...")
        
        try:
            # Test AGI Core initialization
            agi_core = AGICore()
            
            # Test reasoning
            reasoning_result = await agi_core.reason_about("What is the meaning of life?")
            assert reasoning_result is not None
            
            # Test planning
            plan = await agi_core.create_plan("Write a Python function to calculate fibonacci numbers")
            assert plan is not None
            assert len(plan.steps) > 0
            
            # Test learning
            learning_result = await agi_core.learn_from_experience(
                "Successfully completed a coding task",
                {"task": "fibonacci", "success": True}
            )
            assert learning_result is not None
            
            self.test_results.append({
                "component": "AGI Core",
                "status": "PASS",
                "details": "All core functions working correctly"
            })
            print("✅ AGI Core tests passed")
            
        except Exception as e:
            self.test_results.append({
                "component": "AGI Core",
                "status": "FAIL",
                "details": f"Error: {str(e)}"
            })
            print(f"❌ AGI Core tests failed: {e}")
    
    async def test_unified_system(self):
        """Test Unified AGI System"""
        print("\n🔗 Testing Unified AGI System...")
        
        try:
            # Test system initialization
            system = UnifiedAGISystem()
            await system.initialize()
            
            # Test system modes
            await system.start(SystemMode.CONVERSATIONAL)
            assert system.is_active
            
            # Test user input processing
            response = await system.process_user_input("Hello, how are you?")
            assert response is not None
            
            # Test action execution
            action_result = await system.execute_action("test_action", {"param": "value"})
            assert action_result is not None
            
            # Test system stop
            await system.stop()
            assert not system.is_active
            
            self.test_results.append({
                "component": "Unified AGI System",
                "status": "PASS",
                "details": "System lifecycle and operations working correctly"
            })
            print("✅ Unified AGI System tests passed")
            
        except Exception as e:
            self.test_results.append({
                "component": "Unified AGI System",
                "status": "FAIL",
                "details": f"Error: {str(e)}"
            })
            print(f"❌ Unified AGI System tests failed: {e}")
    
    async def test_llm_providers(self):
        """Test LLM Providers"""
        print("\n🤖 Testing LLM Providers...")
        
        try:
            # Test provider initialization
            from Core.brain.llm_provider import LLMProviderRouter
            router = LLMProviderRouter()
            
            # Test provider registration
            router.register_provider("test", "Test Provider")
            assert "test" in router.providers
            
            # Test provider selection
            provider = router.get_provider("test")
            assert provider is not None
            
            # Test response generation
            response = await router.generate_response(
                prompt="Test prompt",
                provider="test",
                max_tokens=100
            )
            assert response is not None
            
            self.test_results.append({
                "component": "LLM Providers",
                "status": "PASS",
                "details": "Provider management and response generation working"
            })
            print("✅ LLM Providers tests passed")
            
        except Exception as e:
            self.test_results.append({
                "component": "LLM Providers",
                "status": "FAIL",
                "details": f"Error: {str(e)}"
            })
            print(f"❌ LLM Providers tests failed: {e}")
    
    async def test_agent_factory(self):
        """Test Agent Factory"""
        print("\n🏭 Testing Agent Factory...")
        
        try:
            factory = get_agent_factory()
            
            # Test agent creation
            agent_id = await factory.create_agent("default_code_agent")
            assert agent_id is not None
            
            # Test agent start
            success = await factory.start_agent(agent_id)
            assert success
            
            # Test agent execution
            result = await factory.execute_task(agent_id, "test_task", {"param": "value"})
            assert result is not None
            
            # Test agent stop
            success = await factory.stop_agent(agent_id)
            assert success
            
            # Test agent removal
            success = await factory.remove_agent(agent_id)
            assert success
            
            self.test_results.append({
                "component": "Agent Factory",
                "status": "PASS",
                "details": "Agent lifecycle management working correctly"
            })
            print("✅ Agent Factory tests passed")
            
        except Exception as e:
            self.test_results.append({
                "component": "Agent Factory",
                "status": "FAIL",
                "details": f"Error: {str(e)}"
            })
            print(f"❌ Agent Factory tests failed: {e}")
    
    async def test_memory_systems(self):
        """Test Memory Systems"""
        print("\n🧠 Testing Memory Systems...")
        
        try:
            # Test Vector Store
            vector_store = get_vector_store()
            
            # Test memory storage
            memory_id = await vector_store.store_memory(
                content="Test memory content",
                metadata={"type": "test"},
                user_id="test_user"
            )
            assert memory_id is not None
            
            # Test memory search
            results = await vector_store.search_memory("test", user_id="test_user")
            assert len(results) > 0
            
            # Test Knowledge Graph
            knowledge_graph = get_knowledge_graph()
            
            # Test node creation
            node_id = await knowledge_graph.create_node(
                label="Test Node",
                node_type="test",
                properties={"key": "value"},
                user_id="test_user"
            )
            assert node_id is not None
            
            # Test edge creation
            edge_id = await knowledge_graph.create_edge(
                source=node_id,
                target=node_id,
                relationship="test_relation",
                user_id="test_user"
            )
            assert edge_id is not None
            
            # Test graph query
            query_results = await knowledge_graph.query_graph("test", user_id="test_user")
            assert len(query_results) > 0
            
            self.test_results.append({
                "component": "Memory Systems",
                "status": "PASS",
                "details": "Vector store and knowledge graph working correctly"
            })
            print("✅ Memory Systems tests passed")
            
        except Exception as e:
            self.test_results.append({
                "component": "Memory Systems",
                "status": "FAIL",
                "details": f"Error: {str(e)}"
            })
            print(f"❌ Memory Systems tests failed: {e}")
    
    async def test_conversation_engine(self):
        """Test Conversation Engine"""
        print("\n💬 Testing Conversation Engine...")
        
        try:
            engine = get_conversation_engine()
            
            # Test message processing
            response = await engine.process_message(
                user_id="test_user",
                session_id="test_session",
                message="Hello, how are you?"
            )
            assert response is not None
            assert response.message is not None
            
            # Test conversation history
            history = await engine.get_conversation_history(
                user_id="test_user",
                session_id="test_session"
            )
            assert isinstance(history, list)
            
            # Test conversation clearing
            success = await engine.clear_conversation(
                user_id="test_user",
                session_id="test_session"
            )
            assert success
            
            self.test_results.append({
                "component": "Conversation Engine",
                "status": "PASS",
                "details": "Message processing and conversation management working"
            })
            print("✅ Conversation Engine tests passed")
            
        except Exception as e:
            self.test_results.append({
                "component": "Conversation Engine",
                "status": "FAIL",
                "details": f"Error: {str(e)}"
            })
            print(f"❌ Conversation Engine tests failed: {e}")
    
    async def test_skynet_system(self):
        """Test Skynet System"""
        print("\n🤖 Testing Skynet System...")
        
        try:
            auto_healer = get_auto_healer()
            
            # Test healing rules
            rules = await auto_healer.get_heal_rules()
            assert len(rules) > 0
            
            # Test healing check
            attempts = await auto_healer.check_and_heal()
            assert isinstance(attempts, list)
            
            # Test component status
            status = await auto_healer.get_component_status()
            assert isinstance(status, dict)
            
            # Test healing stats
            stats = await auto_healer.get_healing_stats()
            assert isinstance(stats, dict)
            
            self.test_results.append({
                "component": "Skynet System",
                "status": "PASS",
                "details": "Auto-healing and system monitoring working"
            })
            print("✅ Skynet System tests passed")
            
        except Exception as e:
            self.test_results.append({
                "component": "Skynet System",
                "status": "FAIL",
                "details": f"Error: {str(e)}"
            })
            print(f"❌ Skynet System tests failed: {e}")
    
    async def test_monitoring_system(self):
        """Test Monitoring System"""
        print("\n📊 Testing Monitoring System...")
        
        try:
            alert_manager = get_alert_manager()
            
            # Test alert sending
            alert_id = await alert_manager.send_alert(
                level="info",
                message="Test alert",
                component="test_component"
            )
            assert alert_id is not None
            
            # Test alert retrieval
            alerts = await alert_manager.get_alerts(limit=10)
            assert isinstance(alerts, list)
            
            # Test alert acknowledgment
            success = await alert_manager.acknowledge_alert(alert_id)
            assert success
            
            # Test alert resolution
            success = await alert_manager.resolve_alert(alert_id)
            assert success
            
            # Test alert stats
            stats = await alert_manager.get_alert_stats()
            assert isinstance(stats, dict)
            
            self.test_results.append({
                "component": "Monitoring System",
                "status": "PASS",
                "details": "Alerting and monitoring working correctly"
            })
            print("✅ Monitoring System tests passed")
            
        except Exception as e:
            self.test_results.append({
                "component": "Monitoring System",
                "status": "FAIL",
                "details": f"Error: {str(e)}"
            })
            print(f"❌ Monitoring System tests failed: {e}")
    
    async def test_auth_system(self):
        """Test Authentication System"""
        print("\n🔐 Testing Authentication System...")
        
        try:
            # Test password hashing
            password = "test_password_123"
            hashed = hash_password(password)
            assert hashed != password
            
            # Test password verification
            is_valid = verify_password(password, hashed)
            assert is_valid
            
            # Test token creation
            token = create_access_token({"sub": "test_user", "username": "test"})
            assert token is not None
            
            # Test token verification
            from Core.auth import verify_token
            payload = verify_token(token)
            assert payload is not None
            assert payload["sub"] == "test_user"
            
            self.test_results.append({
                "component": "Authentication System",
                "status": "PASS",
                "details": "Password hashing and token management working"
            })
            print("✅ Authentication System tests passed")
            
        except Exception as e:
            self.test_results.append({
                "component": "Authentication System",
                "status": "FAIL",
                "details": f"Error: {str(e)}"
            })
            print(f"❌ Authentication System tests failed: {e}")
    
    async def test_api_endpoints(self):
        """Test API Endpoints"""
        print("\n🌐 Testing API Endpoints...")
        
        try:
            # Test FastAPI app creation
            assert app is not None
            
            # Test root endpoint
            from fastapi.testclient import TestClient
            client = TestClient(app)
            
            response = client.get("/")
            assert response.status_code == 200
            
            # Test health endpoint
            response = client.get("/health")
            assert response.status_code in [200, 503]  # 503 if AGI system not initialized
            
            # Test API status endpoint
            response = client.get("/api/status")
            assert response.status_code == 200
            
            self.test_results.append({
                "component": "API Endpoints",
                "status": "PASS",
                "details": "API endpoints responding correctly"
            })
            print("✅ API Endpoints tests passed")
            
        except Exception as e:
            self.test_results.append({
                "component": "API Endpoints",
                "status": "FAIL",
                "details": f"Error: {str(e)}"
            })
            print(f"❌ API Endpoints tests failed: {e}")
    
    def print_test_results(self):
        """Print test results summary"""
        print("\n" + "=" * 60)
        print("📋 TEST RESULTS SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["status"] == "PASS"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
            print(f"Total Duration: {duration:.2f} seconds")
        
        print("\n📝 DETAILED RESULTS:")
        print("-" * 60)
        
        for result in self.test_results:
            status_icon = "✅" if result["status"] == "PASS" else "❌"
            print(f"{status_icon} {result['component']}: {result['status']}")
            print(f"   Details: {result['details']}")
            print()
        
        if failed_tests == 0:
            print("🎉 ALL TESTS PASSED! System is ready for production.")
        else:
            print(f"⚠️  {failed_tests} tests failed. Please review and fix issues.")
        
        print("=" * 60)


async def main():
    """Main test function"""
    test = SystemIntegrationTest()
    await test.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())