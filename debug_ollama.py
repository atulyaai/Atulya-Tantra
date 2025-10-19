#!/usr/bin/env python3
"""
Debug Ollama integration
"""

import ollama
import os

print("=== Debugging Ollama Integration ===")

# Test 1: Check if ollama is available
try:
    models_response = ollama.list()
    print(f"✅ Ollama.list() works: {type(models_response)}")
    
    available_models = [model.model for model in models_response.models]
    print(f"✅ Available models: {available_models}")
    
    # Test 2: Try to use mistral
    if 'mistral:latest' in available_models:
        print("✅ mistral:latest found in models")
        
        # Test 3: Try chat
        try:
            response = ollama.chat(
                model='mistral:latest',
                messages=[{'role': 'user', 'content': 'Hello! How are you?'}],
                options={
                    'temperature': 0.7,
                    'top_p': 0.9,
                    'max_tokens': 1000
                }
            )
            print(f"✅ Chat response: {response['message']['content'][:100]}...")
        except Exception as e:
            print(f"❌ Chat failed: {e}")
    else:
        print("❌ mistral:latest not found")
        
except Exception as e:
    print(f"❌ Ollama.list() failed: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Testing the exact server code ===")

# Test the exact server initialization code
openai_client = None
anthropic_client = None
ollama_available = False
available_models = []

# Check Ollama availability and get available models
try:
    models_response = ollama.list()
    available_models = [model.model for model in models_response.models]
    ollama_available = True
    print(f"✅ Server code works: ollama_available={ollama_available}, models={available_models}")
except Exception as e:
    print(f"❌ Server code failed: {e}")

# Test the model selection logic
if ollama_available and available_models:
    model_priority = ['mistral:latest', 'qwen2.5-coder:7b', 'gemma2:2b']
    selected_model = None
    
    for model in model_priority:
        if model in available_models:
            selected_model = model
            break
    
    if not selected_model and available_models:
        selected_model = available_models[0]
    
    print(f"✅ Selected model: {selected_model}")
    
    if selected_model:
        try:
            response = ollama.chat(
                model=selected_model,
                messages=[{'role': 'user', 'content': 'Test message'}],
                options={
                    'temperature': 0.7,
                    'top_p': 0.9,
                    'max_tokens': 1000
                }
            )
            print(f"✅ Full integration works: {response['message']['content'][:50]}...")
        except Exception as e:
            print(f"❌ Full integration failed: {e}")
else:
    print("❌ Ollama not available or no models")
