"""
Atulya Tantra - Protocol Testing Suite
Comprehensive tests for JARVIS and SKYNET protocols
"""

import unittest
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestJARVISProtocol(unittest.TestCase):
    """Test JARVIS Protocol functionality"""
    
    def setUp(self):
        """Setup test fixtures"""
        from protocols.jarvis import JarvisInterface, ConversationManager, PersonalityEngine
        
        self.jarvis = JarvisInterface()
        self.conversation = ConversationManager()
        self.personality = PersonalityEngine()
    
    def test_jarvis_initialization(self):
        """Test JARVIS interface initializes correctly"""
        self.assertIsNotNone(self.jarvis)
        self.assertFalse(self.jarvis.is_active)
    
    def test_jarvis_activation(self):
        """Test JARVIS activation"""
        result = asyncio.run(self.jarvis.activate())
        self.assertEqual(result['status'], 'active')
        self.assertTrue(self.jarvis.is_active)
    
    def test_conversation_manager(self):
        """Test conversation management"""
        self.conversation.add_message('user', 'Hello')
        self.conversation.add_message('assistant', 'Hi there!')
        
        self.assertEqual(len(self.conversation.history), 2)
        
        context = self.conversation.get_context(last_n=2)
        self.assertEqual(len(context), 2)
    
    def test_personality_emotion_detection(self):
        """Test emotion detection"""
        happy_emotion = self.personality.detect_emotion("I'm so happy!")
        self.assertEqual(happy_emotion, 'happy')
        
        sad_emotion = self.personality.detect_emotion("I'm feeling sad")
        self.assertEqual(sad_emotion, 'sad')
    
    def test_personality_adaptation(self):
        """Test personality adaptation"""
        state = self.personality.adapt_response_tone('happy')
        self.assertIsNotNone(state)


class TestSKYNETProtocol(unittest.TestCase):
    """Test SKYNET Protocol functionality"""
    
    def setUp(self):
        """Setup test fixtures"""
        from protocols.skynet import SkynetOrchestrator, BaseAgent, AgentCoordinator
        
        self.skynet = SkynetOrchestrator()
        self.coordinator = AgentCoordinator()
    
    def test_skynet_initialization(self):
        """Test SKYNET orchestrator initializes correctly"""
        self.assertIsNotNone(self.skynet)
        self.assertFalse(self.skynet.is_active)
    
    def test_skynet_activation(self):
        """Test SKYNET activation"""
        result = asyncio.run(self.skynet.activate())
        self.assertEqual(result['status'], 'active')
        self.assertTrue(self.skynet.is_active)
        self.assertGreater(result['agents_online'], 0)
    
    def test_task_routing(self):
        """Test task routing to appropriate agents"""
        asyncio.run(self.skynet.activate())
        
        result = asyncio.run(self.skynet.route_task("Write a Python function"))
        self.assertEqual(result['routed_to'], 'code')
        
        result = asyncio.run(self.skynet.route_task("Research quantum computing"))
        self.assertEqual(result['routed_to'], 'research')
    
    def test_coordinator(self):
        """Test agent coordination"""
        result = asyncio.run(
            self.coordinator.coordinate(
                "Complex task",
                agents=['code', 'research']
            )
        )
        
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(result['agents']), 2)
    
    def test_task_decomposition(self):
        """Test task decomposition"""
        subtasks = asyncio.run(
            self.coordinator.decompose_task("Build a web application")
        )
        
        self.assertIsInstance(subtasks, list)
        self.assertGreater(len(subtasks), 0)


class TestAgentBase(unittest.TestCase):
    """Test base agent functionality"""
    
    def setUp(self):
        """Setup test fixtures"""
        from protocols.skynet.agent_base import ConversationAgent, CodeAgent, AgentType
        
        self.conversation_agent = ConversationAgent()
        self.code_agent = CodeAgent()
    
    def test_agent_initialization(self):
        """Test agent initialization"""
        self.assertEqual(self.conversation_agent.name, 'ConversationAgent')
        self.assertEqual(self.code_agent.name, 'CodeAgent')
    
    def test_agent_execution(self):
        """Test agent task execution"""
        result = asyncio.run(self.conversation_agent.execute("Hello"))
        self.assertTrue(result['success'])
        
        result = asyncio.run(self.code_agent.execute("Write code"))
        self.assertTrue(result['success'])
    
    def test_agent_status(self):
        """Test agent status retrieval"""
        status = self.conversation_agent.get_status()
        
        self.assertIn('name', status)
        self.assertIn('type', status)
        self.assertIn('status', status)


def run_protocol_tests():
    """Run all protocol tests"""
    print("=" * 70)
    print("🤖 ATULYA TANTRA - PROTOCOL TEST SUITE")
    print("=" * 70)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestJARVISProtocol))
    suite.addTests(loader.loadTestsFromTestCase(TestSKYNETProtocol))
    suite.addTests(loader.loadTestsFromTestCase(TestAgentBase))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print()
    print("=" * 70)
    if result.wasSuccessful():
        print("✅ ALL PROTOCOL TESTS PASSED")
    else:
        print("⚠️  SOME PROTOCOL TESTS FAILED")
    print("=" * 70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_protocol_tests()
    sys.exit(0 if success else 1)

