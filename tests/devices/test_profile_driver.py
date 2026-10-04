import asyncio

import pytest

from atulya.devices.base import DeviceError, DeviceRecord, is_lan_host
from atulya.devices.profile_driver import ProfileDriver, load_profiles, validate_profile
from tests.devices import sims


@pytest.fixture(autouse=True)
def loopback(monkeypatch):
    monkeypatch.setenv("ATULYA_DEVICES_ALLOW_LOOPBACK", "on")


def run(c):
    return asyncio.run(c)


def device(profile, sim, name="Dev"):
    return DeviceRecord(id="d1", name=name, kind="tv", driver="profile", address="127.0.0.1", config={"profile": profile, "port": sim.port})


def test_every_shipped_profile_is_valid():
    profiles = load_profiles()
    assert {"roku", "tasmota", "wled", "shelly", "kodi"} <= set(profiles)
    for p in profiles.values():
        validate_profile(p)


def test_roku_keys_and_repeat():
    drv = ProfileDriver()
    with sims.roku() as sim:
        d = device("roku", sim)
        assert "power off" in run(drv.execute(d, "power_off", {}))
        run(drv.execute(d, "volume_up", {"times": 3}))
        run(drv.execute(d, "launch_app_id", {"app_id": "12"}))
    assert [(r["method"], r["path"]) for r in sim.requests] == [
        ("POST", "/keypress/PowerOff"), ("POST", "/keypress/VolumeUp"), ("POST", "/keypress/VolumeUp"), ("POST", "/keypress/VolumeUp"),
        ("POST", "/launch/12")]


def test_json_bodies_keep_their_types_and_ranges_are_enforced():
    drv = ProfileDriver()
    with sims.wled() as sim:
        d = device("wled", sim)
        run(drv.execute(d, "set_brightness", {"value": "128"}))
        run(drv.execute(d, "power_off", {}))
        with pytest.raises(DeviceError, match="between"):
            run(drv.execute(d, "set_brightness", {"value": 999}))
        with pytest.raises(DeviceError, match="integer"):
            run(drv.execute(d, "set_brightness", {"value": "very bright"}))
        with pytest.raises(DeviceError, match="I need value"):
            run(drv.execute(d, "set_brightness", {}))
    assert sim.requests[0]["json"] == {"on": True, "bri": 128} and isinstance(sim.requests[0]["json"]["bri"], int)
    assert sim.requests[1]["json"] == {"on": False} and len(sim.requests) == 2    # bad values never reached the device


def test_tasmota_kodi_shelly_paths():
    drv = ProfileDriver()
    with sims.tasmota() as t, sims.kodi() as k, sims.shelly() as s:
        run(drv.execute(device("tasmota", t), "power_on", {}))
        run(drv.execute(device("tasmota", t), "set_brightness", {"value": 40}))
        run(drv.execute(device("kodi", k), "set_volume", {"value": 30}))
        run(drv.execute(device("shelly", s), "toggle", {}))
    assert [r["path"] for r in t.requests] == ["/cm?cmnd=Power%20On", "/cm?cmnd=Dimmer%2040"]
    assert k.requests[0]["json"]["params"] == {"volume": 30} and s.requests[0]["path"] == "/relay/0?turn=toggle"


def test_unknown_capability_and_offline_device_say_so():
    drv = ProfileDriver()
    with sims.roku() as sim:
        d = device("roku", sim)
        with pytest.raises(DeviceError, match="can't “fly”"):
            run(drv.execute(d, "fly", {}))
    d.config["port"] = 1                                                  # nothing listens there
    with pytest.raises(DeviceError, match="couldn't reach"):
        run(drv.execute(d, "power_off", {}))


def test_http_errors_are_reported():
    with sims.Sim({("POST", "/keypress/"): (500, "boom")}) as sim:
        with pytest.raises(DeviceError, match="answered 500"):
            run(ProfileDriver().execute(device("roku", sim), "power_off", {}))


def test_only_lan_devices_get_commands(monkeypatch):
    monkeypatch.delenv("ATULYA_DEVICES_ALLOW_LOOPBACK")
    assert is_lan_host("192.168.1.20") and is_lan_host("10.0.0.5") and is_lan_host("tv.local")
    assert not is_lan_host("8.8.8.8") and not is_lan_host("") and not is_lan_host("127.0.0.1")
    d = DeviceRecord(id="x", name="Far TV", kind="tv", driver="profile", address="8.8.8.8", config={"profile": "roku"})
    with pytest.raises(DeviceError, match="not on your home network"):
        run(ProfileDriver().execute(d, "power_off", {}))


def test_profile_validation_rejects_dangerous_or_sloppy_profiles():
    base = {"id": "x", "capabilities": {"go": {"request": {"method": "GET", "path": "/ok"}}}}
    validate_profile(base)
    bad = [
        {**base, "id": "Bad Id!"},
        {**base, "port": 70000},
        {**base, "scheme": "ftp"},
        {**base, "capabilities": {}},
        {**base, "capabilities": {"go": {"request": {"method": "GET", "path": "http://evil.example/steal"}}}},
        {**base, "capabilities": {"go": {"request": {"method": "GET", "path": "//evil.example/x"}}}},
        {**base, "capabilities": {"go": {"request": {"method": "GET", "path": "/a/../../etc"}}}},
        {**base, "capabilities": {"go": {"request": {"method": "TRACE", "path": "/x"}}}},
        {**base, "capabilities": {"go": {"request": {"method": "GET", "path": "/x/{secret}"}}}},
        {**base, "capabilities": {"go": {"requests": [{"path": "/x"}] * 9}}},
        "not a dict",
    ]
    for profile in bad:
        with pytest.raises(DeviceError):
            validate_profile(profile)


def test_a_string_parameter_cannot_escape_its_path():
    profile = {"id": "p", "port": 1, "capabilities": {"open": {"params": {"name": {"type": "string"}},
               "request": {"method": "GET", "path": "/apps/{name}"}}}}
    with sims.Sim({("GET", "/apps/"): (200, "ok")}) as sim:
        d = DeviceRecord(id="d", name="D", kind="tv", driver="profile", address="127.0.0.1", config={"profile": "p", "port": sim.port})
        run(ProfileDriver({"p": profile}).execute(d, "open", {"name": "../../admin?x=1&y=2"}))
    assert sim.requests[0]["path"] == "/apps/..%2F..%2Fadmin%3Fx%3D1%26y%3D2"
