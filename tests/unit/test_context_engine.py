"""
Unit tests for Context Engine components.
Tests: ActivityLog, IdleDetector, PatternLearner, PreferenceModel, ContextEngine
"""

import pytest
import os
import json
import time
from datetime import datetime, timedelta
from core.context_engine import (
    ActivityLog, IdleDetector, PatternLearner, 
    PreferenceModel, ContextEngine
)


class TestActivityLog:
    """Test ActivityLog persistence and rotation"""
    
    def setup_method(self):
        """Create temp log file for testing"""
        self.test_log = "memory/test_activity_log.json"
        if os.path.exists(self.test_log):
            os.remove(self.test_log)
    
    def teardown_method(self):
        """Clean up test files"""
        if os.path.exists(self.test_log):
            os.remove(self.test_log)
    
    def test_log_activity(self):
        """Test basic activity logging"""
        log = ActivityLog(self.test_log)
        log.log("test input", "trace123", "GENERAL_TASK", 100)
        
        assert log.count() == 1
        recent = log.get_recent(1)
        assert recent[0]["input"] == "test input"
        assert recent[0]["trace_id"] == "trace123"
    
    def test_persistence(self):
        """Test log survives restart"""
        log1 = ActivityLog(self.test_log)
        log1.log("persistent test", "trace456", "INFORMATION_SEARCH", 200)
        
        # Simulate restart
        log2 = ActivityLog(self.test_log)
        assert log2.count() == 1
        assert log2.get_recent(1)[0]["input"] == "persistent test"
    
    def test_rotation(self):
        """Test automatic rotation at max_entries"""
        log = ActivityLog(self.test_log, max_entries=5)
        
        # Add 10 entries
        for i in range(10):
            log.log(f"entry {i}", f"trace{i}", "GENERAL_TASK", 0)
        
        # Should only keep last 5
        assert log.count() == 5
        recent = log.get_recent(5)
        assert recent[0]["input"] == "entry 5"
        assert recent[-1]["input"] == "entry 9"
    
    def test_corruption_recovery(self):
        """Test recovery from corrupted log file"""
        # Create corrupted file
        with open(self.test_log, 'w') as f:
            f.write("{ invalid json }")
        
        # Should recover gracefully
        log = ActivityLog(self.test_log)
        assert log.count() == 0
        log.log("recovery test", "trace789", "GENERAL_TASK", 0)
        assert log.count() == 1


class TestIdleDetector:
    """Test idle detection logic"""
    
    def test_initial_state(self):
        """Test detector starts as not idle"""
        detector = IdleDetector(threshold=1)
        assert not detector.is_idle()
    
    def test_idle_after_threshold(self):
        """Test becomes idle after threshold"""
        detector = IdleDetector(threshold=0.1)  # 100ms threshold
        time.sleep(0.15)
        assert detector.is_idle()
    
    def test_reset(self):
        """Test reset clears idle state"""
        detector = IdleDetector(threshold=0.1)
        time.sleep(0.15)
        assert detector.is_idle()
        
        detector.reset()
        assert not detector.is_idle()
    
    def test_idle_duration(self):
        """Test idle duration calculation"""
        detector = IdleDetector(threshold=1)
        time.sleep(0.1)
        duration = detector.idle_duration()
        assert 0.09 < duration < 0.15  # Allow some variance


class TestPatternLearner:
    """Test pattern recognition"""
    
    def test_frequent_commands(self):
        """Test command frequency detection"""
        log = ActivityLog("memory/test_pattern_log.json")
        
        # Add activities with different intents
        log.log("search 1", "t1", "INFORMATION_SEARCH", 0)
        log.log("search 2", "t2", "INFORMATION_SEARCH", 0)
        log.log("create file", "t3", "FILE_CREATION", 0)
        
        learner = PatternLearner()
        learner.learn_from_activity(log)
        
        freq_cmds = learner.get_frequent_commands(2)
        assert freq_cmds[0][0] == "INFORMATION_SEARCH"
        assert freq_cmds[0][1] == 2
        
        # Cleanup
        os.remove("memory/test_pattern_log.json")
    
    def test_frequent_topics(self):
        """Test topic extraction"""
        log = ActivityLog("memory/test_topic_log.json")
        
        log.log("quantum computing basics", "t1", "INFORMATION_SEARCH", 0)
        log.log("quantum mechanics intro", "t2", "INFORMATION_SEARCH", 0)
        
        learner = PatternLearner()
        learner.learn_from_activity(log)
        
        freq_topics = learner.get_frequent_topics(5)
        topic_words = [t[0] for t in freq_topics]
        assert "quantum" in topic_words
        
        # Cleanup
        os.remove("memory/test_topic_log.json")


class TestPreferenceModel:
    """Test preference learning"""
    
    def setup_method(self):
        self.test_pref = "memory/test_preferences.json"
        if os.path.exists(self.test_pref):
            os.remove(self.test_pref)
    
    def teardown_method(self):
        if os.path.exists(self.test_pref):
            os.remove(self.test_pref)
    
    def test_initial_score(self):
        """Test default preference score"""
        model = PreferenceModel(self.test_pref)
        assert model.get_action_score("local_search") == 0.5
    
    def test_approval_increases_score(self):
        """Test approval increases preference"""
        model = PreferenceModel(self.test_pref)
        model.update_action_preference("local_search", approved=True)
        assert model.get_action_score("local_search") > 0.5
    
    def test_rejection_decreases_score(self):
        """Test rejection decreases preference"""
        model = PreferenceModel(self.test_pref)
        model.update_action_preference("web_search", approved=False)
        assert model.get_action_score("web_search") < 0.5
    
    def test_persistence(self):
        """Test preferences persist across restarts"""
        model1 = PreferenceModel(self.test_pref)
        model1.update_action_preference("read_file", approved=True)
        
        model2 = PreferenceModel(self.test_pref)
        assert model2.get_action_score("read_file") > 0.5


class TestContextEngine:
    """Integration tests for ContextEngine"""
    
    def setup_method(self):
        self.test_log = "memory/test_context_log.json"
        self.test_pref = "memory/test_context_pref.json"
        for f in [self.test_log, self.test_pref]:
            if os.path.exists(f):
                os.remove(f)
    
    def teardown_method(self):
        for f in [self.test_log, self.test_pref]:
            if os.path.exists(f):
                os.remove(f)
    
    def test_log_activity_resets_idle(self):
        """Test logging activity resets idle timer"""
        engine = ContextEngine(self.test_log, self.test_pref)
        engine.idle_detector.threshold = 0.1
        
        time.sleep(0.15)
        assert engine.check_idle()
        
        engine.log_activity("test", "t1", "GENERAL_TASK", 0)
        assert not engine.check_idle()
    
    def test_get_context(self):
        """Test context retrieval"""
        engine = ContextEngine(self.test_log, self.test_pref)
        engine.log_activity("search quantum", "t1", "INFORMATION_SEARCH", 100)
        engine.log_activity("search python", "t2", "INFORMATION_SEARCH", 150)
        
        context = engine.get_context()
        assert context["total_activities"] == 2
        assert len(context["recent_activities"]) == 2
        assert context["frequent_commands"][0][0] == "INFORMATION_SEARCH"
    
    def test_learn_from_approval(self):
        """Test preference learning integration"""
        engine = ContextEngine(self.test_log, self.test_pref)
        engine.learn_from_approval("local_search", approved=True)
        
        score = engine.preference_model.get_action_score("local_search")
        assert score > 0.5
