"""
Phase F: Crash & Recovery Tests
SILENT KILLER #3: Tests restart trust gap and semantic continuity.

Manual execution required - this script provides guidance.
"""

import sys
import logging
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CrashRecoveryTest")


def capture_pre_crash_state():
    """Capture system state before crash."""
    logger.info("[Pre-Crash] Capturing state...")
    
    from core.knowledge.knowledge_brain import KnowledgeBrain
    from core.evolution.auditor import DriftAuditor
    
    kb = KnowledgeBrain()
    auditor = DriftAuditor()
    
    state = {
        "timestamp": time.time(),
        "active_topics": kb.get_all_topics(),
        "total_facts": sum(len(kb.get_topic_facts(t)) for t in kb.get_all_topics()),
        "confidence_history": auditor.metrics.get("confidence_history", []),
        "strategy_stats": auditor.metrics.get("strategy_stats", {}),
    }
    
    # Save to file
    with open("logs/pre_crash_state.json", 'w') as f:
        json.dump(state, f, indent=2)
    
    logger.info(f"  Topics: {len(state['active_topics'])}")
    logger.info(f"  Facts: {state['total_facts']}")
    logger.info(f"  Confidence events: {len(state['confidence_history'])}")
    logger.info(f"  State saved to logs/pre_crash_state.json")
    
    return state


def verify_post_crash_state():
    """Verify system state after crash and restart."""
    logger.info("[Post-Crash] Verifying state...")
    
    # Load pre-crash state
    try:
        with open("logs/pre_crash_state.json", 'r') as f:
            pre_state = json.load(f)
    except FileNotFoundError:
        logger.error("  No pre-crash state found - run capture_pre_crash_state() first")
        return False
    
    from core.knowledge.knowledge_brain import KnowledgeBrain
    from core.evolution.auditor import DriftAuditor
    
    kb = KnowledgeBrain()
    auditor = DriftAuditor()
    
    post_state = {
        "active_topics": kb.get_all_topics(),
        "total_facts": sum(len(kb.get_topic_facts(t)) for t in kb.get_all_topics()),
        "confidence_history": auditor.metrics.get("confidence_history", []),
    }
    
    # Compare
    logger.info("\n" + "="*60)
    logger.info("STATE COMPARISON")
    logger.info("="*60)
    
    checks = []
    
    # Check 1: Topics preserved
    topics_match = set(pre_state["active_topics"]) == set(post_state["active_topics"])
    logger.info(f"Topics: {len(pre_state['active_topics'])} → {len(post_state['active_topics'])}")
    logger.info(f"  Match: {topics_match}")
    checks.append(("Topics preserved", topics_match))
    
    # Check 2: Facts preserved
    facts_match = pre_state["total_facts"] == post_state["total_facts"]
    logger.info(f"Facts: {pre_state['total_facts']} → {post_state['total_facts']}")
    logger.info(f"  Match: {facts_match}")
    checks.append(("Facts preserved", facts_match))
    
    # Check 3: Confidence history preserved
    conf_match = len(pre_state["confidence_history"]) == len(post_state["confidence_history"])
    logger.info(f"Confidence events: {len(pre_state['confidence_history'])} → {len(post_state['confidence_history'])}")
    logger.info(f"  Match: {conf_match}")
    checks.append(("Confidence history preserved", conf_match))
    
    # SILENT KILLER #3: Check for confidence jumps
    if pre_state["confidence_history"] and post_state["confidence_history"]:
        pre_last = pre_state["confidence_history"][-1][1] if pre_state["confidence_history"] else 0
        post_first = post_state["confidence_history"][0][1] if post_state["confidence_history"] else 0
        conf_jump = abs(post_first - pre_last)
        
        logger.info(f"\nConfidence continuity:")
        logger.info(f"  Pre-crash last: {pre_last:.2f}")
        logger.info(f"  Post-crash first: {post_first:.2f}")
        logger.info(f"  Jump: {conf_jump:.2f}")
        
        no_jump = conf_jump < 0.3  # Allow small variation
        checks.append(("No confidence jump (SK-3)", no_jump))
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("RECOVERY CHECKS")
    logger.info("="*60)
    for check_name, passed in checks:
        status = "[PASS]" if passed else "[FAIL]"
        logger.info(f"{status}: {check_name}")
    
    all_passed = all(p for _, p in checks)
    return all_passed


def run_crash_recovery_guide():
    """Provide manual crash recovery test guide."""
    logger.info("\n" + "="*60)
    logger.info("CRASH & RECOVERY TEST GUIDE (MANUAL)")
    logger.info("="*60 + "\n")
    
    logger.info("This test requires manual execution:\n")
    
    logger.info("Step 1: Capture pre-crash state")
    logger.info("  >>> python -c \"from experiments.crash_recovery_test import capture_pre_crash_state; capture_pre_crash_state()\"")
    logger.info("")
    
    logger.info("Step 2: Start presence loop")
    logger.info("  >>> python run_atulya_tantra.py --presence")
    logger.info("")
    
    logger.info("Step 3: Kill process mid-operation (CTRL+C or taskkill)")
    logger.info("  Wait for an active task, then kill")
    logger.info("")
    
    logger.info("Step 4: Restart immediately")
    logger.info("  >>> python run_atulya_tantra.py --presence")
    logger.info("")
    
    logger.info("Step 5: Verify post-crash state")
    logger.info("  >>> python -c \"from experiments.crash_recovery_test import verify_post_crash_state; verify_post_crash_state()\"")
    logger.info("")
    
    logger.info("Expected: All checks pass, no data loss, no confidence jumps")
    logger.info("\n" + "="*60)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "capture":
            capture_pre_crash_state()
        elif sys.argv[1] == "verify":
            success = verify_post_crash_state()
            sys.exit(0 if success else 1)
        else:
            print("Usage: python crash_recovery_test.py [capture|verify]")
    else:
        run_crash_recovery_guide()
