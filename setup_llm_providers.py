#!/usr/bin/env python3
"""
Setup script for Tantra LLM providers
Helps users configure their preferred LLM provider
"""

import os
import json
from pathlib import Path

def create_env_file():
    """Create .env file with LLM provider configuration"""
    env_content = """# Tantra AI Assistant - Environment Configuration
# Choose your preferred LLM provider and configure accordingly

# Option 1: Ollama (Local - Recommended for privacy)
# Install Ollama from https://ollama.ai/
# Then run: ollama pull gemma2:2b
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma2:2b

# Option 2: OpenAI (Cloud - Requires API key)
# Get your API key from https://platform.openai.com/api-keys
# OPENAI_API_KEY=your_openai_api_key_here
# OPENAI_MODEL=gpt-3.5-turbo

# Option 3: Anthropic (Cloud - Requires API key)
# Get your API key from https://console.anthropic.com/
# ANTHROPIC_API_KEY=your_anthropic_api_key_here
# ANTHROPIC_MODEL=claude-3-sonnet-20240229

# Priority order (first available will be used):
# 1. Ollama (if running locally)
# 2. OpenAI (if API key is provided)
# 3. Anthropic (if API key is provided)
"""
    
    env_file = Path(".env")
    if not env_file.exists():
        with open(env_file, "w") as f:
            f.write(env_content)
        print("✅ Created .env file with LLM provider configuration")
    else:
        print("ℹ️  .env file already exists")

def check_ollama():
    """Check if Ollama is available"""
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print("✅ Ollama is running and available")
            return True
        else:
            print("❌ Ollama is not running")
            return False
    except:
        print("❌ Ollama is not available")
        return False

def check_api_keys():
    """Check for API keys in environment"""
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    
    if openai_key:
        print("✅ OpenAI API key found")
    else:
        print("❌ OpenAI API key not found")
    
    if anthropic_key:
        print("✅ Anthropic API key found")
    else:
        print("❌ Anthropic API key not found")

def install_ollama_instructions():
    """Print instructions for installing Ollama"""
    print("\n📋 To install Ollama (Recommended):")
    print("1. Visit https://ollama.ai/")
    print("2. Download and install Ollama for your system")
    print("3. Run: ollama pull gemma2:2b")
    print("4. Start Ollama service")
    print("5. Run tantra.py again")

def main():
    print("🚀 Tantra LLM Provider Setup")
    print("=" * 40)
    
    # Create .env file
    create_env_file()
    
    # Check current status
    print("\n🔍 Checking current status...")
    ollama_available = check_ollama()
    check_api_keys()
    
    # Provide setup instructions
    if not ollama_available:
        install_ollama_instructions()
    
    print("\n📝 Next steps:")
    print("1. Choose your preferred LLM provider")
    print("2. Configure the .env file with your settings")
    print("3. Run: python3 tantra.py")
    
    print("\n✅ Setup completed!")

if __name__ == "__main__":
    main()