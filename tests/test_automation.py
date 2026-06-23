"""Tests for automation/cron routes — job CRUD and execution."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAutomationRoutes:
    @pytest.fixture
    def mock_admin(self):
        with patch("drishti.dashboard.routes.automation._require_admin") as m:
            m.return_value = {"username": "admin", "role": "admin"}
            yield m

    def test_list_jobs_empty(self, tmp_path, mock_admin):
        from drishti.dashboard.routes.automation import JOBS_FILE, api_cron_jobs
        import drishti.dashboard.routes.automation as auto_mod
        auto_mod.JOBS_FILE = tmp_path / "jobs.json"

        result = api_cron_jobs(_admin=mock_admin.return_value)
        assert result["jobs"] == []

    def test_list_jobs_with_data(self, tmp_path, mock_admin):
        from drishti.dashboard.routes.automation import api_cron_jobs
        import drishti.dashboard.routes.automation as auto_mod
        jobs_file = tmp_path / "jobs.json"
        auto_mod.JOBS_FILE = jobs_file
        jobs_file.write_text(json.dumps([{"id": "1", "name": "test"}]))

        result = api_cron_jobs(_admin=mock_admin.return_value)
        assert len(result["jobs"]) == 1

    def test_add_job(self, tmp_path, mock_admin):
        from drishti.dashboard.routes.automation import JOBS_FILE, api_cron_add_job
        import drishti.dashboard.routes.automation as auto_mod
        auto_mod.JOBS_FILE = tmp_path / "jobs.json"

        with patch("time.time", return_value=1000):
            result = api_cron_add_job({"name": "myjob", "schedule": "3600", "command": "say hi"}, _admin=mock_admin.return_value)

        assert result["ok"] is True
        assert result["job"]["name"] == "myjob"

    def test_delete_job(self, tmp_path, mock_admin):
        from drishti.dashboard.routes.automation import api_cron_delete_job
        import drishti.dashboard.routes.automation as auto_mod
        jobs_file = tmp_path / "jobs.json"
        auto_mod.JOBS_FILE = jobs_file
        jobs_file.write_text(json.dumps([{"id": "1", "name": "a"}, {"id": "2", "name": "b"}]))

        result = api_cron_delete_job("1", _admin=mock_admin.return_value)
        assert result["ok"] is True
        remaining = json.loads(jobs_file.read_text())
        assert len(remaining) == 1

    def test_update_job(self, tmp_path, mock_admin):
        from drishti.dashboard.routes.automation import api_cron_update_job
        import drishti.dashboard.routes.automation as auto_mod
        jobs_file = tmp_path / "jobs.json"
        auto_mod.JOBS_FILE = jobs_file
        jobs_file.write_text(json.dumps([{"id": "1", "name": "old", "schedule": "3600"}]))

        result = api_cron_update_job("1", {"name": "new"}, _admin=mock_admin.return_value)
        assert result["ok"] is True
        assert result["job"]["name"] == "new"

    def test_update_job_not_found(self, tmp_path, mock_admin):
        from drishti.dashboard.routes.automation import api_cron_update_job
        import drishti.dashboard.routes.automation as auto_mod
        auto_mod.JOBS_FILE = tmp_path / "jobs.json"

        result = api_cron_update_job("nonexistent", {"name": "x"}, _admin=mock_admin.return_value)
        assert result["ok"] is False

    def test_run_job(self, tmp_path, mock_admin):
        from drishti.dashboard.routes.automation import api_cron_run_job
        import drishti.dashboard.routes.automation as auto_mod
        jobs_file = tmp_path / "jobs.json"
        auto_mod.JOBS_FILE = jobs_file
        jobs_file.write_text(json.dumps([{"id": "1", "name": "test", "command": "say hi"}]))

        mock_request = MagicMock()
        mock_request.app.state.automation_runner = None

        with patch("atulya.llm.get_default_llm") as llm:
            with patch("drishti.dashboard.automation_runner.AutomationRunner") as runner_cls:
                runner = MagicMock()
                runner.run_job = AsyncMock()
                runner_cls.return_value = runner
                import asyncio
                result = asyncio.run(api_cron_run_job(mock_request, "1", _admin=mock_admin.return_value))

        assert result["ok"] is True
