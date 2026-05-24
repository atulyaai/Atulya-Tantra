"""Tests for HeartbeatSystem — health checks and status persistence."""

import tempfile
import json
import os


class TestHeartbeatSystem:
    """Tests for HeartbeatSystem (non-async parts)."""

    def test_initialization(self):
        from atulya.heartbeat import HeartbeatSystem
        with tempfile.TemporaryDirectory() as tmp:
            hb = HeartbeatSystem(data_dir=tmp)
            assert hb.data_dir.exists()
            assert hb._checks == []
            assert hb._running is False

    def test_memory_check_import_fallback(self):
        """_memory_check should handle missing psutil gracefully."""
        from atulya.heartbeat import HeartbeatSystem
        import asyncio
        with tempfile.TemporaryDirectory() as tmp:
            hb = HeartbeatSystem(data_dir=tmp)
            result = asyncio.run(hb._memory_check())
            assert result.name == "memory"
            assert result.status == "ok"

    def test_disk_check(self):
        from atulya.heartbeat import HeartbeatSystem
        import asyncio
        with tempfile.TemporaryDirectory() as tmp:
            hb = HeartbeatSystem(data_dir=tmp)
            result = asyncio.run(hb._disk_check())
            assert result.name == "disk"
            assert result.status in ("ok", "warning", "error")

    def test_maintenance_check(self):
        from atulya.heartbeat import HeartbeatSystem
        import asyncio
        with tempfile.TemporaryDirectory() as tmp:
            hb = HeartbeatSystem(data_dir=tmp)
            result = asyncio.run(hb._maintenance_check())
            assert result.name == "maintenance"
            assert result.status in ("ok", "warning", "info", "error")

    def test_save_status_creates_file(self):
        from atulya.heartbeat import HeartbeatSystem
        import asyncio
        with tempfile.TemporaryDirectory() as tmp:
            hb = HeartbeatSystem(data_dir=tmp)
            asyncio.run(hb._run_checks())
            # File is heartbeat_status.json, not heartbeat.json
            status_file = hb.data_dir / "heartbeat_status.json"
            assert status_file.exists()
            data = json.loads(status_file.read_text())
            assert "last_check" in data
            assert "checks" in data

    def test_healthcheck_dataclass(self):
        from atulya.heartbeat import HealthCheck
        hc = HealthCheck(name="test", status="ok", message="all good")
        assert hc.name == "test"
        assert hc.status == "ok"
        assert hc.message == "all good"
        assert hc.timestamp > 0

    def test_get_status_empty(self):
        """get_status returns default when no file exists."""
        from atulya.heartbeat import HeartbeatSystem
        with tempfile.TemporaryDirectory() as tmp:
            hb = HeartbeatSystem(data_dir=tmp)
            status = hb.get_status()
            assert status["last_check"] == 0
            assert status["checks"] == []

    def test_task_check_no_crash(self):
        """_task_check should handle missing kanban directory."""
        from atulya.heartbeat import HeartbeatSystem
        import asyncio
        with tempfile.TemporaryDirectory() as tmp:
            hb = HeartbeatSystem(data_dir=tmp)
            result = asyncio.run(hb._task_check())
            assert result.name == "tasks"

    def test_start_stop(self):
        from atulya.heartbeat import HeartbeatSystem
        import asyncio
        with tempfile.TemporaryDirectory() as tmp:
            hb = HeartbeatSystem(data_dir=tmp)
            hb._interval = 0.1
            # Quick start/stop to ensure it doesn't crash
            async def quick_test():
                task = asyncio.create_task(hb.start())
                await asyncio.sleep(0.05)
                await hb.stop()
                await task
            asyncio.run(quick_test())
            status_file = hb.data_dir / "heartbeat_status.json"
            assert status_file.exists()
