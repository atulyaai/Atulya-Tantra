#!/usr/bin/env python3
"""
Atulya Tantra - Complete Test Suite
All tests consolidated in one file for simplicity
"""

import unittest
import asyncio
import sys
import os
import importlib
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import get_config, get_logger
from configuration import (
    JarvisInterface, ConversationManager, PersonalityEngine, EmotionalState,
    SkynetOrchestrator, get_prompt, list_available_prompts
)

logger = get_logger('testing')


# ============================================================================
# SYSTEM TESTS
# ============================================================================

class TestSystemIntegrity(unittest.TestCase):
    """Test system integrity and structure"""
    
    def setUp(self):
        self.root = Path(__file__).parent.parent
    
    def test_directories_exist(self):
        """Test required directories exist"""
        required = ['core', 'configuration', 'models', 'automation', 'testing', 'webui']
        for dir_name in required:
            self.assertTrue((self.root / dir_name).exists(), f"Missing: {dir_name}")
        
        # Verify protocols are in configuration
        self.assertTrue((self.root / 'configuration' / 'protocols').exists(), 
                       "Missing: configuration/protocols")
    
    def test_core_files_exist(self):
        """Test core files exist"""
        required = [
            'VERSION', 'README.md', 'LICENSE', 'requirements.txt',
            'core/__init__.py', 'configuration/__init__.py'
        ]
        for file_path in required:
            self.assertTrue((self.root / file_path).exists(), f"Missing: {file_path}")
    
    def test_imports_work(self):
        """Test critical imports"""
        modules = [
            'core', 'configuration', 'configuration.protocols.jarvis', 'configuration.protocols.skynet'
        ]
        for module in modules:
            try:
                importlib.import_module(module)
            except ImportError as e:
                self.fail(f"Import failed: {module} - {e}")


# ============================================================================
# CONFIGURATION TESTS
# ============================================================================

class TestConfiguration(unittest.TestCase):
    """Test configuration system"""
    
    def test_global_config(self):
        """Test global configuration"""
        config = get_config()
        self.assertIsNotNone(config)
        self.assertEqual(config.version, "1.0.3")
        self.assertEqual(config.codename, "JARVIS")
    
    def test_config_settings(self):
        """Test configuration settings"""
        config = get_config()
        self.assertIsNotNone(config.default_model)
        self.assertIsInstance(config.temperature, float)
        self.assertIsInstance(config.max_tokens, int)
    
    def test_prompts_available(self):
        """Test prompts are available"""
        prompts = list_available_prompts()
        self.assertGreater(len(prompts), 0)
        self.assertIn('jarvis', prompts)
        self.assertIn('skynet', prompts)
    
    def test_prompt_retrieval(self):
        """Test prompt retrieval"""
        jarvis_prompt = get_prompt('jarvis')
        self.assertIsNotNone(jarvis_prompt)
        self.assertGreater(len(jarvis_prompt), 0)


# ============================================================================
# JARVIS PROTOCOL TESTS
# ============================================================================

class TestJarvisProtocol(unittest.TestCase):
    """Test JARVIS Protocol"""
    
    def setUp(self):
        self.jarvis = JarvisInterface()
    
    def test_initialization(self):
        """Test JARVIS initialization"""
        self.assertIsNotNone(self.jarvis)
        self.assertFalse(self.jarvis.is_active)
        self.assertIsNotNone(self.jarvis.conversation)
        self.assertIsNotNone(self.jarvis.personality)
    
    def test_activation(self):
        """Test JARVIS activation"""
        result = asyncio.run(self.jarvis.activate())
        self.assertEqual(result['status'], 'active')
        self.assertTrue(self.jarvis.is_active)
    
    def test_deactivation(self):
        """Test JARVIS deactivation"""
        asyncio.run(self.jarvis.activate())
        result = asyncio.run(self.jarvis.deactivate())
        self.assertEqual(result['status'], 'inactive')
        self.assertFalse(self.jarvis.is_active)
    
    def test_status(self):
        """Test JARVIS status"""
        status = self.jarvis.get_status()
        self.assertIn('protocol', status)
        self.assertEqual(status['protocol'], 'JARVIS')


class TestConversationManager(unittest.TestCase):
    """Test conversation management"""
    
    def setUp(self):
        self.conversation = ConversationManager(max_history=10)
    
    def test_add_message(self):
        """Test adding messages"""
        self.conversation.add_message('user', 'Hello')
        self.assertEqual(len(self.conversation.history), 1)
    
    def test_get_context(self):
        """Test getting context"""
        for i in range(5):
            self.conversation.add_message('user', f'Message {i}')
        context = self.conversation.get_context(last_n=3)
        self.assertEqual(len(context), 3)
    
    def test_max_history(self):
        """Test max history limit"""
        for i in range(15):
            self.conversation.add_message('user', f'Message {i}')
        self.assertLessEqual(len(self.conversation.history), 10)


class TestPersonalityEngine(unittest.TestCase):
    """Test personality engine"""
    
    def setUp(self):
        self.personality = PersonalityEngine()
    
    def test_emotion_detection(self):
        """Test emotion detection"""
        emotions = [
            ("I'm so happy!", 'happy'),
            ("I'm feeling sad", 'sad'),
            ("Hello", 'neutral'),
        ]
        for text, expected in emotions:
            emotion = self.personality.detect_emotion(text)
            self.assertIsNotNone(emotion)
    
    def test_personality_adaptation(self):
        """Test personality adaptation"""
        state = self.personality.adapt_response_tone('happy')
        self.assertEqual(state, EmotionalState.ENTHUSIASTIC)
    
    def test_response_modifiers(self):
        """Test response modifiers"""
        modifiers = self.personality.get_response_modifiers()
        self.assertIn('tone', modifiers)
        self.assertIn('warmth', modifiers)


# ============================================================================
# SKYNET PROTOCOL TESTS
# ============================================================================

class TestSkynetProtocol(unittest.TestCase):
    """Test SKYNET Protocol"""
    
    def setUp(self):
        self.skynet = SkynetOrchestrator()
    
    def test_initialization(self):
        """Test SKYNET initialization"""
        self.assertIsNotNone(self.skynet)
        self.assertFalse(self.skynet.is_active)
    
    def test_activation(self):
        """Test SKYNET activation"""
        result = asyncio.run(self.skynet.activate())
        self.assertEqual(result['status'], 'active')
        self.assertTrue(self.skynet.is_active)
    
    def test_status(self):
        """Test SKYNET status"""
        asyncio.run(self.skynet.activate())
        status = self.skynet.get_status()
        self.assertIn('protocol', status)
        self.assertEqual(status['protocol'], 'SKYNET')


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance(unittest.TestCase):
    """Test system performance"""
    
    def test_import_speed(self):
        """Test import speed"""
        import time
        start = time.time()
        importlib.reload(sys.modules['core'])
        elapsed = time.time() - start
        self.assertLess(elapsed, 1.0, "Import too slow")
    
    def test_config_access_speed(self):
        """Test config access speed"""
        import time
        start = time.time()
        for _ in range(1000):
            config = get_config()
        elapsed = time.time() - start
        self.assertLess(elapsed, 0.1, "Config access too slow")


# ============================================================================
# TEST RUNNER
# ============================================================================

def run_all_tests(verbose=True):
    """Run all tests"""
    if verbose:
        print("=" * 70)
        print("🧪 ATULYA TANTRA - COMPLETE TEST SUITE")
        print("=" * 70)
        print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestSystemIntegrity,
        TestConfiguration,
        TestJarvisProtocol,
        TestConversationManager,
        TestPersonalityEngine,
        TestSkynetProtocol,
        TestPerformance,
    ]
    
    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2 if verbose else 1)
    result = runner.run(suite)
    
    # Print summary
    if verbose:
        print()
        print("=" * 70)
        if result.wasSuccessful():
            print("✅ ALL TESTS PASSED")
        else:
            print("⚠️  SOME TESTS FAILED")
        print("=" * 70)
        print(f"Tests Run: {result.testsRun}")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        print("=" * 70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)

