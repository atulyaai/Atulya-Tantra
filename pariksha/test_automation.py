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
                runner_cls.return_value = runner
                import asyncio
                result = asyncio.run(api_cron_run_job(mock_request, "1", _admin=mock_admin.return_value))

        assert result["ok"] is True

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
