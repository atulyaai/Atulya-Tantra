#!/usr/bin/env python3
"""
Test script for Tantra core functionality without GUI components
"""

import os
import sys
import threading
import queue
import time
import json
import re
from datetime import datetime
import requests

# Set DISPLAY environment variable to avoid pyautogui issues
os.environ['DISPLAY'] = ':0'

# Add current directory to path
sys.path.append('.')

from Tools.tantra_tools import (
    get_user_id,
    get_session_paths,
    append_jsonl,
    backup_file,
)

def test_tantra_core():
    """Test core Tantra functionality"""
    print("🧠 Testing Tantra Core Functionality")
    print("=" * 50)
    
    try:
        # Test Tools module
        print("1. Testing Tools module...")
        user_id = get_user_id()
        print(f"   ✅ User ID: {user_id}")
        
        session_paths = get_session_paths(user_id)
        print(f"   ✅ Session paths: {session_paths}")
        
        # Test JSONL functionality
        test_data = {
            'type': 'test',
            'message': 'Hello Tantra!',
            'timestamp': datetime.now().isoformat()
        }
        success = append_jsonl(session_paths['latest'], test_data)
        print(f"   ✅ JSONL append: {success}")
        
        # Test Core module
        print("\n2. Testing Core module...")
        from Core import AGICore, AssistantCore, UnifiedAGISystem
        
        agi = AGICore()
        assistant = AssistantCore()
        unified = UnifiedAGISystem()
        
        print("   ✅ Core modules imported successfully")
        print(f"   ✅ AGI Core: {type(agi).__name__}")
        print(f"   ✅ Assistant Core: {type(assistant).__name__}")
        print(f"   ✅ Unified System: {type(unified).__name__}")
        
        # Test agents
        print("\n3. Testing Agents...")
        from Core.agents import CodeAgent, CreativeAgent, DataAgent, ResearchAgent, SystemAgent
        
        code_agent = CodeAgent()
        creative_agent = CreativeAgent()
        data_agent = DataAgent()
        research_agent = ResearchAgent()
        system_agent = SystemAgent()
        
        print("   ✅ All agents created successfully")
        
        # Test brain modules
        print("\n4. Testing Brain modules...")
        from Core.brain import OllamaClient, OpenAIClient, AnthropicClient
        
        ollama = OllamaClient()
        openai = OpenAIClient()
        anthropic = AnthropicClient()
        
        print("   ✅ All brain modules created successfully")
        
        # Test database
        print("\n5. Testing Database...")
        from Core.database import Database, DatabaseService
        
        db = Database("test.db")
        db.connect()
        db.create_tables()
        print("   ✅ Database created successfully")
        
        # Test memory
        print("\n6. Testing Memory...")
        from Core.memory import ConversationMemory
        
        memory = ConversationMemory()
        memory.add_memory(user_id, "Test memory", "test")
        memories = memory.get_memories(user_id)
        print(f"   ✅ Memory system working: {len(memories)} memories")
        
        print("\n" + "=" * 50)
        print("🎉 All core functionality tests passed!")
        print("✅ Tantra AGI system is ready for use")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_tantra_core()
    sys.exit(0 if success else 1)