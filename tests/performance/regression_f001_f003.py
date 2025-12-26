"""
Regression tests for F-001 and F-003 fixes.
Tests silent audio and text input validation.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.sensors.voice_sensor import LocalTranscriber
from core.sensors.text_sensor import TextSensor
from core.sensors.manifest import SensorManifest
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("RegressionTest")


def test_f001_silent_audio():
    """Regression test for F-001: Silent audio handling."""
    logger.info("[F-001] Testing silent audio fix...")
    
    transcriber = LocalTranscriber()
    
    # Test 1: None input
    text, conf = transcriber.transcribe(None)
    assert text == "", f"Expected empty string, got {repr(text)}"
    assert conf == 0.0, f"Expected 0.0 confidence, got {conf}"
    
    # Test 2: Empty list
    text, conf = transcriber.transcribe([])
    assert text == "", f"Expected empty string, got {repr(text)}"
    assert conf == 0.0, f"Expected 0.0 confidence, got {conf}"
    
    # Test 3: Whitespace only
    text, conf = transcriber.transcribe(["   ", "\t", "\n"])
    assert text == "", f"Expected empty string, got {repr(text)}"
    assert conf == 0.0, f"Expected 0.0 confidence, got {conf}"
    
    logger.info("  [PASS] F-001 regression test")
    return True


def test_f003_text_validation():
    """Regression test for F-003: Text input validation."""
    logger.info("[F-003] Testing text validation fix...")
    
    manifest = SensorManifest()
    sensor = TextSensor(manifest)
    
    # Manually inject test cases (bypass stdin)
    test_cases = [
        ("A" * 15000, "Very long text"),  # Should truncate
        ("test\x00null", "Null bytes"),  # Should remove
        ("!@#$%^&*()", "Special chars"),  # Should handle
        ("😀" * 100, "Emoji flood"),  # Should handle
    ]
    
    passed = 0
    for test_input, test_name in test_cases:
        try:
            # Inject directly into queue
            sensor.input_queue.put(test_input)
            result = sensor.capture()
            
            # Should not crash
            logger.info(f"  {test_name}: handled")
            passed += 1
        except Exception as e:
            logger.error(f"  {test_name}: FAILED - {str(e)}")
    
    logger.info(f"  [{'PASS' if passed == len(test_cases) else 'FAIL'}] F-003 regression test ({passed}/{len(test_cases)})")
    return passed == len(test_cases)


if __name__ == "__main__":
    logger.info("\n" + "="*60)
    logger.info("REGRESSION TESTS (F-001, F-003)")
    logger.info("="*60 + "\n")
    
    results = {
        "F-001": test_f001_silent_audio(),
        "F-003": test_f003_text_validation(),
    }
    
    logger.info("\n" + "="*60)
    logger.info("REGRESSION SUMMARY")
    logger.info("="*60)
    for test_id, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        logger.info(f"{status}: {test_id}")
    
    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)
