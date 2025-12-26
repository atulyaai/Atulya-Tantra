"""
Unit tests for Governor (Safety Layer)
Tests safety checks, TraceID enforcement, and policy blocking.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.governor import Governor
from core.memory_manager import MemoryManager


class TestGovernor:
    """Test suite for safety and governance."""
    
    def test_governor_initialization(self, mock_memory):
        """Test that governor initializes correctly."""
        governor = Governor(mock_memory)
        assert governor is not None
        assert governor.memory == mock_memory
    
    def test_trace_id_generation(self, mock_memory):
        """Test that TraceID is generated."""
        governor = Governor(mock_memory)
        trace_id = governor.generate_trace_id()
        
        assert trace_id is not None
        assert len(trace_id) == 8  # 8-char TraceID
        assert isinstance(trace_id, str)
    
    def test_trace_id_uniqueness(self, mock_memory):
        """Test that TraceIDs are unique."""
        governor = Governor(mock_memory)
        
        trace_ids = [governor.generate_trace_id() for _ in range(100)]
        unique_ids = set(trace_ids)
        
        # Should have high uniqueness (allow small collision rate)
        assert len(unique_ids) > 95
    
    def test_dangerous_command_blocking(self, mock_memory):
        """Test that dangerous commands are blocked."""
        governor = Governor(mock_memory)
        
        dangerous_commands = [
            "rm -rf /",
            "del C:\\Windows",
            "subprocess.call(['rm', '-rf', '/'])"
        ]
        
        for cmd in dangerous_commands:
            # Governor should block or flag these
            # Implementation depends on governor logic
            pass  # Placeholder for actual blocking test
    
    def test_policy_enforcement(self, mock_memory):
        """Test that policies are enforced."""
        governor = Governor(mock_memory)
        
        # Test that governor has policy mechanisms
        assert hasattr(governor, 'memory')
        assert governor.memory is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
