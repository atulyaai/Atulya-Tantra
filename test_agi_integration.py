#!/usr/bin/env python3
"""
Test script for Tantra AGI integration
Tests the Core AGI system and LLM providers
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Core.brain.ollama_client import OllamaClient
from Core.brain.openai_client import OpenAIClient
from Core.brain.anthropic_client import AnthropicClient

def test_llm_providers():
    """Test all LLM providers"""
    print("🧠 Testing LLM Providers...")
    
    # Test Ollama
    print("\n1. Testing Ollama...")
    ollama = OllamaClient()
    if ollama.is_available():
        print("✅ Ollama is available")
        response = ollama.generate_response("Hello, how are you?", max_tokens=50)
        print(f"Response: {response}")
    else:
        print("❌ Ollama is not available")
    
    # Test OpenAI
    print("\n2. Testing OpenAI...")
    openai = OpenAIClient()
    if openai.is_available():
        print("✅ OpenAI is available")
        response = openai.generate_response("Hello, how are you?", max_tokens=50)
        print(f"Response: {response}")
    else:
        print("❌ OpenAI is not available (no API key)")
    
    # Test Anthropic
    print("\n3. Testing Anthropic...")
    anthropic = AnthropicClient()
    if anthropic.is_available():
        print("✅ Anthropic is available")
        response = anthropic.generate_response("Hello, how are you?", max_tokens=50)
        print(f"Response: {response}")
    else:
        print("❌ Anthropic is not available (no API key)")

def test_tantra_brain():
    """Test TantraBrain integration"""
    print("\n🤖 Testing TantraBrain...")
    
    try:
        from tantra import TantraBrain
        
        brain = TantraBrain()
        print(f"Brain initialized: {brain.model_loaded}")
        print(f"LLM Provider: {brain.llm_provider.name if brain.llm_provider else 'None'}")
        
        if brain.model_loaded:
            response = brain.generate_response("What can you do?")
            print(f"Response: {response}")
        else:
            print("❌ Brain not ready")
            
    except Exception as e:
        print(f"❌ Error testing TantraBrain: {e}")

def test_system_commands():
    """Test system command execution"""
    print("\n⚙️ Testing System Commands...")
    
    try:
        from tantra import TantraApp
        
        app = TantraApp()
        
        # Test time command
        time_response = app.get_live_data("what time is it")
        print(f"Time response: {time_response}")
        
        # Test date command
        date_response = app.get_live_data("what date is it")
        print(f"Date response: {date_response}")
        
        # Test weather command
        weather_response = app.get_live_data("what's the weather")
        print(f"Weather response: {weather_response}")
        
    except Exception as e:
        print(f"❌ Error testing system commands: {e}")

if __name__ == "__main__":
    print("🚀 Tantra AGI Integration Test")
    print("=" * 50)
    
    test_llm_providers()
    test_tantra_brain()
    test_system_commands()
    
    print("\n✅ Test completed!")