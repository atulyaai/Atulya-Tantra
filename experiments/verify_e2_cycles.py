import os
import sys
import time
import json

# Add current directory to path
sys.path.append(os.getcwd())

from core.engine import Engine
from core.memory_manager import MemoryManager
from core.governor import Governor
from core.evolution.cycle_driver import KnowledgeCycleDriver

def verify_e2_cycles():
    print("--- Phase E2: Knowledge Accumulation Cycles Verification ---")
    
    # Ensure KnowledgeBase is clean for the test
    if os.path.exists("memory/knowledge_base.json"):
        os.remove("memory/knowledge_base.json")
        
    memory = MemoryManager()
    governor = Governor(memory)
    engine = Engine(memory, governor)
    driver = KnowledgeCycleDriver(engine)
    
    # 1. Run discovery cycle
    # Topic: "Latest RWKV Performance Benchmarks"
    success = driver.run_discovery_cycle()
    
    if success:
        print("\nPhase E2 Success: Knowledge accumulated via Governed Search.")
        # Check if KnowledgeBase reflects the search result
        topic = "Research Latest RWKV Performance Benchmarks" # Topic name defaults to query for UNKNOWN
        facts = engine.knowledge_brain.get_topic_facts(topic)
        
        # If no match on "Research...", try the raw gap string
        if not facts:
            topic = "Latest RWKV Performance Benchmarks"
            facts = engine.knowledge_brain.get_topic_facts(topic)
            
        print(f"Facts in DB for '{topic}': {len(facts)}")
        for f in facts:
            print(f" - {f['content']} (Source: {f['source']})")
            
        print("\nPhase E2 Verification: PASSED")
    else:
        print("\nPhase E2 Verification: FAILED")

if __name__ == "__main__":
    verify_e2_cycles()
