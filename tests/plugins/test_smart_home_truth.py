import asyncio

from tools.plugins.system import smart_home


def test_without_home_assistant_nothing_is_claimed(monkeypatch):
    monkeypatch.setattr(smart_home, "HASS_URL", "")
    monkeypatch.setattr(smart_home, "HASS_TOKEN", "")
    for device, action in (("desk lamp", "on"), ("lights", "movie"), ("movie", "on")):
        reply = asyncio.run(smart_home.execute_smart_home(device, action))
        assert "not connected" in reply and "nothing was changed" in reply
        assert "Triggered" not in reply and "dispatched" not in reply
