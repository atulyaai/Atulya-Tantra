#!/usr/bin/env python3
"""
Atulya Tantra - Structure Test
Version: 2.5.0
Test to verify project structure and file organization
"""

import sys
from pathlib import Path

def test_file_structure():
    """Test file structure"""
    print("🧪 Testing File Structure...")
    
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
        "docker-compose.yml",
        "k8s/deployment.yaml",
        "k8s/service.yaml",
        "config/prometheus.yml",
        "config/nginx.conf"
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

def test_directory_structure():
    """Test directory structure"""
    print("\n🧪 Testing Directory Structure...")
    
    required_dirs = [
        "src",
        "src/api",
        "src/api/routes",
        "src/services",
        "src/core",
        "src/core/agents",
        "src/core/agents/jarvis",
        "src/core/agents/skynet",
        "src/core/agents/specialized",
        "src/core/memory",
        "src/core/reasoning",
        "src/core/security",
        "src/integrations",
        "src/models",
        "webui",
        "k8s",
        "config",
        "tests",
        "tests/unit",
        "tests/integration",
        "tests/e2e",
        "tests/performance",
        "scripts"
    ]
    
    missing_dirs = []
    for dir_path in required_dirs:
        if not Path(dir_path).exists():
            missing_dirs.append(dir_path)
    
    if missing_dirs:
        print(f"❌ Missing directories: {missing_dirs}")
        return False
    else:
        print("✅ All required directories present")
        return True

def test_file_sizes():
    """Test that key files have content"""
    print("\n🧪 Testing File Content...")
    
    key_files = [
        "src/main.py",
        "README.md",
        "requirements.txt",
        "webui/index.html"
    ]
    
    empty_files = []
    for file_path in key_files:
        if Path(file_path).stat().st_size < 100:  # Less than 100 bytes
            empty_files.append(file_path)
    
    if empty_files:
        print(f"❌ Files appear to be empty or too small: {empty_files}")
        return False
    else:
        print("✅ Key files have content")
        return True

def main():
    """Main test function"""
    print("🚀 Atulya Tantra Level 5 AGI System - Structure Test")
    print("=" * 60)
    
    tests = [
        ("File Structure", test_file_structure),
        ("Directory Structure", test_directory_structure),
        ("File Content", test_file_sizes)
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
        print("🎉 All structure tests passed! Atulya Tantra Level 5 AGI System is properly organized!")
        return True
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
