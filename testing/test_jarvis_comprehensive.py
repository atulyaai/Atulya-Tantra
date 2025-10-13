"""
Comprehensive JARVIS Protocol Test Suite
Tests all JARVIS functionality including Ollama integration
"""

import unittest
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from protocols.jarvis import JarvisInterface
from protocols.jarvis.conversation import ConversationManager
from protocols.jarvis.personality import PersonalityEngine, EmotionalState


class TestJarvisComprehensive(unittest.TestCase):
    """Comprehensive JARVIS Protocol tests"""
    
    def setUp(self):
        """Set up test fixtures"""
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
        self.assertIn('model', result)
    
    def test_deactivation(self):
        """Test JARVIS deactivation"""
        asyncio.run(self.jarvis.activate())
        result = asyncio.run(self.jarvis.deactivate())
        self.assertEqual(result['status'], 'inactive')
        self.assertFalse(self.jarvis.is_active)
    
    def test_message_processing_structure(self):
        """Test message processing returns correct structure"""
        result = asyncio.run(self.jarvis.process_message("Hello"))
        
        self.assertIn('response', result)
        self.assertIn('status', result)
        self.assertIn('protocol', result)
        self.assertEqual(result['protocol'], 'JARVIS')
    
    def test_emotion_detection(self):
        """Test emotion detection in messages"""
        test_cases = [
            ("I'm so happy!", 'happy'),
            ("I'm feeling sad", 'sad'),
            ("I'm angry", 'angry'),
            ("Hello", 'neutral'),
        ]
        
        for message, expected_emotion in test_cases:
            result = asyncio.run(self.jarvis.process_message(message))
            if result['status'] == 'success':
                detected = result.get('emotion_detected')
                self.assertIsNotNone(detected)
    
    def test_conversation_context(self):
        """Test conversation context is preserved"""
        asyncio.run(self.jarvis.process_message("My name is Alice"))
        asyncio.run(self.jarvis.process_message("What's my name?"))
        
        # Check conversation history
        history = self.jarvis.conversation.history
        self.assertGreaterEqual(len(history), 2)
    
    def test_personality_adaptation(self):
        """Test personality adapts to emotions"""
        result = asyncio.run(self.jarvis.process_message("I'm feeling sad"))
        
        if result['status'] == 'success':
            personality_state = result.get('personality_state')
            self.assertIn(personality_state, ['supportive', 'concerned', 'neutral'])
    
    def test_status_endpoint(self):
        """Test status retrieval"""
        status = self.jarvis.get_status()
        
        self.assertIn('protocol', status)
        self.assertEqual(status['protocol'], 'JARVIS')
        self.assertIn('active', status)
        self.assertIn('conversation_length', status)
        self.assertIn('capabilities', status)
    
    def test_multiple_messages(self):
        """Test processing multiple messages in sequence"""
        messages = [
            "Hello",
            "How are you?",
            "Tell me a joke"
        ]
        
        for msg in messages:
            result = asyncio.run(self.jarvis.process_message(msg))
            self.assertIn('status', result)
        
        # Verify all messages saved
        history_length = len(self.jarvis.conversation.history)
        self.assertGreaterEqual(history_length, len(messages) * 2)  # user + assistant


class TestConversationManager(unittest.TestCase):
    """Test conversation management"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.conversation = ConversationManager(max_history=10)
    
    def test_add_message(self):
        """Test adding messages"""
        self.conversation.add_message('user', 'Hello')
        self.assertEqual(len(self.conversation.history), 1)
    
    def test_get_context(self):
        """Test retrieving context"""
        for i in range(5):
            self.conversation.add_message('user', f'Message {i}')
        
        context = self.conversation.get_context(last_n=3)
        self.assertEqual(len(context), 3)
    
    def test_max_history(self):
        """Test history limit enforcement"""
        for i in range(15):
            self.conversation.add_message('user', f'Message {i}')
        
        self.assertLessEqual(len(self.conversation.history), 10)
    
    def test_clear_history(self):
        """Test clearing history"""
        self.conversation.add_message('user', 'Hello')
        self.conversation.clear_history()
        self.assertEqual(len(self.conversation.history), 0)
    
    def test_summary(self):
        """Test conversation summary"""
        self.conversation.add_message('user', 'Hello')
        summary = self.conversation.get_summary()
        
        self.assertIn('total_messages', summary)
        self.assertEqual(summary['total_messages'], 1)


class TestPersonalityEngine(unittest.TestCase):
    """Test personality engine"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.personality = PersonalityEngine()
    
    def test_emotion_detection_happy(self):
        """Test detecting happy emotion"""
        emotion = self.personality.detect_emotion("I'm so happy and excited!")
        self.assertEqual(emotion, 'happy')
    
    def test_emotion_detection_sad(self):
        """Test detecting sad emotion"""
        emotion = self.personality.detect_emotion("I'm feeling sad and upset")
        self.assertEqual(emotion, 'sad')
    
    def test_emotion_detection_neutral(self):
        """Test detecting neutral emotion"""
        emotion = self.personality.detect_emotion("Hello, how are you?")
        self.assertEqual(emotion, 'neutral')
    
    def test_adapt_response_tone(self):
        """Test response tone adaptation"""
        state = self.personality.adapt_response_tone('happy')
        self.assertEqual(state, EmotionalState.ENTHUSIASTIC)
        
        state = self.personality.adapt_response_tone('sad')
        self.assertEqual(state, EmotionalState.SUPPORTIVE)
    
    def test_response_modifiers(self):
        """Test response modifiers"""
        self.personality.adapt_response_tone('happy')
        modifiers = self.personality.get_response_modifiers()
        
        self.assertIn('tone', modifiers)
        self.assertIn('brevity', modifiers)
        self.assertIn('warmth', modifiers)
    
    def test_personality_status(self):
        """Test personality status"""
        status = self.personality.get_status()
        
        self.assertIn('current_state', status)
        self.assertIn('traits', status)


def run_comprehensive_tests():
    """Run all comprehensive tests"""
    print("=" * 70)
    print("🧪 JARVIS PROTOCOL - COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    print()
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestJarvisComprehensive))
    suite.addTests(loader.loadTestsFromTestCase(TestConversationManager))
    suite.addTests(loader.loadTestsFromTestCase(TestPersonalityEngine))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    print("=" * 70)
    if result.wasSuccessful():
        print("✅ ALL COMPREHENSIVE TESTS PASSED")
    else:
        print("⚠️  SOME TESTS FAILED")
    print("=" * 70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_comprehensive_tests()
    sys.exit(0 if success else 1)

