"""Tests for SelfRepairSystem and CodeEvolver â€” automatic error recovery and evolution."""

import tempfile
import traceback


class TestSelfRepairSystem:
    """Tests for SelfRepairSystem â€” analyze errors and apply fixes."""

    def test_analyze_error(self):
        from yantra.selfrepair import SelfRepairSystem
        with tempfile.TemporaryDirectory() as tmp:
            repair = SelfRepairSystem(data_dir=tmp)
            error = ValueError("invalid input")
            tb = traceback.extract_stack()
            action = repair.analyze_error(error, tb)
            assert action is not None
            assert action.issue_type == "ValueError"
            assert "invalid input" in action.description

    def test_analyze_error_no_traceback(self):
        from yantra.selfrepair import SelfRepairSystem
        with tempfile.TemporaryDirectory() as tmp:
            repair = SelfRepairSystem(data_dir=tmp)
            action = repair.analyze_error(ModuleNotFoundError("No module named 'nonexistent'"))
            assert action is not None
            assert action.issue_type == "ModuleNotFoundError"

    def test_analyze_error_runtime(self):
        from yantra.selfrepair import SelfRepairSystem
        with tempfile.TemporaryDirectory() as tmp:
            repair = SelfRepairSystem(data_dir=tmp)
            try:
                1 / 0
            except ZeroDivisionError as e:
                tb = traceback.extract_tb(e.__traceback__)
                action = repair.analyze_error(e, tb)
                assert action.issue_type == "ZeroDivisionError"

    def test_apply_fix_no_file(self):
        from yantra.selfrepair import SelfRepairSystem
        with tempfile.TemporaryDirectory() as tmp:
            repair = SelfRepairSystem(data_dir=tmp)
            success = repair.apply_fix("/nonexistent/file.py", "ModuleNotFoundError: pip install requests")
            assert success is False

    def test_apply_fix_adds_import(self):
        from yantra.selfrepair import SelfRepairSystem
        with tempfile.TemporaryDirectory() as tmp:
            repair = SelfRepairSystem(data_dir=tmp)
            test_file = f"{tmp}/test_mod.py"
            with open(test_file, "w") as f:
                f.write("x = 1\n")
            success = repair.apply_fix(test_file, "ModuleNotFoundError: pip install requests")
            content = open(test_file).read()
            assert "import requests" in content
            assert success is True

    def test_get_repair_history_empty(self):
        from yantra.selfrepair import SelfRepairSystem
        with tempfile.TemporaryDirectory() as tmp:
            repair = SelfRepairSystem(data_dir=tmp)
            history = repair.get_repair_history()
            assert isinstance(history, list)
            assert len(history) == 0

    def test_get_stats(self):
        from yantra.selfrepair import SelfRepairSystem
        with tempfile.TemporaryDirectory() as tmp:
            repair = SelfRepairSystem(data_dir=tmp)
            repair.analyze_error(ValueError("bad"))
            repair.analyze_error(KeyError("missing"))
            stats = repair.get_stats()
            assert isinstance(stats, dict)
            assert stats["total_repairs"] == 2
            assert stats["by_type"]["ValueError"] == 1
            assert stats["by_type"]["KeyError"] == 1

    def test_multiple_repairs_tracked(self):
        from yantra.selfrepair import SelfRepairSystem
        with tempfile.TemporaryDirectory() as tmp:
            repair = SelfRepairSystem(data_dir=tmp)
            repair.analyze_error(ValueError("a"))
            repair.analyze_error(TypeError("b"))
            repair.analyze_error(KeyError("c"))
            history = repair.get_repair_history()
            assert len(history) == 3

    def test_repair_persistence(self):
        """Repair log should persist across re-initialization."""
        from yantra.selfrepair import SelfRepairSystem
        with tempfile.TemporaryDirectory() as tmp:
            r1 = SelfRepairSystem(data_dir=tmp)
            r1.analyze_error(ValueError("persist"))
            r2 = SelfRepairSystem(data_dir=tmp)
            assert r2.get_stats()["total_repairs"] == 1


class TestCodeEvolver:
    """Tests for CodeEvolver â€” architecture evolution and change proposals."""

    def test_propose_change(self):
        from yantra.selfrepair import CodeEvolver
        with tempfile.TemporaryDirectory() as tmp:
            evolver = CodeEvolver(base_dir=tmp)
            proposal = evolver.propose_change("mod.py", "old_code", "new_code", "Performance improvement")
            assert proposal is not None
            assert proposal["file"] == "mod.py"
            assert proposal["reason"] == "Performance improvement"
            assert proposal["approved"] is False

    def test_apply_change_unapproved(self):
        from yantra.selfrepair import CodeEvolver
        with tempfile.TemporaryDirectory() as tmp:
            evolver = CodeEvolver(base_dir=tmp)
            proposal = evolver.propose_change("mod.py", "old_code", "new_code", "fix")
            result = evolver.apply_change(proposal["id"])
            assert result is False  # Not approved

    def test_apply_change_approved(self):
        from yantra.selfrepair import CodeEvolver
        with tempfile.TemporaryDirectory() as tmp:
            test_file = f"{tmp}/mod.py"
            with open(test_file, "w") as f:
                f.write("OLD CODE")
            evolver = CodeEvolver(base_dir=tmp)
            proposal = evolver.propose_change("mod.py", "OLD CODE", "NEW CODE", "update")
            # Manually approve
            proposal["approved"] = True
            result = evolver.apply_change(proposal["id"])
            assert result is True
            assert open(test_file).read() == "NEW CODE"

    def test_get_stats(self):
        from yantra.selfrepair import CodeEvolver
        with tempfile.TemporaryDirectory() as tmp:
            evolver = CodeEvolver(base_dir=tmp)
            evolver.propose_change("a.py", "a", "b", "fix1")
            evolver.propose_change("b.py", "c", "d", "fix2")
            stats = evolver.get_stats()
            assert isinstance(stats, dict)
            assert stats["proposals"] == 2
