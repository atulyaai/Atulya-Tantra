"""
Phase F: Sensor Abuse Tests
Tests all sensors (voice, vision, text) under hostile/malformed input.

Focus: Crashes, blocking calls, garbage confidence scores.
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SensorAbuseTest")


def test_voice_abuse():
    """Test voice sensor with hostile inputs."""
    logger.info("[Voice Abuse] Testing...")
    
    from core.sensors.voice_sensor import LocalTranscriber
    
    transcriber = LocalTranscriber(confidence_floor=0.5)
    
    test_cases = [
        ("Silent audio", []),  # Empty buffer
        ("Noise", ["[NOISE]", "[STATIC]", "[NOISE]"]),  # Simulated noise
        ("Cutoff", ["Hello this is", "a test that"]),  # Incomplete
        ("Language switch", ["Hello", "Hola", "Bonjour"]),  # Mixed languages
    ]
    
    passed = 0
    for test_name, audio_data in test_cases:
        try:
            text, confidence = transcriber.transcribe(audio_data)
            logger.info(f"  {test_name}: text='{text}', confidence={confidence:.2f}")
            
            # Should not crash
            assert text is not None
            assert 0 <= confidence <= 1.0
            passed += 1
            
        except Exception as e:
            logger.error(f"  {test_name}: FAILED - {str(e)}")
    
    logger.info(f"  Voice: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_vision_abuse():
    """Test vision sensor with hostile inputs."""
    logger.info("[Vision Abuse] Testing...")
    
    # Note: Vision sensor requires real files, so we test error handling
    from core.sensors.vision_sensor import VisionSensor
    from core.sensors.manifest import SensorManifest
    
    manifest = SensorManifest()
    vision = VisionSensor(manifest)
    vision.set_state(active=True)
    
    test_cases = [
        ("Nonexistent file", "nonexistent.jpg"),
        ("Invalid path", "/invalid/path/image.png"),
        ("No file", None),
    ]
    
    passed = 0
    for test_name, image_path in test_cases:
        try:
            result = vision.capture_snapshot(image_path=image_path)
            
            # Should handle gracefully (return None or fallback)
            logger.info(f"  {test_name}: handled gracefully")
            passed += 1
            
        except Exception as e:
            # Should NOT crash
            logger.error(f"  {test_name}: CRASHED - {str(e)}")
    
    logger.info(f"  Vision: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_text_abuse():
    """Test text sensor with malformed input."""
    logger.info("[Text Abuse] Testing...")
    
    from core.sensors.text_sensor import TextSensor
    from core.sensors.manifest import SensorManifest
    
    manifest = SensorManifest()
    text_sensor = TextSensor(manifest)
    
    test_cases = [
        ("Empty string", ""),
        ("Whitespace only", "   \n\t  "),
        ("Very long", "A" * 10000),
        ("Special chars", "!@#$%^&*(){}[]|\\<>?"),
        ("Emoji flood", "😀" * 100),
        ("Null bytes", "test\x00null"),
    ]
    
    passed = 0
    for test_name, text_input in test_cases:
        try:
            # Text sensor should normalize to stimulus
            stimulus = manifest.normalize("TEXT", text_input, is_interrupt=False)
            
            # Should not crash
            assert stimulus is not None
            logger.info(f"  {test_name}: handled")
            passed += 1
            
        except Exception as e:
            logger.error(f"  {test_name}: FAILED - {str(e)}")
    
    logger.info(f"  Text: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def run_sensor_abuse_tests():
    """Run all sensor abuse tests."""
    logger.info("\n" + "="*60)
    logger.info("SENSOR ABUSE TESTS")
    logger.info("="*60 + "\n")
    
    results = {
        "Voice": test_voice_abuse(),
        "Vision": test_vision_abuse(),
        "Text": test_text_abuse()
    }
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("TEST SUMMARY")
    logger.info("="*60)
    for sensor, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        logger.info(f"{status}: {sensor} sensor abuse tests")
    
    all_passed = all(results.values())
    logger.info(f"\nOverall: {'PASS' if all_passed else 'FAIL'}")
    
    return all_passed


if __name__ == "__main__":
    success = run_sensor_abuse_tests()
    sys.exit(0 if success else 1)
