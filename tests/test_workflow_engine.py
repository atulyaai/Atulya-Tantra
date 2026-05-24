"""Tests for WorkflowEngine — multi-step task orchestration."""

import pytest
import tempfile
import asyncio


class TestWorkflowEngine:
    """Tests for WorkflowEngine task creation, execution, and stats."""

    def _make_engine(self):
        """Create a WorkflowEngine with a temp directory."""
        from yantra.tools.workflow_engine import WorkflowEngine
        import tempfile
        tmp = tempfile.mkdtemp()
        return WorkflowEngine(data_dir=tmp), tmp

    def test_create_task(self):
        from yantra.tools.workflow_engine import WorkflowEngine
        engine, tmp = self._make_engine()
        try:
            tid = engine.create_task("test-task")
            assert tid is not None
            assert len(tid) > 0
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_create_task_with_tool(self):
        from yantra.tools.workflow_engine import WorkflowEngine
        engine, tmp = self._make_engine()
        try:
            tid = engine.create_task("calc-task", tool_name="calculator", tool_args={"expr": "2+2"})
            assert tid is not None
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_get_task(self):
        from yantra.tools.workflow_engine import WorkflowEngine
        engine, tmp = self._make_engine()
        try:
            tid = engine.create_task("test-task")
            task = engine.get_task(tid)
            assert task is not None
            assert task.title == "test-task"
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_get_task_not_found(self):
        from yantra.tools.workflow_engine import WorkflowEngine
        engine, tmp = self._make_engine()
        try:
            assert engine.get_task("nonexistent") is None
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_create_workflow(self):
        from yantra.tools.workflow_engine import WorkflowEngine
        engine, tmp = self._make_engine()
        try:
            t1 = engine.create_task("step1")
            t2 = engine.create_task("step2")
            wid = engine.create_workflow("test-flow", [t1, t2])
            assert wid is not None
            assert len(wid) > 0
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_get_workflow(self):
        from yantra.tools.workflow_engine import WorkflowEngine
        engine, tmp = self._make_engine()
        try:
            t1 = engine.create_task("step1")
            wid = engine.create_workflow("test-flow", [t1])
            wf = engine.get_workflow(wid)
            assert wf is not None
            assert isinstance(wf, list)
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_execute_task_simple(self):
        from yantra.tools.workflow_engine import WorkflowEngine
        engine, tmp = self._make_engine()
        try:
            tid = engine.create_task("simple-task")
            result = asyncio.run(engine.execute_task(tid))
            assert result is not None
            assert result.status.value in ("done", "in_progress", "todo")
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_execute_workflow(self):
        from yantra.tools.workflow_engine import WorkflowEngine
        engine, tmp = self._make_engine()
        try:
            t1 = engine.create_task("a")
            t2 = engine.create_task("b")
            wid = engine.create_workflow("test-flow", [t1, t2])
            results = asyncio.run(engine.execute_workflow(wid))
            assert results is not None
            assert isinstance(results, list)
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_execute_task_not_found_raises(self):
        from yantra.tools.workflow_engine import WorkflowEngine
        engine, tmp = self._make_engine()
        try:
            with pytest.raises(ValueError):
                asyncio.run(engine.execute_task("nonexistent"))
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_get_blocked_tasks(self):
        from yantra.tools.workflow_engine import WorkflowEngine
        engine, tmp = self._make_engine()
        try:
            blocked = engine.get_blocked_tasks()
            assert isinstance(blocked, list)
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_get_pending_tasks(self):
        from yantra.tools.workflow_engine import WorkflowEngine
        engine, tmp = self._make_engine()
        try:
            pending = engine.get_pending_tasks()
            assert isinstance(pending, list)
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_get_stats(self):
        from yantra.tools.workflow_engine import WorkflowEngine
        engine, tmp = self._make_engine()
        try:
            engine.create_task("task1")
            engine.create_task("task2")
            engine.create_task("task3")
            stats = engine.get_stats()
            assert isinstance(stats, dict)
            assert stats["total_tasks"] == 3
            assert stats["workflows"] >= 0
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_get_stats_empty(self):
        from yantra.tools.workflow_engine import WorkflowEngine
        engine, tmp = self._make_engine()
        try:
            stats = engine.get_stats()
            assert stats["total_tasks"] == 0
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_task_dependencies_block(self):
        from yantra.tools.workflow_engine import WorkflowEngine
        engine, tmp = self._make_engine()
        try:
            t1 = engine.create_task("dep-a")
            t2 = engine.create_task("dep-b", dependencies=[t1])
            result = asyncio.run(engine.execute_task(t2))
            # t2 should be blocked because t1 is still TODO
            assert result.status.value == "blocked"
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)
