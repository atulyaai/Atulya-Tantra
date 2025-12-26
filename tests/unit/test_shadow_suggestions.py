import unittest
from unittest.mock import MagicMock
from core.shadow_suggestions import ShadowSuggester
from core.engine import Engine

class TestShadowSuggestions(unittest.TestCase):
    def setUp(self):
        self.mock_goals = MagicMock()
        self.mock_planner = MagicMock()
        self.mock_ledger = MagicMock()
        self.suggester = ShadowSuggester(self.mock_goals, self.mock_planner, self.mock_ledger)

    def test_no_active_goals(self):
        self.mock_goals.get_active_goals.return_value = []
        msg = self.suggester.generate_suggestion()
        self.assertIn("don't have any active goals", msg)

    def test_suggestion_generation(self):
        # Setup mock goal
        self.mock_goals.get_active_goals.return_value = [{'description': 'Test Goal'}]
        
        # Setup mock plan
        # Planner.plan returns list of (strategy_name, steps)
        self.mock_planner.plan.return_value = [
            ("StrategyA", [{"action": "local_search", "params": {"query": "foo"}}])
        ]
        
        # Setup mock ledger
        self.mock_ledger.get_success_rate.return_value = 0.9
        
        msg = self.suggester.generate_suggestion()
        
        self.assertIn("One possible next step is", msg)
        self.assertIn("search for 'foo'", msg)
        self.assertIn("Confidence: High", msg)
        self.assertIn("Would you like me to do it", msg)

    def test_low_confidence(self):
        self.mock_goals.get_active_goals.return_value = [{'description': 'Test Goal'}]
        self.mock_planner.plan.return_value = [
            ("StrategyB", [{"action": "unknown_action"}])
        ]
        self.mock_ledger.get_success_rate.return_value = 0.0
        
        msg = self.suggester.generate_suggestion()
        
        self.assertIn("perform unknown_action", msg)
        self.assertIn("Confidence: Low/Unknown", msg)

    def test_no_side_effects(self):
        """Verify suggestion generation calls NOTHING on executor (implicit by design, but checking planner calls)"""
        self.mock_goals.get_active_goals.return_value = [{'description': 'Test Goal'}]
        self.suggester.generate_suggestion()
        
        # Planner should be called with Intent
        self.mock_planner.plan.assert_called_once()
        # Ensure no other side effects (mock ledger read only)
        # Executor is not even passed to Suggester, so it CANNOT execute.

if __name__ == '__main__':
    unittest.main()
