"""
Unit tests for Atulya components
"""

import unittest
from datetime import datetime, timedelta
from atulya import Atulya
from atulya.core.nlp_engine import NLPEngine
from atulya.core.reasoning_engine import ReasoningEngine
from atulya.memory.memory_manager import MemoryManager
from atulya.evolution.evolution_engine import EvolutionEngine
from atulya.agents.task_agent import TaskAgent
from atulya.skills.skill_manager import SkillManager
from atulya.automation.task_scheduler import TaskScheduler
from atulya.integrations.integration_manager import IntegrationManager


class TestAtulyaCore(unittest.TestCase):
    """Test Atulya main engine"""
    
    def setUp(self):
        self.assistant = Atulya(name="TestAtulya")
    
    def test_initialization(self):
        """Test Atulya initialization"""
        self.assertEqual(self.assistant.name, "TestAtulya")
        self.assertEqual(self.assistant.stats["tasks_executed"], 0)
    
    def test_task_execution(self):
        """Test task execution"""
        result = self.assistant.execute_task("Test task")
        self.assertIn("success", result)
        self.assertEqual(self.assistant.stats["tasks_executed"], 1)
    
    def test_evolution_status(self):
        """Test evolution status retrieval"""
        status = self.assistant.get_evolution_status()
        self.assertIn("name", status)
        self.assertIn("stats", status)
        self.assertIn("evolution_metrics", status)


class TestNLPEngine(unittest.TestCase):
    """Test NLP Engine"""
    
    def setUp(self):
        self.nlp = NLPEngine()
    
    def test_parse_task(self):
        """Test task parsing"""
        parsed = self.nlp.parse_task("What is AI?")
        self.assertIn("intent", parsed)
        self.assertIn("keywords", parsed)
    
    def test_intent_detection(self):
        """Test intent detection"""
        assert self.nlp._detect_intent("Tell me about Python") == "information"
        assert self.nlp._detect_intent("Run the script") == "execution"
    
    def test_sentiment_analysis(self):
        """Test sentiment analysis"""
        sentiment = self.nlp.sentiment_analysis("I love this amazing system")
        self.assertGreater(sentiment["positive"], sentiment["negative"])


class TestMemoryManager(unittest.TestCase):
    """Test Memory Manager"""
    
    def setUp(self):
        self.memory = MemoryManager()
    
    def test_store_task_result(self):
        """Test storing task results"""
        result = {"success": True, "output": "test"}
        self.memory.store_task_result("test_task", result)
        self.assertGreater(self.memory.get_size()["short_term"], 0)
    
    def test_search_similar(self):
        """Test similarity search"""
        self.memory.store_task_result("machine learning task", {"success": True})
        similar = self.memory.search_similar("machine learning")
        self.assertGreater(len(similar), 0)


class TestEvolutionEngine(unittest.TestCase):
    """Test Evolution Engine"""
    
    def setUp(self):
        self.evolution = EvolutionEngine()
    
    def test_evolution_step(self):
        """Test evolution iteration"""
        result = {"success": True}
        insights = {"success": True, "confidence": 0.9}
        evolution_result = self.evolution.evolve("test_task", result, insights)
        
        self.assertGreater(evolution_result["fitness"], 0)
        self.assertEqual(evolution_result["generation"], 1)
    
    def test_get_metrics(self):
        """Test metrics retrieval"""
        metrics = self.evolution.get_metrics()
        self.assertIn("generation", metrics)
        self.assertIn("avg_fitness", metrics)


class TestSkillManager(unittest.TestCase):
    """Test Skill Manager"""
    
    def setUp(self):
        self.skills = SkillManager()
    
    def test_add_skill(self):
        """Test adding skills"""
        success = self.skills.add_skill("test_skill", {"data": "test"})
        self.assertTrue(success)
        self.assertEqual(self.skills.count_skills(), 1)
    
    def test_skill_usage(self):
        """Test skill usage and improvement"""
        self.skills.add_skill("test_skill", {"initial_proficiency": 0.5})
        result = self.skills.use_skill("test_skill")
        self.assertIn("proficiency", result)


class TestTaskScheduler(unittest.TestCase):
    """Test Task Scheduler"""
    
    def setUp(self):
        self.scheduler = TaskScheduler()
    
    def test_schedule_task(self):
        """Test task scheduling"""
        def dummy_task():
            return "executed"
        
        scheduled = self.scheduler.schedule_task(
            "test_task",
            dummy_task,
            datetime.now() + timedelta(seconds=10)
        )
        self.assertTrue(scheduled)
    
    def test_automation_rule(self):
        """Test automation rules"""
        def trigger():
            return True
        
        def action():
            pass
        
        success = self.scheduler.add_automation_rule("test_rule", trigger, action)
        self.assertTrue(success)


class TestIntegrationManager(unittest.TestCase):
    """Test Integration Manager"""
    
    def setUp(self):
        self.integrations = IntegrationManager()
    
    def test_integration_manager_init(self):
        """Test integration manager initialization"""
        self.assertEqual(len(self.integrations.integrations), 0)


if __name__ == "__main__":
    unittest.main()
