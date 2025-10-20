#!/usr/bin/env python3
"""
Atulya Tantra - Basic Import Test
Version: 2.5.0
Basic test to verify all modules can be imported
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test basic imports"""
    print("🧪 Testing Basic Imports...")
    
    try:
        # Test core modules
        import src.core
        print("✅ src.core imported")
        
        import src.api
        print("✅ src.api imported")
        
        import src.services
        print("✅ src.services imported")
        
        import src.models
        print("✅ src.models imported")
        
        import src.integrations
        print("✅ src.integrations imported")
        
        # Test specific components
        from src.core.agents.jarvis import PersonalityEngine
        print("✅ PersonalityEngine imported")
        
        from src.core.agents.skynet import SystemMonitor
        print("✅ SystemMonitor imported")
        
        from src.core.agents.specialized import CodeAgent
        print("✅ CodeAgent imported")
        
        from src.core.memory import EpisodicMemory
        print("✅ EpisodicMemory imported")
        
        from src.core.reasoning import ChainOfThoughtReasoner, PlanningEngine
        print("✅ ChainOfThoughtReasoner and PlanningEngine imported")
        
        from src.core.security import RateLimiter
        print("✅ RateLimiter imported")
        
        from src.integrations import CalendarIntegration
        print("✅ CalendarIntegration imported")
        
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False

def test_file_structure():
    """Test file structure"""
    print("\n🧪 Testing File Structure...")
    
    required_files = [
        "src/main.py",
        "src/api/routes/chat.py",
        "src/api/routes/admin.py",
        "src/api/routes/health.py",
        "src/services/ai_service.py",
        "src/services/chat_service.py",
        "src/core/agents/jarvis/personality.py",
        "src/core/agents/skynet/monitor.py",
        "src/core/agents/specialized/code_agent.py",
        "src/core/memory/episodic.py",
        "src/core/reasoning/chain_of_thought.py",
        "src/core/security/encryption.py",
        "src/integrations/calendar.py",
        "webui/index.html",
        "requirements.txt",
        "README.md",
        "Dockerfile",
        "docker-compose.yml"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    else:
        print("✅ All required files present")
        return True

def main():
    """Main test function"""
    print("🚀 Atulya Tantra Level 5 AGI System - Basic Test")
    print("=" * 60)
    
    tests = [
        ("Basic Imports", test_imports),
        ("File Structure", test_file_structure)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            result = test_func()
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
        print("🎉 Basic tests passed! Atulya Tantra Level 5 AGI System structure is correct!")
        return True
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
