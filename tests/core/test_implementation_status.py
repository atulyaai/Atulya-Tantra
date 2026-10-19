import asyncio

from atulya.implementation import implementation_status, implementation_tool
from tools.plugins.registry import PluginContext
from tools.plugins.toolkit import Toolbox, TOOLS


def test_work_log_keeps_unfinished_and_user_blocked_work_visible():
    data = implementation_status()
    states = {r["id"]: r["status"] for r in data["items"]}
    assert states["google"] == "waiting_for_user" and states["pc"] == "waiting_for_user"
    assert states["server-health"] == "live_verified"
    assert "Only the owner" in asyncio.run(implementation_tool({}, PluginContext("web", None, None, "other")))


def test_unconnected_hardware_is_not_reported_ready(project_temp_dir, monkeypatch):
    from tools.plugins.system import smart_home
    monkeypatch.setenv("ATULYA_DATA_DIR", str(project_temp_dir))
    monkeypatch.setattr(smart_home, "HASS_URL", "")
    monkeypatch.setattr(smart_home, "HASS_TOKEN", "")
    rows = {r["name"]: r for r in Toolbox(TOOLS, PluginContext("web", None, None)).capabilities}
    assert rows["smart_home_control"]["status"] == "needs_connection"
    assert rows["cast_to_tv"]["status"] == "needs_connection"
    assert rows["visual_inspect"]["status"] == "unsupported"
