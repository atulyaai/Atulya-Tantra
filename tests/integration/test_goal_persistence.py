"""
Integration test for goal persistence with Engine.
Tests goal restoration across engine restart.
"""

import pytest
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.engine import Engine
from core.memory_manager import MemoryManager
from core.governor import Governor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestGoalPersistence")


def test_goal_persistence_with_engine():
    """Test that goals persist across engine restart."""
    logger.info("[Test] Goal persistence with engine restart...")
    
    # Create engine and add goal
    memory1 = MemoryManager()
    governor1 = Governor(memory1)
    engine1 = Engine(memory1, governor1)
    
    goal_id = engine1.goal_manager.add_goal(
        "Test engine integration goal",
        source="user"
    )
    
    logger.info(f"  Created goal: {goal_id}")
    
    # Simulate restart - create new engine
    memory2 = MemoryManager()
    governor2 = Governor(memory2)
    engine2 = Engine(memory2, governor2)
    
    # Verify goal restored
    goals = engine2.goal_manager.get_all_goals()
    
    assert len(goals) == 1
    assert goals[0]["goal_id"] == goal_id
    assert goals[0]["description"] == "Test engine integration goal"
    
    logger.info("  [PASS] Goal persisted across engine restart")
    
    # Clean up
    if os.path.exists("memory/goals.json"):
        os.remove("memory/goals.json")


if __name__ == "__main__":
    test_goal_persistence_with_engine()
