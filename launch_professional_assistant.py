#!/usr/bin/env python3
"""
Professional AI Assistant Launcher
Simple launcher script for the professional assistant system
"""

import sys
import os
import subprocess
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = [
        'requests',
        'pyttsx3',
        'SpeechRecognition'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n📦 Install missing packages with:")
        print("   pip install -r requirements_professional.txt")
        return False
    
    return True

def check_ollama():
    """Check if Ollama is running"""
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print("✅ Ollama is running")
            return True
    except:
        pass
    
    print("⚠️  Ollama not detected. The assistant will work with limited functionality.")
    print("   To install Ollama: https://ollama.ai/")
    return False

def main():
    """Main launcher function"""
    print("🚀 Professional AI Assistant Launcher")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check Ollama
    check_ollama()
    
    # Launch the assistant
    try:
        print("\n🎯 Starting Professional AI Assistant...")
        from professional_assistant import main as assistant_main
        assistant_main()
    except ImportError as e:
        print(f"❌ Error importing assistant: {e}")
        print("   Make sure you're in the correct directory")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting assistant: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
