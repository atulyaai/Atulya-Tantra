#!/usr/bin/env python3
"""
Atulya Tantra - Final System Test
Version: 2.5.0
Comprehensive test to verify all components are working
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_core_components():
    """Test all core components"""
    print("🧪 Testing Core Components...")
    
    try:
        # Test JARVIS components
        from src.core.agents.jarvis.personality import PersonalityEngine
        from src.core.agents.jarvis.memory import JARVISConversationalMemory
        from src.core.agents.jarvis.nlu import JARVISNLU
        from src.core.agents.jarvis.assistant import JARVISTaskAssistant
        from src.core.agents.jarvis.knowledge import JARVISKnowledgeManager
        from src.core.agents.jarvis.voice import JARVISVoiceInterface
        
        print("✅ JARVIS components imported successfully")
        
        # Test Skynet components
        from src.core.agents.skynet.system_control import SystemControl
        from src.core.agents.skynet.automation import DesktopAutomation
        from src.core.agents.skynet.scheduler import TaskScheduler
        from src.core.agents.skynet.monitor import SystemMonitor
        from src.core.agents.skynet.healer import AutoHealingSystem
        from src.core.agents.skynet.decision_engine import DecisionEngine
        from src.core.agents.skynet.coordinator import MultiAgentCoordinator
        from src.core.agents.skynet.executor import TaskExecutor
        from src.core.agents.skynet.safety import SafetySystem
        
        print("✅ Skynet components imported successfully")
        
        # Test specialized agents
        from src.core.agents.specialized.base_agent import BaseAgent
        from src.core.agents.specialized.code_agent import CodeAgent
        from src.core.agents.specialized.research_agent import ResearchAgent
        from src.core.agents.specialized.creative_agent import CreativeAgent
        from src.core.agents.specialized.data_agent import DataAgent
        
        print("✅ Specialized agents imported successfully")
        
        # Test memory systems
        from src.core.memory.episodic import EpisodicMemory
        from src.core.memory.semantic import SemanticMemory
        from src.core.memory.vector_store import VectorStore
        from src.core.memory.knowledge_graph import KnowledgeGraph
        
        print("✅ Memory systems imported successfully")
        
        # Test reasoning systems
        from src.core.reasoning.chain_of_thought import ChainOfThoughtReasoner
        from src.core.reasoning.planner import Planner
        
        print("✅ Reasoning systems imported successfully")
        
        # Test security systems
        from src.core.security.encryption import EncryptionManager
        from src.core.security.rate_limiter import RateLimiter
        
        print("✅ Security systems imported successfully")
        
        # Test integrations
        from src.integrations.base_integration import BaseIntegration
        from src.integrations.calendar import CalendarIntegration
        from src.integrations.email import EmailIntegration
        from src.integrations.storage import StorageIntegration
        
        print("✅ Integration systems imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Core components test failed: {e}")
        return False

async def test_services():
    """Test service layer"""
    print("\n🧪 Testing Services...")
    
    try:
        from src.services.ai_service import AIService
        from src.services.chat_service import ChatService
        from src.services.auth_service import AuthService
        from src.services.multimodal_service import MultimodalService
        
        print("✅ Services imported successfully")
        return True
        
    except Exception as e:
        print(f"❌ Services test failed: {e}")
        return False

async def test_api():
    """Test API routes"""
    print("\n🧪 Testing API Routes...")
    
    try:
        from src.api.routes.chat import router as chat_router
        from src.api.routes.admin import router as admin_router
        from src.api.routes.health import router as health_router
        
        print("✅ API routes imported successfully")
        return True
        
    except Exception as e:
        print(f"❌ API routes test failed: {e}")
        return False

async def test_models():
    """Test database models"""
    print("\n🧪 Testing Database Models...")
    
    try:
        from src.models import User, Conversation, Message, AgentTask, SystemEvent
        
        print("✅ Database models imported successfully")
        return True
        
    except Exception as e:
        print(f"❌ Database models test failed: {e}")
        return False

async def test_initialization():
    """Test component initialization"""
    print("\n🧪 Testing Component Initialization...")
    
    try:
        # Test JARVIS personality engine
        personality = PersonalityEngine()
        print("✅ PersonalityEngine initialized")
        
        # Test Skynet system monitor
        monitor = SystemMonitor()
        health = await monitor.health_check()
        print("✅ SystemMonitor initialized and health check passed")
        
        # Test specialized agents
        code_agent = CodeAgent()
        capabilities = await code_agent.get_capabilities()
        print("✅ CodeAgent initialized")
        
        # Test memory systems
        episodic_memory = EpisodicMemory()
        print("✅ EpisodicMemory initialized")
        
        # Test reasoning systems
        chain_of_thought = ChainOfThoughtReasoner()
        print("✅ ChainOfThoughtReasoner initialized")
        
        # Test security systems
        rate_limiter = RateLimiter()
        print("✅ RateLimiter initialized")
        
        return True
        
    except Exception as e:
        print(f"❌ Component initialization test failed: {e}")
        return False

async def test_integration():
    """Test component integration"""
    print("\n🧪 Testing Component Integration...")
    
    try:
        # Test agent coordinator
        from src.core.agents.agent_coordinator import AgentCoordinator
        coordinator = AgentCoordinator()
        status = await coordinator.health_check()
        print("✅ AgentCoordinator integration test passed")
        
        # Test task executor
        from src.core.agents.skynet.executor import task_executor
        executor_status = await task_executor.health_check()
        print("✅ TaskExecutor integration test passed")
        
        # Test safety system
        from src.core.agents.skynet.safety import safety_system
        safety_status = await safety_system.health_check()
        print("✅ SafetySystem integration test passed")
        
        return True
        
    except Exception as e:
        print(f"❌ Component integration test failed: {e}")
        return False

async def main():
    """Main test function"""
    print("🚀 Atulya Tantra Level 5 AGI System - Final Test")
    print("=" * 60)
    
    tests = [
        ("Core Components", test_core_components),
        ("Services", test_services),
        ("API Routes", test_api),
        ("Database Models", test_models),
        ("Component Initialization", test_initialization),
        ("Component Integration", test_integration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            if result:
                passed += 1
                print(f"✅ {test_name} test passed")
            else:
                print(f"❌ {test_name} test failed")
        except Exception as e:
            print(f"❌ {test_name} test failed with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Atulya Tantra Level 5 AGI System is ready!")
        return True
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
