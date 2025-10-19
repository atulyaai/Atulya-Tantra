#!/usr/bin/env python3
"""
Test Ollama connection directly
"""

import ollama
import json

try:
    print("Testing Ollama connection...")
    
    # Test list models
    models_response = ollama.list()
    print(f"Models response type: {type(models_response)}")
    print(f"Models response: {models_response}")
    
    available_models = [model['name'] for model in models_response['models']]
    print(f"Available models: {available_models}")
    
    # Test chat with mistral
    if 'mistral:latest' in available_models:
        print("\nTesting chat with mistral:latest...")
        response = ollama.chat(
            model='mistral:latest',
            messages=[{'role': 'user', 'content': 'Hello! How are you?'}],
            options={
                'temperature': 0.7,
                'top_p': 0.9,
                'max_tokens': 1000
            }
        )
        print(f"Response: {response['message']['content']}")
    else:
        print("mistral:latest not found in available models")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
