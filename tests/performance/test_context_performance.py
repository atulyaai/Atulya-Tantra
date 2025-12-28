"""
Performance test for Context Engine.
Verifies system can handle high activity volume without degradation.
"""

import pytest
import time
from core.context_engine import ContextEngine


class TestContextPerformance:
    """Performance and stress tests for Context Engine"""
    
    def setup_method(self):
        self.engine = ContextEngine(
            "memory/test_perf_log.json",
            "memory/test_perf_pref.json"
        )
    
    def teardown_method(self):
        import os
        for f in ["memory/test_perf_log.json", "memory/test_perf_pref.json"]:
            if os.path.exists(f):
                os.remove(f)
    
    def test_1000_activities_performance(self):
        """Test logging 1000 activities"""
        start = time.time()
        
        for i in range(1000):
            self.engine.log_activity(
                f"test activity {i}",
                f"trace{i}",
                "GENERAL_TASK",
                100
            )
        
        duration = time.time() - start
        
        # Should complete in <1 second
        assert duration < 1.0, f"Took {duration}s, expected <1s"
        
        # Should auto-rotate to 1000 entries
        assert self.engine.activity_log.count() == 1000
    
    def test_pattern_learning_performance(self):
        """Test pattern learning on large dataset"""
        # Generate 500 activities
        for i in range(500):
            intent = "INFORMATION_SEARCH" if i % 2 == 0 else "FILE_CREATION"
            self.engine.log_activity(f"activity {i}", f"t{i}", intent, 50)
        
        start = time.time()
        context = self.engine.get_context()
        duration = time.time() - start
        
        # Pattern learning should be fast (<100ms)
        assert duration < 0.1, f"Pattern learning took {duration}s"
        
        # Should detect patterns
        assert len(context["frequent_commands"]) > 0
        assert context["frequent_commands"][0][1] == 250  # 250 searches
    
    def test_idle_detection_overhead(self):
        """Test idle detection has minimal overhead"""
        iterations = 10000
        start = time.time()
        
        for _ in range(iterations):
            self.engine.check_idle()
        
        duration = time.time() - start
        per_check = (duration / iterations) * 1000  # ms
        
        # Should be <0.01ms per check
        assert per_check < 0.01, f"Idle check: {per_check}ms, expected <0.01ms"
    
    def test_concurrent_activity_logging(self):
        """Test thread-safety of activity logging"""
        import threading
        
        def log_activities(thread_id):
            for i in range(100):
                self.engine.log_activity(
                    f"thread {thread_id} activity {i}",
                    f"t{thread_id}_{i}",
                    "GENERAL_TASK",
                    10
                )
        
        threads = [threading.Thread(target=log_activities, args=(i,)) for i in range(5)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have 500 total activities (5 threads * 100 each)
        assert self.engine.activity_log.count() == 500
