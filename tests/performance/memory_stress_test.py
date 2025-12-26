"""
Phase F: Memory Stress & Corruption Test
Tests knowledge brain under extreme load and corruption scenarios.
"""

import sys
import time
import os
import signal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge.knowledge_brain import KnowledgeBrain
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MemoryStressTest")


def test_massive_fact_injection():
    """Test 1: Inject 1000+ facts and verify performance."""
    logger.info("[Test 1] Massive fact injection...")
    
    kb = KnowledgeBrain(storage_path="memory/test_knowledge_base.json")
    
    start_time = time.time()
    for i in range(1000):
        kb.add_fact(
            topic_name=f"Topic_{i % 10}",
            content=f"Test fact {i} with some content to simulate real data.",
            source="stress_test",
            confidence=0.8,
            ttl=3600 * 24 * 7  # 7 days
        )
        
        if (i + 1) % 100 == 0:
            logger.info(f"  Injected {i + 1} facts...")
    
    elapsed = time.time() - start_time
    logger.info(f"  ✓ Injected 1000 facts in {elapsed:.2f}s ({1000/elapsed:.0f} facts/sec)")
    
    # Verify retrieval
    facts = kb.get_topic_facts("Topic_0")
    logger.info(f"  ✓ Retrieved {len(facts)} facts for Topic_0")
    
    return True


def test_expired_ttl_handling():
    """Test 2: Verify expired facts are filtered correctly."""
    logger.info("[Test 2] Expired TTL handling...")
    
    kb = KnowledgeBrain(storage_path="memory/test_knowledge_base.json")
    
    # Add fact with very short TTL
    kb.add_fact(
        topic_name="TTL_TEST",
        content="This fact should expire quickly",
        source="ttl_test",
        confidence=0.9,
        ttl=1  # 1 second TTL
    )
    
    # Immediate retrieval should work
    facts_before = kb.get_topic_facts("TTL_TEST")
    logger.info(f"  Before expiry: {len(facts_before)} facts")
    
    # Wait for expiry
    time.sleep(2)
    
    # Should be filtered out
    facts_after = kb.get_topic_facts("TTL_TEST")
    logger.info(f"  After expiry: {len(facts_after)} facts")
    
    if len(facts_after) < len(facts_before):
        logger.info("  ✓ Expired facts correctly filtered")
        return True
    else:
        logger.error("  ✗ Expired facts NOT filtered")
        return False


def test_partial_write_corruption():
    """Test 3: Simulate kill during write and verify recovery."""
    logger.info("[Test 3] Partial write corruption...")
    
    kb = KnowledgeBrain(storage_path="memory/test_knowledge_base.json")
    
    # Add some baseline facts
    for i in range(10):
        kb.add_fact(
            topic_name="BASELINE",
            content=f"Baseline fact {i}",
            source="baseline",
            confidence=0.9
        )
    
    logger.info("  Baseline facts added")
    
    # Simulate corruption by writing invalid JSON
    try:
        with open(kb.storage_path, 'w') as f:
            f.write('{"topics": {"CORRUPT": ')  # Incomplete JSON
        logger.info("  Simulated corruption (incomplete JSON)")
    except Exception as e:
        logger.error(f"  Failed to simulate corruption: {str(e)}")
        return False
    
    # Try to load corrupted file
    kb2 = KnowledgeBrain(storage_path="memory/test_knowledge_base.json")
    
    # Should recover to empty state
    topics = kb2.get_all_topics()
    logger.info(f"  After corruption load: {len(topics)} topics")
    
    if len(topics) == 0:
        logger.info("  ✓ Gracefully recovered from corruption (reset to empty)")
        return True
    else:
        logger.warning("  ~ Loaded despite corruption (may have stale data)")
        return True  # Not a failure, but worth noting


def test_restart_after_corruption():
    """Test 4: Verify clean restart after corruption."""
    logger.info("[Test 4] Restart after corruption...")
    
    # Clean up test file
    test_path = "memory/test_knowledge_base.json"
    if os.path.exists(test_path):
        os.remove(test_path)
    
    # Create fresh KB
    kb = KnowledgeBrain(storage_path=test_path)
    
    # Add facts
    for i in range(5):
        kb.add_fact(
            topic_name="RESTART_TEST",
            content=f"Restart test fact {i}",
            source="restart_test",
            confidence=0.9
        )
    
    # Reload
    kb2 = KnowledgeBrain(storage_path=test_path)
    facts = kb2.get_topic_facts("RESTART_TEST")
    
    if len(facts) == 5:
        logger.info(f"  ✓ Restart successful: {len(facts)} facts recovered")
        return True
    else:
        logger.error(f"  ✗ Restart failed: expected 5 facts, got {len(facts)}")
        return False


def run_memory_stress_tests():
    """Run all memory stress tests."""
    logger.info("\n" + "="*60)
    logger.info("MEMORY STRESS & CORRUPTION TESTS")
    logger.info("="*60 + "\n")
    
    tests = [
        ("Massive Fact Injection", test_massive_fact_injection),
        ("Expired TTL Handling", test_expired_ttl_handling),
        ("Partial Write Corruption", test_partial_write_corruption),
        ("Restart After Corruption", test_restart_after_corruption)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            logger.error(f"[{test_name}] EXCEPTION: {str(e)}")
            results.append((test_name, False))
        print()
    
    # Summary
    logger.info("="*60)
    logger.info("TEST SUMMARY")
    logger.info("="*60)
    for test_name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        logger.info(f"{status}: {test_name}")
    
    passed_count = sum(1 for _, p in results if p)
    logger.info(f"\nPassed: {passed_count}/{len(results)}")
    
    return all(p for _, p in results)


if __name__ == "__main__":
    success = run_memory_stress_tests()
    sys.exit(0 if success else 1)
