import unittest
import os
import json
import shutil
import time
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.engine import Engine
from core.memory_manager import MemoryManager
from core.governor import Governor

class TestActionLedgerPersistence(unittest.TestCase):
    def setUp(self):
        self.ledger_path = "memory/action_ledger.json"
        
        # Backup existing ledger if it exists (don't destroy real data)
        if os.path.exists(self.ledger_path):
            shutil.copy2(self.ledger_path, self.ledger_path + ".bak")
            os.remove(self.ledger_path)
            
        self.memory = MemoryManager()
        self.governor = Governor(self.memory)
        self.engine = Engine(self.memory, self.governor)

    def tearDown(self):
        # Restore real ledger
        if os.path.exists(self.ledger_path + ".bak"):
            if os.path.exists(self.ledger_path):
                os.remove(self.ledger_path)
            shutil.move(self.ledger_path + ".bak", self.ledger_path)

    def test_engine_integration_persistence(self):
        # 1. Simulate a successful task via Engine internals
        # We manually record because running a full task is complex/slow
        # But we want to test the Engine's instance of ledger
        
        trace_id = "INTEG_TEST"
        self.engine.action_ledger.record_outcome(
            action_type="integration_test_action",
            outcome="success",
            context="Testing persistence from engine",
            confidence=0.99,
            trace_id=trace_id
        )
        
        # 2. Verify file exists
        self.assertTrue(os.path.exists(self.ledger_path))
        
        # 3. Simulate Restart (New Engine)
        del self.engine
        new_engine = Engine(self.memory, self.governor)
        
        # 4. Verify Data Preserved
        entries = new_engine.action_ledger.entries
        self.assertTrue(len(entries) > 0)
        
        last_entry = entries[-1]
        self.assertEqual(last_entry["action_type"], "integration_test_action")
        self.assertEqual(last_entry["outcome"], "success")
        self.assertEqual(last_entry["trace_id"], "INTEG_TEST")

if __name__ == '__main__':
    unittest.main()
