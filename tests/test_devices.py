"""Tests for devices route — CRUD and command dispatch."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestDevices:
    @pytest.fixture
    def mock_auth(self):
        with patch("drishti.dashboard.routes.devices._require_auth") as m:
            m.return_value = {"username": "testuser"}
            yield m

    @pytest.fixture
    def mock_controller(self):
        ctrl = MagicMock()
        ctrl._devices = {}
        ctrl.add_device.return_value = "dev_abc123"
        ctrl.send_command = AsyncMock()
        ctrl.get_stats.return_value = {"total_devices": 0, "by_protocol": {}}
        ctrl._save = MagicMock()
        with patch("drishti.dashboard.routes.devices._controller", ctrl):
            yield ctrl

    def test_list_devices_empty(self, mock_auth, mock_controller):
        from drishti.dashboard.routes.devices import list_devices
        result = list_devices(token="t")
        assert result["devices"] == []

    def test_list_devices_with_data(self, mock_auth, mock_controller):
        from drishti.dashboard.routes.devices import list_devices
        mock_controller._devices["d1"] = MagicMock()
        mock_controller._devices["d1"].__dict__ = {"id": "d1", "name": "TV"}
        result = list_devices(token="t")
        assert len(result["devices"]) == 1

    def test_add_device(self, mock_auth, mock_controller):
        from drishti.dashboard.routes.devices import add_device
        result = add_device({"name": "TV", "device_type": "tv", "protocol": "ir"}, token="t")
        assert result["ok"] is True
        assert result["device_id"] == "dev_abc123"
        mock_controller.add_device.assert_called_once_with("TV", "tv", "ir", "", 0)

    def test_add_device_no_name(self, mock_auth, mock_controller):
        from drishti.dashboard.routes.devices import add_device
        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="name"):
            add_device({"device_type": "tv"}, token="t")

    def test_device_stats(self, mock_auth, mock_controller):
        from drishti.dashboard.routes.devices import device_stats
        result = device_stats(token="t")
        assert result["total_devices"] == 0

    def test_delete_device(self, mock_auth, mock_controller):
        from drishti.dashboard.routes.devices import delete_device
        mock_controller._devices["d1"] = MagicMock()
        result = delete_device("d1", token="t")
        assert result["ok"] is True
        assert "d1" not in mock_controller._devices

    def test_delete_device_not_found(self, mock_auth, mock_controller):
        from drishti.dashboard.routes.devices import delete_device
        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="not found"):
            delete_device("nonexistent", token="t")

    def test_send_command(self, mock_auth, mock_controller):
        from drishti.dashboard.routes.devices import send_command
        import asyncio
        mock_controller.send_command.return_value = {"success": True, "output": "ok"}
        result = asyncio.run(send_command("d1", {"command": "power_on"}, token="t"))
        assert result["success"] is True

    def test_send_command_no_cmd(self, mock_auth, mock_controller):
        from drishti.dashboard.routes.devices import send_command
        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="(?i)command"):
            import asyncio
            asyncio.run(send_command("d1", {}, token="t"))


try:
    from unittest.mock import AsyncMock
except ImportError:
    class AsyncMock(MagicMock):
        async def __call__(self, *args, **kwargs):
            return super().__call__(*args, **kwargs)
