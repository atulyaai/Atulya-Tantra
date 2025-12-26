"""
Unit tests for GoalManager (Persistent Goals)
Tests goal creation, persistence, corruption recovery, and atomic writes.
"""

import pytest
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.goals import GoalManager
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("TestGoals")


class TestGoalManager:
    """Test suite for persistent goals."""
    
    def test_goal_creation(self):
        """Test goal creation with source guard."""
        gm = GoalManager(storage_path="memory/test_goals.json")
        
        # Valid creation (source='user')
        goal_id = gm.add_goal("Test goal description", source="user")
        
        assert goal_id is not None
        assert len(goal_id) == 36  # UUID length
        
        goals = gm.get_all_goals()
        assert len(goals) == 1
        assert goals[0]["description"] == "Test goal description"
        assert goals[0]["status"] == "pending"
        assert goals[0]["goal_id"] == goal_id
        
        logger.info("  [PASS] Goal creation")
    
    def test_source_guard(self):
        """Test that non-user sources are rejected."""
        gm = GoalManager(storage_path="memory/test_goals.json")
        
        # Should raise PermissionError
        with pytest.raises(PermissionError) as exc_info:
            gm.add_goal("Auto-created goal", source="system")
        
        assert "explicit user instruction" in str(exc_info.value)
        
        logger.info("  [PASS] Source guard enforced")
    
    def test_persistence_across_restart(self):
        """Test that goals persist across GoalManager restart."""
        # Clean up first
        test_file = "memory/test_goals.json"
        if os.path.exists(test_file):
            os.remove(test_file)
        
        # Create goal
        gm1 = GoalManager(storage_path=test_file)
        goal_id = gm1.add_goal("Persistent goal", source="user")
        
        # Simulate restart
        gm2 = GoalManager(storage_path=test_file)
        goals = gm2.load_goals()
        
        assert len(goals) == 1
        assert goals[0]["goal_id"] == goal_id
        assert goals[0]["description"] == "Persistent goal"
        
        logger.info("  [PASS] Persistence across restart")
    
    def test_corruption_recovery(self):
        """Test graceful recovery from corrupted goals.json."""
        gm = GoalManager(storage_path="memory/test_goals.json")
        
        # Write invalid JSON
        with open(gm.storage_path, 'w') as f:
            f.write('{"goals": [invalid json')
        
        # Should recover gracefully
        gm2 = GoalManager(storage_path="memory/test_goals.json")
        goals = gm2.get_all_goals()
        
        assert len(goals) == 0  # Reset to empty
        assert os.path.exists(gm.storage_path + ".corrupted")  # Backup created
        
        logger.info("  [PASS] Corruption recovery")
    
    def test_status_transitions(self):
        """Test goal status transitions."""
        gm = GoalManager(storage_path="memory/test_goals.json")
        goal_id = gm.add_goal("Status test goal", source="user")
        
        # pending → active
        gm.update_goal(goal_id, status="active", last_action="Started work")
        goal = gm.get_goal_by_id(goal_id)
        assert goal["status"] == "active"
        assert goal["last_action"] == "Started work"
        
        # active → blocked
        gm.update_goal(goal_id, status="blocked", blocker="Waiting for user input")
        goal = gm.get_goal_by_id(goal_id)
        assert goal["status"] == "blocked"
        assert goal["blocker"] == "Waiting for user input"
        
        # blocked → completed
        gm.update_goal(goal_id, status="completed", last_action="Finished")
        goal = gm.get_goal_by_id(goal_id)
        assert goal["status"] == "completed"
        
        logger.info("  [PASS] Status transitions")
    
    def test_read_only_access(self):
        """Test that returned goals are copies (read-only)."""
        gm = GoalManager(storage_path="memory/test_goals.json")
        goal_id = gm.add_goal("Read-only test", source="user")
        
        # Get goal
        goal = gm.get_goal_by_id(goal_id)
        
        # Modify returned copy
        goal["description"] = "Modified externally"
        goal["status"] = "hacked"
        
        # Original should be unchanged
        goal_original = gm.get_goal_by_id(goal_id)
        assert goal_original["description"] == "Read-only test"
        assert goal_original["status"] == "pending"
        
        logger.info("  [PASS] Read-only access enforced")
    
    def test_atomic_writes(self):
        """Test atomic write behavior."""
        gm = GoalManager(storage_path="memory/test_goals.json")
        gm.add_goal("Atomic test", source="user")
        
        # Verify temp file doesn't exist after save
        temp_path = gm.storage_path + ".tmp"
        assert not os.path.exists(temp_path)
        
        # Verify actual file exists
        assert os.path.exists(gm.storage_path)
        
        logger.info("  [PASS] Atomic writes")


def run_goal_tests():
    """Run all goal tests."""
    logger.info("\n" + "="*60)
    logger.info("GOAL MANAGER TESTS")
    logger.info("="*60 + "\n")
    
    # Clean up test file
    test_file = "memory/test_goals.json"
    if os.path.exists(test_file):
        os.remove(test_file)
    if os.path.exists(test_file + ".corrupted"):
        os.remove(test_file + ".corrupted")
    
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    run_goal_tests()
