"""Tests for automation/cron routes — job CRUD and execution."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAutomationRoutes:
    @pytest.fixture
    def mock_admin(self):
        with patch("atulya.dwar._require_admin") as m:
            m.return_value = {"username": "admin", "role": "admin"}
            yield m

    def test_list_jobs_empty(self, tmp_path, mock_admin):
        import atulya.dwar as auto_mod
        from atulya.dwar import api_cron_jobs
        auto_mod.JOBS_FILE = tmp_path / "jobs.json"

        result = api_cron_jobs(_admin=mock_admin.return_value)
        assert result["jobs"] == []

    def test_list_jobs_with_data(self, tmp_path, mock_admin):
        import atulya.dwar as auto_mod
        from atulya.dwar import api_cron_jobs
        jobs_file = tmp_path / "jobs.json"
        auto_mod.JOBS_FILE = jobs_file
        jobs_file.write_text(json.dumps([{"id": "1", "name": "test"}]))

        result = api_cron_jobs(_admin=mock_admin.return_value)
        assert len(result["jobs"]) == 1

    def test_add_job(self, tmp_path, mock_admin):
        import atulya.dwar as auto_mod
        from atulya.dwar import api_cron_add_job
        auto_mod.JOBS_FILE = tmp_path / "jobs.json"

        with patch("time.time", return_value=1000):
            result = api_cron_add_job({"name": "myjob", "schedule": "3600", "command": "say hi"}, _admin=mock_admin.return_value)

        assert result["ok"] is True
        assert result["job"]["name"] == "myjob"

    def test_add_job_rejects_invalid_schedule(self, tmp_path, mock_admin):
        import atulya.dwar as auto_mod
        from atulya.dwar import api_cron_add_job
        auto_mod.JOBS_FILE = tmp_path / "jobs.json"

        with pytest.raises(Exception) as exc:
            api_cron_add_job({"name": "bad", "schedule": "0", "command": "say hi"}, _admin=mock_admin.return_value)
        assert getattr(exc.value, "status_code", None) == 400

    def test_delete_job(self, tmp_path, mock_admin):
        import atulya.dwar as auto_mod
        from atulya.dwar import api_cron_delete_job
        jobs_file = tmp_path / "jobs.json"
        auto_mod.JOBS_FILE = jobs_file
        jobs_file.write_text(json.dumps([{"id": "1", "name": "a"}, {"id": "2", "name": "b"}]))

        result = api_cron_delete_job("1", _admin=mock_admin.return_value)
        assert result["ok"] is True
        remaining = json.loads(jobs_file.read_text())
        assert len(remaining) == 1

    def test_update_job(self, tmp_path, mock_admin):
        import atulya.dwar as auto_mod
        from atulya.dwar import api_cron_update_job
        jobs_file = tmp_path / "jobs.json"
        auto_mod.JOBS_FILE = jobs_file
        jobs_file.write_text(json.dumps([{"id": "1", "name": "old", "schedule": "3600"}]))

        result = api_cron_update_job("1", {"name": "new"}, _admin=mock_admin.return_value)
        assert result["ok"] is True
        assert result["job"]["name"] == "new"

    def test_update_job_not_found(self, tmp_path, mock_admin):
        import atulya.dwar as auto_mod
        from atulya.dwar import api_cron_update_job
        auto_mod.JOBS_FILE = tmp_path / "jobs.json"

        result = api_cron_update_job("nonexistent", {"name": "x"}, _admin=mock_admin.return_value)
        assert result["ok"] is False

    def test_run_job(self, tmp_path, mock_admin):
        import atulya.dwar as auto_mod
        from atulya.dwar import api_cron_run_job
        jobs_file = tmp_path / "jobs.json"
        auto_mod.JOBS_FILE = jobs_file
        jobs_file.write_text(json.dumps([{"id": "1", "name": "test", "command": "say hi"}]))

        mock_request = MagicMock()
        mock_request.app.state.automation_runner = None

        with patch("atulya.mastishk.get_default_llm"):
            with patch("atulya.dwar.AutomationRunner") as runner_cls:
                runner = MagicMock()
                runner.run_job = AsyncMock()
                runner.start_job = AsyncMock(return_value={"id": "1", "name": "test", "command": "say hi"})
                runner_cls.return_value = runner
                import asyncio
                result = asyncio.run(api_cron_run_job(mock_request, "1", _admin=mock_admin.return_value))

        assert result["ok"] is True


class TestAutomationLifecycle:
    @pytest.mark.asyncio
    async def test_job_completion_is_persisted(self, tmp_path):
        from types import SimpleNamespace
        from atulya.dwar import AutomationRunner

        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text(json.dumps([{"id": "job-1", "name": "test", "command": "say hi"}]))
        runner = AutomationRunner(jobs_file, llm=None)
        runner._notify_job = AsyncMock()
        kernel = SimpleNamespace(handle=AsyncMock(return_value=SimpleNamespace(
            text="finished", provider="fake", needs_approval=False, pending_tool=None)))

        with patch("atulya.buddhi.get_kernel", return_value=kernel):
            await runner.run_job({"id": "job-1", "name": "test", "command": "say hi"})

        saved = json.loads(jobs_file.read_text())[0]
        assert saved["run_status"] == "completed"
        assert saved["run_progress"] == 100
        assert saved["last_result"] == "finished"
        assert saved["run_expires_at"] > saved["run_updated_at"]

    @pytest.mark.asyncio
    async def test_cancelled_job_persists_cancelled_state(self, tmp_path):
        import asyncio
        from types import SimpleNamespace
        from atulya.dwar import AutomationRunner

        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text(json.dumps([{"id": "job-2", "name": "test", "command": "wait"}]))
        runner = AutomationRunner(jobs_file, llm=None)
        runner._notify_job = AsyncMock()
        started = asyncio.Event()

        async def wait_forever(*_args, **_kwargs):
            started.set()
            await asyncio.Future()

        kernel = SimpleNamespace(handle=wait_forever)
        with patch("atulya.buddhi.get_kernel", return_value=kernel):
            await runner.start_job({"id": "job-2", "name": "test", "command": "wait"})
            await started.wait()
            saved = await runner.cancel_job("job-2")

        assert saved["run_status"] == "cancelled"
        assert saved["last_error"] == "Cancelled by owner"

    def test_expired_run_metadata_is_removed_but_job_is_kept(self, tmp_path, monkeypatch):
        import atulya.dwar as auto_mod

        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text(json.dumps([{
            "id": "job-3", "name": "keep me", "command": "say hi",
            "run_status": "completed", "run_progress": 100, "run_expires_at": 50,
            "last_result": "old result",
        }]))
        monkeypatch.setattr(auto_mod, "JOBS_FILE", jobs_file)
        with patch("time.time", return_value=100):
            jobs = auto_mod._load_jobs()

        assert jobs == [{"id": "job-3", "name": "keep me", "command": "say hi"}]

    @pytest.mark.asyncio
    async def test_restart_marks_running_job_interrupted_without_replaying(self, tmp_path):
        from atulya.dwar import AutomationRunner

        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text(json.dumps([{
            "id": "job-4", "name": "maybe ran", "command": "turn off lights",
            "schedule": "60", "enabled": True, "next_run": 1, "run_status": "running",
        }]))
        runner = AutomationRunner(jobs_file, llm=None)
        with patch("time.time", return_value=1000):
            await runner.tick()

        saved = json.loads(jobs_file.read_text())[0]
        assert saved["run_status"] == "interrupted"
        assert saved["next_run"] == 1060
        assert "not replayed" in saved["last_error"]
        assert saved.get("run_count", 0) == 0

    def test_seed_default_jobs(self, tmp_path):
        import atulya.dwar as auto_mod
        from atulya.dwar import _seed_default_jobs
        jobs_file = tmp_path / "jobs.json"
        auto_mod.JOBS_FILE = jobs_file

        _seed_default_jobs()
        seeded = json.loads(jobs_file.read_text())
        assert len(seeded) == 2
        assert seeded[0]["enabled"] is True
        assert all(job.get("command") for job in seeded)

    def test_seed_default_jobs_idempotent(self, tmp_path):
        import atulya.dwar as auto_mod
        from atulya.dwar import _seed_default_jobs
        jobs_file = tmp_path / "jobs.json"
        auto_mod.JOBS_FILE = jobs_file
        jobs_file.write_text(json.dumps([{"id": "custom", "name": "mine"}]))

        _seed_default_jobs()
        preserved = json.loads(jobs_file.read_text())
        assert len(preserved) == 1
        assert preserved[0]["id"] == "custom"
