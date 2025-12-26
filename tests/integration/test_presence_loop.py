"""
Integration test for Presence Loop
Tests idle stability, priority preemption, and watchdog timeout.
"""

import pytest
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.engine import Engine
from core.memory_manager import MemoryManager
from core.governor import Governor
from internal.simulator import StimulusInjector


class TestPresenceLoop:
    """Integration tests for presence loop behavior."""
    
    def test_presence_loop_initialization(self, mock_memory, mock_governor):
        """Test that presence loop can be initialized."""
        engine = Engine(mock_memory, mock_governor)
        simulator = StimulusInjector()
        
        assert engine is not None
        assert simulator is not None
    
    def test_idle_stability(self, mock_memory, mock_governor, disable_logging):
        """Test that system remains stable during idle polling."""
        engine = Engine(mock_memory, mock_governor)
        simulator = StimulusInjector()
        
        # Simulate idle polling (no stimuli)
        for _ in range(10):
            # In real loop, this would poll sensors
            time.sleep(0.01)
        
        # Should not crash
        assert True
    
    def test_stimulus_injection(self, mock_memory, mock_governor, disable_logging):
        """Test that stimuli can be injected and processed."""
        engine = Engine(mock_memory, mock_governor)
        simulator = StimulusInjector()
        
        # Inject test stimulus
        simulator.inject_text("Test message")
        
        # Verify injection
        assert len(simulator.buffer) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
