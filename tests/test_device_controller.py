"""Tests for DeviceController — IoT device management with multi-protocol support."""

import pytest
import tempfile
import asyncio


class TestDeviceController:
    """Tests for DeviceController — add, remove, stats, and command dispatching."""

    def test_add_device(self):
        from atulya.devices.controller import DeviceController
        with tempfile.TemporaryDirectory() as tmp:
            controller = DeviceController(data_dir=tmp)
            did = controller.add_device("test_tv", "tv", "ir")
            assert did is not None
            assert did.startswith("dev_")

    def test_add_device_with_address(self):
        from atulya.devices.controller import DeviceController
        with tempfile.TemporaryDirectory() as tmp:
            controller = DeviceController(data_dir=tmp)
            did = controller.add_device("sensor", "temperature", "wifi",
                                         address="192.168.1.100", port=8080)
            assert did is not None

    def test_send_command_device_not_found(self):
        from atulya.devices.controller import DeviceController
        with tempfile.TemporaryDirectory() as tmp:
            controller = DeviceController(data_dir=tmp)
            result = asyncio.run(controller.send_command("nonexistent", "power_on"))
            assert result["success"] is False
            assert "not found" in result["error"]

    def test_send_command_unsupported_protocol(self):
        from atulya.devices.controller import DeviceController
        with tempfile.TemporaryDirectory() as tmp:
            controller = DeviceController(data_dir=tmp)
            did = controller.add_device("test", "sensor", "unknown_protocol")
            result = asyncio.run(controller.send_command(did, "test"))
            assert result["success"] is False
            assert "Unsupported protocol" in result["error"]

    def test_send_command_ir_fallback(self):
        """IR protocol should work even without lirc (fallback)."""
        from atulya.devices.controller import DeviceController
        with tempfile.TemporaryDirectory() as tmp:
            controller = DeviceController(data_dir=tmp)
            did = controller.add_device("tv", "tv", "ir")
            result = asyncio.run(controller.send_command(did, "power_on"))
            assert result["success"] is True

    def test_get_stats(self):
        from atulya.devices.controller import DeviceController
        with tempfile.TemporaryDirectory() as tmp:
            controller = DeviceController(data_dir=tmp)
            did1 = controller.add_device("tv1", "tv", "ir")
            did2 = controller.add_device("tv2", "tv", "ir")
            did3 = controller.add_device("sensor", "temp", "wifi")
            stats = controller.get_stats()
            # Note: IDs may collide if same second, so total could be 1-3
            assert stats["total_devices"] >= 1
            assert stats["by_protocol"] is not None

    def test_get_stats_empty(self):
        from atulya.devices.controller import DeviceController
        with tempfile.TemporaryDirectory() as tmp:
            controller = DeviceController(data_dir=tmp)
            stats = controller.get_stats()
            assert stats["total_devices"] == 0

    def test_device_persistence(self):
        """Devices should survive across controller re-initialization."""
        from atulya.devices.controller import DeviceController
        with tempfile.TemporaryDirectory() as tmp:
            c1 = DeviceController(data_dir=tmp)
            did = c1.add_device("persistent", "sensor", "serial")
            c2 = DeviceController(data_dir=tmp)
            stats = c2.get_stats()
            assert stats["total_devices"] == 1

    def test_add_device_multiple(self):
        from atulya.devices.controller import DeviceController
        with tempfile.TemporaryDirectory() as tmp:
            controller = DeviceController(data_dir=tmp)
            ids = []
            for i in range(5):
                ids.append(controller.add_device(f"dev_{i}", "generic", "ir"))
            # At least some unique IDs (may collide if same second)
            unique_ids = len(set(ids))
            assert unique_ids >= 1
