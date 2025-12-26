import unittest
import os
import json
import shutil
from pathlib import Path
from core.action_ledger import ActionLedger

class TestActionLedger(unittest.TestCase):
    def setUp(self):
        self.test_path = "memory/test_ledger.json"
        if os.path.exists(self.test_path):
            os.remove(self.test_path)
        self.ledger = ActionLedger(self.test_path)

    def tearDown(self):
        if os.path.exists(self.test_path):
            os.remove(self.test_path)
        if os.path.exists(self.test_path + ".corrupted"):
            os.remove(self.test_path + ".corrupted")

    def test_record_outcome(self):
        self.ledger.record_outcome("test_action", "success", "context", 0.9)
        self.assertEqual(len(self.ledger.entries), 1)
        entry = self.ledger.entries[0]
        self.assertEqual(entry["action_type"], "test_action")
        self.assertEqual(entry["outcome"], "success")
        self.assertEqual(entry["confidence"], 0.9)
        self.assertTrue(os.path.exists(self.test_path))

    def test_persistence_reload(self):
        self.ledger.record_outcome("persist", "success")
        
        # New instance, same path
        new_ledger = ActionLedger(self.test_path)
        self.assertEqual(len(new_ledger.entries), 1)
        self.assertEqual(new_ledger.entries[0]["action_type"], "persist")

    def test_success_rate(self):
        self.ledger.record_outcome("type_a", "success")
        self.ledger.record_outcome("type_a", "failure")
        self.ledger.record_outcome("type_a", "success")
        self.ledger.record_outcome("type_b", "failure")
        
        rate_a = self.ledger.get_success_rate("type_a")
        rate_b = self.ledger.get_success_rate("type_b")
        rate_c = self.ledger.get_success_rate("type_c") # No history
        
        self.assertAlmostEqual(rate_a, 0.6666, places=2)
        self.assertEqual(rate_b, 0.0)
        self.assertEqual(rate_c, 0.0)

    def test_corruption_recovery(self):
        # Create corrupted file
        with open(self.test_path, 'w') as f:
            f.write("{ INVALID JSON ")
            
        # Init should backup and reset
        recovered = ActionLedger(self.test_path)
        self.assertEqual(len(recovered.entries), 0)
        self.assertTrue(os.path.exists(self.test_path + ".corrupted"))

if __name__ == '__main__':
    unittest.main()
