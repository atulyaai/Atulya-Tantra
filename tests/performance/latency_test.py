"""
Phase F: Latency Spike Tests
Tests system behavior under rapid-fire and multimodal load.

Watch for: Watchdog behavior, queue growth, confidence collapse.
"""

import sys
import time
import threading
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.WARNING)  # Reduce noise
logger = logging.getLogger("LatencyTest")


def test_rapid_fire_text():
    """Test rapid-fire text requests."""
    logger.info("[Test 1] Rapid-fire text (10 req/sec for 10s)...")
    
    from core.memory_manager import MemoryManager
    from core.governor import Governor
    from core.engine import Engine
    
    memory = MemoryManager()
    governor = Governor(memory)
    engine = Engine(memory, governor)
    
    requests = [f"What is {i}+{i}?" for i in range(100)]
    
    start_time = time.time()
    completed = 0
    errors = 0
    latencies = []
    
    for req in requests:
        req_start = time.time()
        try:
            result = engine.run_task(req)
            latency = time.time() - req_start
            latencies.append(latency)
            completed += 1
        except Exception as e:
            errors += 1
            logger.warning(f"  Request failed: {str(e)[:50]}")
        
        # Throttle to ~10 req/sec
        time.sleep(0.1)
    
    total_time = time.time() - start_time
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    
    logger.info(f"  Completed: {completed}/{len(requests)}")
    logger.info(f"  Errors: {errors}")
    logger.info(f"  Avg latency: {avg_latency:.2f}s")
    logger.info(f"  Total time: {total_time:.1f}s")
    
    # Should handle gracefully
    if completed > len(requests) * 0.8:  # 80% success rate
        logger.info(f"  [PASS] Handled rapid-fire requests")
        return True
    else:
        logger.error(f"  [FAIL] Too many failures under load")
        return False


def test_concurrent_requests():
    """Test concurrent requests (threading)."""
    logger.info("[Test 2] Concurrent requests (10 threads)...")
    
    from core.memory_manager import MemoryManager
    from core.governor import Governor
    from core.engine import Engine
    
    memory = MemoryManager()
    governor = Governor(memory)
    engine = Engine(memory, governor)
    
    results = []
    errors = []
    
    def worker(task_id):
        try:
            result = engine.run_task(f"Task {task_id}")
            results.append((task_id, result))
        except Exception as e:
            errors.append((task_id, str(e)))
    
    threads = []
    for i in range(10):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    
    # Wait for all
    for t in threads:
        t.join(timeout=30)
    
    logger.info(f"  Completed: {len(results)}/10")
    logger.info(f"  Errors: {len(errors)}")
    
    if len(results) >= 8:  # 80% success
        logger.info(f"  [PASS] Handled concurrent requests")
        return True
    else:
        logger.error(f"  [FAIL] Too many concurrent failures")
        return False


def test_confidence_under_load():
    """
    SILENT KILLER #2: Test for confidence collapse under load.
    Watch for clustering around 0.4-0.6.
    """
    logger.info("[Test 3] Confidence distribution under load...")
    
    from core.knowledge.llm_interface import CoreLMInterface
    
    lm = CoreLMInterface()
    
    # Rapid queries
    queries = [
        "What is AI?",
        "Explain machine learning",
        "What is deep learning?",
        "Define neural networks",
        "What is RWKV?",
    ] * 10  # 50 queries
    
    confidences = []
    
    for query in queries:
        result = lm.query(query, [])
        uncertainty = result['metadata']['perceived_uncertainty']
        confidence = 1.0 - uncertainty
        confidences.append(confidence)
    
    # Analyze distribution
    avg_conf = sum(confidences) / len(confidences)
    clustered = sum(1 for c in confidences if 0.4 <= c <= 0.6)
    cluster_ratio = clustered / len(confidences)
    
    logger.info(f"  Avg confidence: {avg_conf:.2f}")
    logger.info(f"  Clustered (0.4-0.6): {cluster_ratio:.1%}")
    
    # CRITICAL: If >50% cluster in middle, confidence is collapsing
    if cluster_ratio > 0.5:
        logger.error(f"  [FAIL] CONFIDENCE COLLAPSE - {cluster_ratio:.1%} clustered")
        return False
    else:
        logger.info(f"  [PASS] Confidence distribution healthy")
        return True


def run_latency_tests():
    """Run all latency spike tests."""
    logger.info("\n" + "="*60)
    logger.info("LATENCY SPIKE TESTS")
    logger.info("="*60 + "\n")
    
    tests = [
        ("Rapid-Fire Text", test_rapid_fire_text),
        ("Concurrent Requests", test_concurrent_requests),
        ("Confidence Under Load (SK-2)", test_confidence_under_load),
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
    success = run_latency_tests()
    sys.exit(0 if success else 1)
