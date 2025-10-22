#!/usr/bin/env python3
"""
Test script for Atulya Tantra AGI LLM providers
Tests multi-provider LLM integration with fallback
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Core.brain import get_llm_router, generate_response, get_provider_status
from Core.config.logging import get_logger

logger = get_logger(__name__)


async def test_provider_status():
    """Test provider availability"""
    print("🔍 Checking provider status...")
    
    try:
        status = await get_provider_status()
        
        print(f"Primary provider: {status['primary_provider']}")
        print("\nProvider details:")
        
        for provider_name, details in status['providers'].items():
            status_icon = "✅" if details['available'] else "❌"
            print(f"  {status_icon} {provider_name}: {details['model']}")
            
            if details['available']:
                print(f"    Config: {details['config']}")
        
        return status
        
    except Exception as e:
        logger.error(f"Error checking provider status: {e}")
        return None


async def test_simple_generation():
    """Test simple text generation"""
    print("\n🤖 Testing simple text generation...")
    
    test_prompt = "Hello! Please respond with a brief greeting and tell me what AI model you are."
    
    try:
        response = await generate_response(
            prompt=test_prompt,
            max_tokens=100,
            temperature=0.7
        )
        
        print(f"✅ Response: {response}")
        return True
        
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        print(f"❌ Generation failed: {e}")
        return False


async def test_streaming_generation():
    """Test streaming text generation"""
    print("\n🌊 Testing streaming generation...")
    
    test_prompt = "Write a short poem about artificial intelligence."
    
    try:
        print("Streaming response:")
        print("-" * 50)
        
        stream = await generate_response(
            prompt=test_prompt,
            max_tokens=200,
            temperature=0.8,
            stream=True
        )
        
        full_response = ""
        async for chunk in stream:
            print(chunk, end="", flush=True)
            full_response += chunk
        
        print("\n" + "-" * 50)
        print(f"✅ Streaming completed. Total length: {len(full_response)} characters")
        return True
        
    except Exception as e:
        logger.error(f"Error in streaming generation: {e}")
        print(f"❌ Streaming failed: {e}")
        return False


async def test_conversation():
    """Test conversation with context"""
    print("\n💬 Testing conversation with context...")
    
    messages = [
        {"role": "system", "content": "You are a helpful AI assistant. Keep responses concise."},
        {"role": "user", "content": "What is the capital of France?"},
        {"role": "assistant", "content": "The capital of France is Paris."},
        {"role": "user", "content": "What is the population of that city?"}
    ]
    
    try:
        # Convert messages to a single prompt for testing
        prompt = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                prompt += f"System: {content}\n\n"
            elif role == "user":
                prompt += f"Human: {content}\n"
            elif role == "assistant":
                prompt += f"Assistant: {content}\n"
        
        prompt += "Assistant:"
        
        response = await generate_response(
            prompt=prompt,
            max_tokens=150,
            temperature=0.7
        )
        
        print(f"✅ Conversation response: {response}")
        return True
        
    except Exception as e:
        logger.error(f"Error in conversation test: {e}")
        print(f"❌ Conversation failed: {e}")
        return False


async def main():
    """Run all tests"""
    print("🚀 Atulya Tantra AGI - LLM Provider Test Suite")
    print("=" * 60)
    
    # Test 1: Provider status
    status = await test_provider_status()
    if not status:
        print("❌ Provider status check failed. Exiting.")
        return
    
    # Check if any providers are available
    available_providers = [name for name, details in status['providers'].items() if details['available']]
    if not available_providers:
        print("❌ No providers are available. Please check your configuration.")
        return
    
    print(f"\n✅ Found {len(available_providers)} available provider(s): {', '.join(available_providers)}")
    
    # Test 2: Simple generation
    success1 = await test_simple_generation()
    
    # Test 3: Streaming generation
    success2 = await test_streaming_generation()
    
    # Test 4: Conversation
    success3 = await test_conversation()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    print(f"  Provider Status: ✅")
    print(f"  Simple Generation: {'✅' if success1 else '❌'}")
    print(f"  Streaming Generation: {'✅' if success2 else '❌'}")
    print(f"  Conversation: {'✅' if success3 else '❌'}")
    
    total_tests = 4
    passed_tests = 1 + sum([success1, success2, success3])
    
    print(f"\n🎯 Overall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! LLM provider system is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the logs for details.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user.")
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        print(f"❌ Test suite failed: {e}")
