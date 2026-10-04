import asyncio
import json
import socket
import stat
import sys
import threading

import httpx
import pytest

from atulya.upakaran import adb as adbmod
from atulya.upakaran.adb import AdbDriver
from atulya.upakaran.base import DeviceError, DeviceRecord
from atulya.upakaran.ha import HomeAssistantDriver
from atulya.upakaran.wol import WolDriver, magic_packet
from tests.upakaran import sims


@pytest.fixture(autouse=True)
def loopback(monkeypatch):
    monkeypatch.setenv("ATULYA_DEVICES_ALLOW_LOOPBACK", "on")


def run(c):
    return asyncio.run(c)


# ── Wake-on-LAN ──────────────────────────────────────────────────────────────────────────────
def test_magic_packet_is_exact():
    p = magic_packet("AA:BB:CC:DD:EE:FF")
    assert len(p) == 102 and p[:6] == b"\xff" * 6 and p[6:12] == bytes.fromhex("AABBCCDDEEFF") and p[6:] == bytes.fromhex("AABBCCDDEEFF") * 16
    for bad in ("", "AA:BB", "ZZ:BB:CC:DD:EE:FF", "AABBCCDDEEFF"):
        with pytest.raises(DeviceError):
            magic_packet(bad)


def test_wol_sends_the_packet_over_a_real_udp_socket():
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("127.0.0.1", 0))
    rx.settimeout(3)
    port = rx.getsockname()[1]
    got = []
    t = threading.Thread(target=lambda: got.append(rx.recvfrom(2048)[0]))
    t.start()
    d = DeviceRecord(id="p", name="Desktop", kind="pc", driver="wol", config={"mac": "01-23-45-67-89-ab", "broadcast": "127.0.0.1", "wol_port": port})
    assert "wake signal" in run(WolDriver().execute(d, "power_on", {}))
    t.join(5)
    rx.close()
    assert got and got[0] == magic_packet("01:23:45:67:89:ab")
    d.config["broadcast"] = "8.8.8.8"
    with pytest.raises(DeviceError, match="home network"):
        run(WolDriver().execute(d, "power_on", {}))
    with pytest.raises(DeviceError):
        run(WolDriver().execute(d, "power_off", {}))


# ── ADB (a fake adb program records what it is asked to do) ───────────────────────────────────────
FAKE_ADB = r'''#!%(py)s
import sys, json
log = %(log)r
args = sys.argv[1:]
open(log, "a").write(json.dumps(args) + "\n")
tail = " ".join(args)
if "pm list packages" in tail:
    sys.stdout.write("package:com.google.android.youtube\npackage:com.netflix.mediaclient\npackage:com.spotify.music\n")
elif "dumpsys battery" in tail:
    sys.stdout.write("Current Battery Service state:\n  level: 73\n")
elif "screencap" in tail:
    sys.stdout.buffer.write(b"\x89PNG-fake")
elif args[:1] == ["connect"]:
    sys.stdout.write("connected to " + args[1])
elif "monkey" in tail and "missing.pkg" in tail:
    sys.stderr.write("no such package"); sys.exit(1)
'''


@pytest.fixture
def fake_adb(tmp_path, monkeypatch):
    log = tmp_path / "calls.jsonl"
    exe = tmp_path / "adb"
    exe.write_text(FAKE_ADB % {"py": sys.executable, "log": str(log)})
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("ATULYA_ADB", str(exe))
    return lambda: [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []


def phone():
    return DeviceRecord(id="ph1", name="My phone", kind="phone", driver="adb", address="127.0.0.1", config={"port": 5555})


def test_adb_keys_apps_and_status(fake_adb):
    drv, d = AdbDriver(), phone()
    run(drv.execute(d, "volume_up", {"times": 2}))
    run(drv.execute(d, "home", {}))
    assert "Opened youtube" in run(drv.execute(d, "launch_app", {"app": "YouTube"}))
    assert "73%" in run(drv.execute(d, "battery", {}))
    assert "Opened the link" in run(drv.execute(d, "open_url", {"url": "https://example.com/a?b=1"}))
    calls = fake_adb()
    shells = [c[3:] for c in calls if c[:3] == ["-s", "127.0.0.1:5555", "shell"]]
    assert shells.count(["input", "keyevent", "24"]) == 2 and ["input", "keyevent", "3"] in shells
    assert ["monkey", "-p", "com.google.android.youtube", "-c", "android.intent.category.LAUNCHER", "1"] in shells
    assert ["am", "start", "-a", "android.intent.action.VIEW", "-d", "https://example.com/a?b=1"] in shells
    assert ["connect", "127.0.0.1:5555"] in calls


def test_adb_refuses_unsafe_input_and_unknown_things(fake_adb):
    drv, d = AdbDriver(), phone()
    for url in ("file:///sdcard/x", "javascript:alert(1)", "https://x.com/a;reboot", "https://x.com/`id`", "ftp://x"):
        with pytest.raises(DeviceError):
            run(drv.execute(d, "open_url", {"url": url}))
    with pytest.raises(DeviceError, match="simple text"):
        run(drv.execute(d, "type_text", {"text": "hi; rm -rf /"}))
    with pytest.raises(DeviceError, match="couldn't find an app"):
        run(drv.execute(d, "launch_app", {"app": "doesnotexist"}))
    with pytest.raises(DeviceError, match="Which app"):
        run(drv.execute(d, "launch_app", {"app": " "}))
    with pytest.raises(DeviceError, match="can't “shell”"):
        run(drv.execute(d, "shell", {"cmd": "id"}))
    assert not any("rm" in " ".join(c) or "reboot" in " ".join(c) for c in fake_adb())      # nothing dangerous ever reached adb
    caps = {c.name: c for c in run(drv.capabilities(d))}
    assert caps["type_text"].risky and not caps["home"].risky and "shell" not in caps


def test_adb_screenshot_and_missing_tool(fake_adb, monkeypatch, tmp_path):
    out = run(AdbDriver().execute(phone(), "screenshot", {}))
    assert "Saved a screenshot" in out
    monkeypatch.delenv("ATULYA_ADB")
    monkeypatch.setattr(adbmod.shutil, "which", lambda _: None)
    with pytest.raises(DeviceError, match="adb tool isn't installed"):
        run(AdbDriver().execute(phone(), "home", {}))


def test_adb_only_connects_to_your_own_network(fake_adb, monkeypatch):
    monkeypatch.delenv("ATULYA_DEVICES_ALLOW_LOOPBACK")
    d = DeviceRecord(id="x", name="Far", kind="phone", driver="adb", address="8.8.8.8")
    with pytest.raises(DeviceError, match="home network"):
        run(AdbDriver().execute(d, "home", {}))
    assert fake_adb() == []


# ── Home Assistant (a fake server checks the token and records service calls) ───────────────────────
def ha_sim():
    states = json.dumps([
        {"entity_id": "light.kitchen", "state": "off", "attributes": {"friendly_name": "Kitchen light"}},
        {"entity_id": "media_player.lg_tv", "state": "on", "attributes": {"friendly_name": "LG TV"}},
        {"entity_id": "lock.front_door", "state": "locked", "attributes": {"friendly_name": "Front door"}},
        {"entity_id": "sensor.temp", "state": "21", "attributes": {}}])
    return sims.Sim({("GET", "/api/states/light.kitchen"): (200, '{"state":"off"}'), ("GET", "/api/states"): (200, states), ("POST", "/api/services/"): (200, "[]")})


def ha_driver(sim):
    return HomeAssistantDriver(url=f"http://127.0.0.1:{sim.port}", token="tok123")


def test_home_assistant_lists_entities_and_calls_services():
    with ha_sim() as sim:
        drv = ha_driver(sim)
        found = run(drv.entities())
        assert {e["entity"] for e in found} == {"light.kitchen", "media_player.lg_tv", "lock.front_door"}     # sensors are not controllable
        light = DeviceRecord(id="1", name="Kitchen light", kind="light", driver="homeassistant", config={"entity": "light.kitchen"})
        tv = DeviceRecord(id="2", name="LG TV", kind="tv", driver="homeassistant", config={"entity": "media_player.lg_tv"})
        run(drv.execute(light, "set_brightness", {"value": 40}))
        run(drv.execute(tv, "set_volume", {"value": 30}))
        run(drv.execute(tv, "volume_up", {}))
        assert run(drv.state(light)) == {"online": True, "state": "off"}
    posts = [r for r in sim.requests if r["method"] == "POST"]
    assert posts[0]["path"] == "/api/services/light/turn_on" and posts[0]["json"] == {"entity_id": "light.kitchen", "brightness_pct": 40}
    assert posts[1]["path"] == "/api/services/media_player/volume_set" and posts[1]["json"]["volume_level"] == 0.3
    assert posts[2]["path"] == "/api/services/media_player/volume_up"
    assert all(r["headers"].get("Authorization") == "Bearer tok123" for r in sim.requests)


def test_home_assistant_capabilities_by_domain_and_unlock_is_risky():
    drv = HomeAssistantDriver(url="http://127.0.0.1:1", token="t")
    lock = DeviceRecord(id="3", name="Door", kind="lock", driver="homeassistant", config={"entity": "lock.front_door"})
    caps = {c.name: c for c in run(drv.capabilities(lock))}
    assert set(caps) == {"lock", "unlock"} and caps["unlock"].risky and not caps["lock"].risky
    with pytest.raises(DeviceError, match="can't “fly”"):
        run(drv.execute(lock, "fly", {}))


def test_home_assistant_errors_are_plain():
    with pytest.raises(DeviceError, match="isn't set up"):
        run(HomeAssistantDriver(url="", token="").entities())
    transport = httpx.MockTransport(lambda r: httpx.Response(401))
    with pytest.raises(DeviceError, match="refused the token"):
        run(HomeAssistantDriver(url="http://127.0.0.1:8123", token="bad", transport=transport).entities())
    with pytest.raises(DeviceError, match="couldn't reach"):
        run(HomeAssistantDriver(url="http://127.0.0.1:1", token="t").entities())
