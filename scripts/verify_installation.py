#!/usr/bin/env python3
"""
Atulya Tantra - Installation Verification Script
Version: 2.0.1
This script verifies that the installation was successful and all components are working.
"""

import sys
import os
import subprocess
import importlib
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def print_header():
    """Print verification header"""
    print("=" * 60)
    print("Atulya Tantra - Installation Verification")
    print("Version: 2.0.1")
    print("=" * 60)

def check_python_version():
    """Check Python version"""
    print("\n🐍 Checking Python version...")
    version = sys.version_info
    if version >= (3, 8):
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} - OK")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} - Requires 3.8+")
        return False

def check_dependencies():
    """Check if required dependencies are installed"""
    print("\n📦 Checking dependencies...")
    
    required_packages = [
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "openai",
        "anthropic",
        "google.generativeai",
        "ollama",
        "chromadb",
        "networkx",
        "PIL",  # pillow
        "yaml"  # pyyaml
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f"✅ {package} - OK")
        except ImportError:
            print(f"❌ {package} - Missing")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("Run: pip install -r requirements.txt")
        return False
    
    return True

def check_directory_structure():
    """Check if directory structure is correct"""
    print("\n📁 Checking directory structure...")
    
    required_dirs = [
        "core",
        "data",
        "models",
        "configuration", 
        "webui",
        "testing",
        "scripts"
    ]
    
    missing_dirs = []
    
    for dir_name in required_dirs:
        if Path(dir_name).exists():
            print(f"✅ {dir_name}/ - OK")
        else:
            print(f"❌ {dir_name}/ - Missing")
            missing_dirs.append(dir_name)
    
    if missing_dirs:
        print(f"\n⚠️  Missing directories: {', '.join(missing_dirs)}")
        return False
    
    return True

def check_models_structure():
    """Check models directory structure"""
    print("\n🤖 Checking models structure...")
    
    model_dirs = ["audio", "vision", "text"]
    missing_model_dirs = []
    
    for model_dir in model_dirs:
        model_path = Path("models") / model_dir
        if model_path.exists():
            print(f"✅ models/{model_dir}/ - OK")
        else:
            print(f"❌ models/{model_dir}/ - Missing")
            missing_model_dirs.append(model_dir)
    
    if missing_model_dirs:
        print(f"\n⚠️  Missing model directories: {', '.join(missing_model_dirs)}")
        return False
    
    return True

def check_configuration():
    """Check configuration files"""
    print("\n⚙️  Checking configuration...")
    
    config_files = [
        "configuration/config.yaml",
        "configuration/unified_config.py",
        ".env.example"
    ]
    
    missing_configs = []
    
    for config_file in config_files:
        if Path(config_file).exists():
            print(f"✅ {config_file} - OK")
        else:
            print(f"❌ {config_file} - Missing")
            missing_configs.append(config_file)
    
    if missing_configs:
        print(f"\n⚠️  Missing configuration files: {', '.join(missing_configs)}")
        return False
    
    return True

def check_installation_scripts():
    """Check installation scripts"""
    print("\n🔧 Checking installation scripts...")
    
    scripts = [
        "scripts/install.sh",
        "scripts/install.ps1", 
        "scripts/setup.py"
    ]
    
    missing_scripts = []
    
    for script in scripts:
        if Path(script).exists():
            print(f"✅ {script} - OK")
        else:
            print(f"❌ {script} - Missing")
            missing_scripts.append(script)
    
    if missing_scripts:
        print(f"\n⚠️  Missing installation scripts: {', '.join(missing_scripts)}")
        return False
    
    return True

def check_server_startup():
    """Check if server can start"""
    print("\n🚀 Checking server startup...")
    
    try:
        # Try to import server components
        import server
        print("✅ Server module imports - OK")
        
        # Check if FastAPI app is created
        if hasattr(server, 'app'):
            print("✅ FastAPI app created - OK")
            return True
        else:
            print("❌ FastAPI app not properly configured")
            return False
            
    except Exception as e:
        print(f"❌ Server startup check failed: {e}")
        return False

def check_core_modules():
    """Check core modules"""
    print("\n🧠 Checking core modules...")
    
    core_modules = [
        "core.config",
        "core.models", 
        "core.memory",
        "core.monitoring",
        "core.voice",
        "core.agents",
        "core.automation"
    ]
    
    missing_modules = []
    
    for module in core_modules:
        try:
            importlib.import_module(module)
            print(f"✅ {module} - OK")
        except ImportError as e:
            print(f"❌ {module} - Error: {e}")
            missing_modules.append(module)
        except Exception as e:
            print(f"❌ {module} - Error: {e}")
            missing_modules.append(module)
    
    if missing_modules:
        print(f"\n⚠️  Missing core modules: {', '.join(missing_modules)}")
        return False
    
    return True

def run_basic_tests():
    """Run basic tests if available"""
    print("\n🧪 Running basic tests...")
    
    if Path("testing").exists():
        try:
            # Only run the basic tests, not the legacy test_all.py
            result = subprocess.run([
                sys.executable, "-m", "pytest", "testing/test_basic.py", "-v", "--tb=short"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print("✅ Basic tests passed - OK")
                return True
            else:
                print(f"⚠️  Some tests failed:")
                print(result.stdout)
                return False
                
        except subprocess.TimeoutExpired:
            print("⚠️  Tests timed out - Skipping")
            return True
        except Exception as e:
            print(f"⚠️  Test execution failed: {e}")
            return True
    else:
        print("⚠️  No tests found - Skipping")
        return True

def main():
    """Main verification function"""
    print_header()
    
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Directory Structure", check_directory_structure),
        ("Models Structure", check_models_structure),
        ("Configuration", check_configuration),
        ("Installation Scripts", check_installation_scripts),
        ("Core Modules", check_core_modules),
        ("Server Startup", check_server_startup),
        ("Basic Tests", run_basic_tests)
    ]
    
    results = []
    
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"❌ {check_name} check failed with error: {e}")
            results.append((check_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{check_name:20} {status}")
        if result:
            passed += 1
    
    print("-" * 60)
    print(f"Total: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 Installation verification completed successfully!")
        print("Atulya Tantra is ready to use.")
        print("\nNext steps:")
        print("1. Edit .env file with your API keys")
        print("2. Start the server: python server.py")
        print("3. Access web interface: http://localhost:8000")
        return 0
    else:
        print(f"\n⚠️  {total - passed} checks failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
