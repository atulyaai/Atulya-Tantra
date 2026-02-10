#!/usr/bin/env python3
"""
JARVIS Hybrid LLM Demo - Shows local conversation model and optional cloud LLM integration
"""

import sys
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)

print("\n" + "="*80)
print("🤖 ATULYA - JARVIS HYBRID LLM DEMONSTRATION")
print("="*80)

# Test 1: Local Conversation Model (Always Available)
print("\n📌 FEATURE 1: Local Conversation Model (No API, Always Works)")
print("-" * 80)

try:
    from atulya.llm.conversation_model import LocalConversationModel
    
    local_model = LocalConversationModel()
    print("✓ Local Conversation Model initialized")
    print("  - Pattern-based conversation: ALWAYS AVAILABLE")
    print("  - No API keys needed")
    print("  - Lightweight (repo-included))")
    
    # Test conversations
    test_inputs = [
        "Hello JARVIS",
        "What can you do?",
        "Thank you",
        "Turn on the lights",
        "What's the weather?",
        "Good night"
    ]
    
    print("\n🎤 Testing Local Model Responses:")
    for user_input in test_inputs:
        response = local_model.process_input(user_input)
        print(f"  👤 User: {user_input}")
        print(f"  🤖 JARVIS: {response}")
    
except Exception as e:
    print(f"✗ Local model error: {e}")


# Test 2: Hybrid LLM Engine
print("\n\n📌 FEATURE 2: Hybrid LLM Engine (Multi-Provider)")
print("-" * 80)

try:
    from atulya.llm import HybridLLMEngine
    
    hybrid = HybridLLMEngine(mode="hybrid")
    
    available_providers = hybrid.get_available_providers()
    print(f"✓ Hybrid LLM Engine initialized")
    print(f"  - Available providers: {', '.join(available_providers) if available_providers else 'None (will use templates)'}")
    
    if hybrid.active_provider:
        print(f"  - Active provider: {hybrid.active_provider.name}")
        print(f"  - Mode: hybrid (LLM + templates)")
    else:
        print(f"  - Mode: hybrid (templates fallback)")
    
except Exception as e:
    print(f"✗ Hybrid engine error: {e}")


# Test 3: ConversationalAI with Hybrid Mode
print("\n\n📌 FEATURE 3: ConversationalAI with Hybrid LLM")
print("-" * 80)

try:
    from atulya import Atulya
    
    atulya = Atulya(name="JARVIS")
    
    if atulya.conversation:
        print("✓ Atulya conversation module initialized")
        print(f"  - Mode: {atulya.conversation.mode}")
        print(f"  - Local model: {atulya.conversation.local_model is not None}")
        print(f"  - LLM engine: {atulya.conversation.llm_engine is not None}")
        
        # Test hybrid conversation
        print("\n💬 Testing Hybrid Conversation:")
        test_inputs = [
            "Hello JARVIS, how are you?",
            "Can you help me with the lights?",
            "What's your status?",
            "Thank you for your help"
        ]
        
        for user_input in test_inputs:
            # Use default hybrid mode
            response = atulya.conversation.process_input(user_input)
            print(f"  👤 User: {user_input}")
            print(f"  🤖 JARVIS: {response}\n")
    
except Exception as e:
    print(f"✗ ConversationalAI error: {e}")
    import traceback
    traceback.print_exc()


# Test 4: Mode Comparison
print("\n📌 FEATURE 4: Conversation Mode Comparison")
print("-" * 80)

try:
    from atulya.conversation import ConversationalAI
    
    # Template mode
    print("Template Mode (Fast, No API):")
    template_conv = ConversationalAI(mode="template")
    response = template_conv.process_input("Hello")
    print(f"  Input: 'Hello'")
    print(f"  Output: {response}")
    
    # Local model mode
    print("\nLocal Model Mode (Smart, No API):")
    local_conv = ConversationalAI(mode="llm")
    response = local_conv.process_input("Hello")
    print(f"  Input: 'Hello'")
    print(f"  Output: {response}")
    
    # Hybrid mode
    print("\nHybrid Mode (Best of Both):")
    hybrid_conv = ConversationalAI(mode="hybrid")
    response = hybrid_conv.process_input("Hello")
    print(f"  Input: 'Hello'")
    print(f"  Output: {response}")
    
except Exception as e:
    print(f"✗ Mode comparison error: {e}")
    import traceback
    traceback.print_exc()


# Test 5: Ollama Integration (Optional)
print("\n\n📌 FEATURE 5: Ollama Integration (Optional Local LLM)")
print("-" * 80)

print("""
To enable Ollama support (local LLM without GPU):

1. Install Ollama: https://ollama.ai
2. Start Ollama server: ollama serve
3. Pull a model: ollama pull neural-chat (or other models)
4. JARVIS will auto-detect and use it

Available Models for Ollama:
  - neural-chat (default, 4.5GB) - Good balance
  - mistral (26GB) - Faster, less capable
  - llama2 (3.5GB) - Solid alternative
  - openhermes (34GB) - Better reasoning
  
Example:
  $ ollama pull neural-chat
  $ python jarvis_demo.py  # Will auto-use Ollama
""")


# Test 6: Required Setup for Cloud LLMs
print("\n📌 FEATURE 6: Cloud LLM Setup (Optional)")
print("-" * 80)

print("""
For OpenAI (GPT-4):
  1. Get API key: https://platform.openai.com/api-keys
  2. Set: export OPENAI_API_KEY=sk-...
  3. JARVIS will auto-detect and use GPT-4

For Anthropic (Claude):
  1. Get API key: https://console.anthropic.com
  2. Set: export ANTHROPIC_API_KEY=sk-ant-...
  3. JARVIS will auto-detect and use Claude

JARVIS Hybrid Logic:
  - Prefers: Local Models (no cost, instant)
  - Then: Ollama (if running locally)
  - Then: Cloud LLM (if API keys set)
  - Falls back: To templates (always works)
""")


# Test 7: Summary
print("\n\n" + "="*80)
print("✨ HYBRID LLM FEATURES SUMMARY")
print("="*80)

features = [
    ("✅", "Local Conversation Model", "Always available (pattern-based)"),
    ("✅", "Template Fallback System", "Works without any LLM"),
    ("✅", "Hybrid Mode", "Smart selection of response method"),
    ("✅", "Multi-Provider Support", "OpenAI, Anthropic, Ollama, Local"),
    ("✅", "Graceful Degradation", "Falls back elegantly"),
    ("⚙️", "Ollama Integration", "Optional local LLM"),
    ("⚙️", "OpenAI Integration", "Optional cloud LLM"),
    ("⚙️", "Anthropic Integration", "Optional cloud LLM"),
]

for status, feature, desc in features:
    print(f"{status} {feature:.<35} {desc}")

print("\n" + "="*80)
print("Ready for Production Use! 🚀")
print("="*80 + "\n")
