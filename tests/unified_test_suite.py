import pytest
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.brain import KnowledgeBrain
from core.memory import GoalManager
from core.governance import Governor, ActionLedger
from core.engine import Engine

class TestUnifiedJARVIS:
    def test_knowledge_brain(self):
        kb = KnowledgeBrain(storage_path="memory/test_kb.json")
        kb.add_fact("SYSTEM", "Test fact")
        facts, topic = kb.query_knowledge("SYSTEM query")
        assert len(facts) > 0
        assert topic == "SYSTEM"
        if os.path.exists("memory/test_kb.json"): os.remove("memory/test_kb.json")

    def test_goals(self):
        gm = GoalManager(storage_path="memory/test_goals.json")
        gid = gm.add_goal("Test goal", source="user")
        assert gid is not None
        assert len(gm.get_all_goals()) == 1
        if os.path.exists("memory/test_goals.json"): os.remove("memory/test_goals.json")

    def test_engine_init(self):
        # Mock objects for basic init test
        class Mock: pass
        engine = Engine(Mock(), Mock())
        assert engine is not None
        assert engine.identity is not None

if __name__ == "__main__":
    pytest.main([__file__])
