#!/usr/bin/env python3
"""
Atulya Tantra AGI - Automated Setup and Configuration
Automatically sets up the environment, installs dependencies, and configures the system
"""

import os
import sys
import subprocess
import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

class AutomatedSetup:
    """Automated setup and configuration for Atulya Tantra AGI"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from config.json or create default"""
        config_file = self.project_root / "config.json"
        
        default_config = {
            "python_version": "3.11+",
            "auto_install_deps": True,
            "auto_setup_env": True,
            "auto_configure_ai": True,
            "auto_run_tests": True,
            "ai_providers": {
                "primary": "ollama",
                "ollama": {
                    "enabled": True,
                    "base_url": "http://localhost:11434",
                    "model": "gemma2:2b"
                },
                "openai": {
                    "enabled": False,
                    "api_key": "",
                    "model": "gpt-4-turbo"
                },
                "anthropic": {
                    "enabled": False,
                    "api_key": "",
                    "model": "claude-3-5-sonnet-20241022"
                }
            },
            "database": {
                "type": "sqlite",
                "path": "data/tantra.db"
            },
            "features": {
                "voice_enabled": True,
                "autonomous_operations": False,
                "streaming_enabled": True,
                "multimodal_enabled": True
            }
        }
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Error loading config: {e}, using defaults")
        
        return default_config
    
    def _save_config(self):
        """Save current configuration"""
        config_file = self.project_root / "config.json"
        with open(config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
        print(f"✅ Configuration saved to {config_file}")
    
    def check_python_version(self) -> bool:
        """Check if Python version is compatible"""
        print("🐍 Checking Python version...")
        
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 11):
            print(f"❌ Python 3.11+ required, found {version.major}.{version.minor}")
            return False
        
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} is compatible")
        return True
    
    def setup_virtual_environment(self) -> bool:
        """Set up Python virtual environment"""
        print("📦 Setting up virtual environment...")
        
        venv_path = self.project_root / "venv"
        
        if venv_path.exists():
            print("✅ Virtual environment already exists")
            return True
        
        try:
            subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
            print("✅ Virtual environment created")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to create virtual environment: {e}")
            return False
    
    def install_dependencies(self) -> bool:
        """Install Python dependencies"""
        print("📥 Installing dependencies...")
        
        requirements_file = self.project_root / "requirements.txt"
        if not requirements_file.exists():
            print("❌ requirements.txt not found")
            return False
        
        try:
            # Determine pip path based on OS
            if os.name == 'nt':  # Windows
                pip_path = self.project_root / "venv" / "Scripts" / "pip.exe"
            else:  # Unix/Linux/macOS
                pip_path = self.project_root / "venv" / "bin" / "pip"
            
            subprocess.run([str(pip_path), "install", "-r", str(requirements_file)], check=True)
            print("✅ Dependencies installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install dependencies: {e}")
            return False
    
    def setup_environment_file(self) -> bool:
        """Set up .env file from configuration"""
        print("⚙️ Setting up environment configuration...")
        
        env_file = self.project_root / ".env"
        env_example = self.project_root / "env.example"
        
        if env_file.exists():
            print("✅ .env file already exists")
            return True
        
        if not env_example.exists():
            print("❌ env.example not found")
            return False
        
        try:
            # Copy example and customize
            shutil.copy(env_example, env_file)
            
            # Update with config values
            with open(env_file, 'r') as f:
                content = f.read()
            
            # Replace placeholders with config values
            content = content.replace("PRIMARY_AI_PROVIDER=ollama", f"PRIMARY_AI_PROVIDER={self.config['ai_providers']['primary']}")
            content = content.replace("OLLAMA_MODEL=gemma2:2b", f"OLLAMA_MODEL={self.config['ai_providers']['ollama']['model']}")
            content = content.replace("VOICE_ENABLED=true", f"VOICE_ENABLED={str(self.config['features']['voice_enabled']).lower()}")
            content = content.replace("AUTONOMOUS_OPERATIONS=false", f"AUTONOMOUS_OPERATIONS={str(self.config['features']['autonomous_operations']).lower()}")
            
            with open(env_file, 'w') as f:
                f.write(content)
            
            print("✅ Environment configuration created")
            return True
        except Exception as e:
            print(f"❌ Failed to setup environment: {e}")
            return False
    
    def setup_directories(self) -> bool:
        """Create necessary directories"""
        print("📁 Setting up directories...")
        
        directories = [
            "data",
            "logs",
            "temp",
            "models",
            "cache"
        ]
        
        try:
            for directory in directories:
                dir_path = self.project_root / directory
                dir_path.mkdir(exist_ok=True)
                print(f"✅ Created directory: {directory}")
            
            return True
        except Exception as e:
            print(f"❌ Failed to create directories: {e}")
            return False
    
    def check_ollama(self) -> bool:
        """Check if Ollama is installed and running"""
        print("🤖 Checking Ollama installation...")
        
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                print("✅ Ollama is running")
                return True
        except:
            pass
        
        print("⚠️ Ollama not detected")
        print("📥 To install Ollama:")
        print("   Windows: Download from https://ollama.ai")
        print("   macOS: brew install ollama")
        print("   Linux: curl -fsSL https://ollama.ai/install.sh | sh")
        
        return False
    
    def pull_ollama_model(self) -> bool:
        """Pull the required Ollama model"""
        print("📥 Pulling Ollama model...")
        
        model = self.config['ai_providers']['ollama']['model']
        
        try:
            subprocess.run(["ollama", "pull", model], check=True)
            print(f"✅ Model {model} pulled successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to pull model: {e}")
            return False
        except FileNotFoundError:
            print("❌ Ollama not found in PATH")
            return False
    
    def run_tests(self) -> bool:
        """Run system tests"""
        print("🧪 Running tests...")
        
        try:
            # Determine python path based on OS
            if os.name == 'nt':  # Windows
                python_path = self.project_root / "venv" / "Scripts" / "python.exe"
            else:  # Unix/Linux/macOS
                python_path = self.project_root / "venv" / "bin" / "python"
            
            subprocess.run([str(python_path), "test_simple.py"], check=True)
            print("✅ Tests passed")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Tests failed: {e}")
            return False
    
    def optimize_code(self) -> bool:
        """Automatically optimize code"""
        print("🔧 Optimizing code...")
        
        try:
            # Determine python path based on OS
            if os.name == 'nt':  # Windows
                python_path = self.project_root / "venv" / "Scripts" / "python.exe"
            else:  # Unix/Linux/macOS
                python_path = self.project_root / "venv" / "bin" / "python"
            
            # Install optimization tools
            subprocess.run([str(python_path), "-m", "pip", "install", "black", "isort", "flake8"], check=True)
            
            # Format code
            subprocess.run([str(python_path), "-m", "black", "Core/"], check=True)
            subprocess.run([str(python_path), "-m", "isort", "Core/"], check=True)
            
            print("✅ Code optimized")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Code optimization failed: {e}")
            return False
    
    def create_startup_script(self) -> bool:
        """Create automated startup script"""
        print("🚀 Creating startup script...")
        
        if os.name == 'nt':  # Windows
            script_content = f'''@echo off
echo Starting Atulya Tantra AGI...
cd /d "{self.project_root}"
call venv\\Scripts\\activate.bat
python Core\\api\\main.py
pause
'''
            script_path = self.project_root / "start.bat"
        else:  # Unix/Linux/macOS
            script_content = f'''#!/bin/bash
echo "Starting Atulya Tantra AGI..."
cd "{self.project_root}"
source venv/bin/activate
python Core/api/main.py
'''
            script_path = self.project_root / "start.sh"
        
        try:
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            if os.name != 'nt':  # Make executable on Unix systems
                os.chmod(script_path, 0o755)
            
            print(f"✅ Startup script created: {script_path}")
            return True
        except Exception as e:
            print(f"❌ Failed to create startup script: {e}")
            return False
    
    def run_full_setup(self) -> bool:
        """Run complete automated setup"""
        print("🚀 Starting automated setup for Atulya Tantra AGI...")
        print("=" * 60)
        
        steps = [
            ("Check Python Version", self.check_python_version),
            ("Setup Virtual Environment", self.setup_virtual_environment),
            ("Install Dependencies", self.install_dependencies),
            ("Setup Environment File", self.setup_environment_file),
            ("Setup Directories", self.setup_directories),
            ("Check Ollama", self.check_ollama),
            ("Pull Ollama Model", self.pull_ollama_model),
            ("Optimize Code", self.optimize_code),
            ("Run Tests", self.run_tests),
            ("Create Startup Script", self.create_startup_script),
            ("Save Configuration", lambda: self._save_config() or True)
        ]
        
        success_count = 0
        total_steps = len(steps)
        
        for step_name, step_function in steps:
            print(f"\n📋 {step_name}...")
            try:
                if step_function():
                    success_count += 1
                else:
                    print(f"⚠️ {step_name} completed with warnings")
            except Exception as e:
                print(f"❌ {step_name} failed: {e}")
        
        print("\n" + "=" * 60)
        print(f"🎉 Setup completed: {success_count}/{total_steps} steps successful")
        
        if success_count == total_steps:
            print("✅ All steps completed successfully!")
            print("\n🚀 To start the application:")
            if os.name == 'nt':
                print("   Double-click start.bat or run: python Core/api/main.py")
            else:
                print("   Run: ./start.sh or python Core/api/main.py")
        else:
            print("⚠️ Some steps had issues, but the system should still work")
        
        return success_count == total_steps

def main():
    """Main entry point"""
    setup = AutomatedSetup()
    success = setup.run_full_setup()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
