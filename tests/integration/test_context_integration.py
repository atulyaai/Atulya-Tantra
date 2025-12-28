"""
Integration test for Context Engine with Engine.
Verifies activity logging, idle detection, and context-aware suggestions.
"""

import pytest
import time
from core.engine import Engine
from memory.memory import Memory
from core.governor import Governor


class TestContextIntegration:
    """Test Context Engine integration with main Engine"""
    
    def setup_method(self):
        """Setup test environment"""
        self.memory = Memory()
        self.governor = Governor()
        self.engine = Engine(self.memory, self.governor)
    
    def test_activity_logged_on_run_task(self):
        """Test that run_task logs activity"""
        initial_count = self.engine.context_engine.activity_log.count()
        
        self.engine.run_task("test input")
        
        new_count = self.engine.context_engine.activity_log.count()
        assert new_count == initial_count + 1
        
        recent = self.engine.context_engine.activity_log.get_recent(1)
        assert recent[0]["input"] == "test input"
    
    def test_idle_reset_on_activity(self):
        """Test that activity resets idle timer"""
        # Set short idle threshold for testing
        self.engine.context_engine.idle_detector.threshold = 0.1
        
        time.sleep(0.15)
        assert self.engine.context_engine.check_idle()
        
        self.engine.run_task("reset idle")
        assert not self.engine.context_engine.check_idle()
    
    def test_context_passed_to_suggester(self):
        """Test that context is passed to Shadow Suggester"""
        # Log some activity
        self.engine.run_task("search quantum computing")
        self.engine.run_task("search python basics")
        
        # Request suggestion
        self.engine.run_task("what next")
        
        # Context should have been used (verified by no crash)
        context = self.engine.context_engine.get_context()
        assert context["total_activities"] >= 3
    
    def test_pattern_learning(self):
        """Test that patterns are learned from activity"""
        # Generate pattern
        for i in range(5):
            self.engine.run_task(f"search topic {i}")
        
        context = self.engine.context_engine.get_context()
        freq_cmds = context["frequent_commands"]
        
        # Should detect INFORMATION_SEARCH as frequent
        assert len(freq_cmds) > 0
        assert freq_cmds[0][0] == "INFORMATION_SEARCH"
        assert freq_cmds[0][1] >= 5
