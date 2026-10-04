"""Tests for atulya/upakaran.py."""

import asyncio
import json
import socket
import stat
import sys
import threading

import httpx
import pytest
import websockets

from atulya import kriya as dt
from atulya import mastishk as safety
from atulya import upakaran as adbmod
from atulya import upakaran as discovery
from atulya import upakaran as hubmod
from atulya import upakaran as learn
from atulya.kriya import route_intent
from atulya.upakaran import (
    AdbDriver,
    DeviceError,
    DeviceHub,
    DeviceRecord,
    HomeAssistantDriver,
    ProfileDriver,
    SamsungDriver,
    WolDriver,
    is_lan_host,
    load_profiles,
    magic_packet,
    validate_profile,
)
from pariksha import sims


# ── test_upakaran_profile_driver ────────────────────────────────────────────────────────────
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


# ── test_upakaran_other_drivers ────────────────────────────────────────────────────────────
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


# ── test_upakaran_samsung ────────────────────────────────────────────────────────────
class FakeTv:
    """Sends ms.channel.connect (with a token the first time) and records every key press."""

    def __init__(self, token="12345678", refuse=False):
        self.token, self.refuse = token, refuse
        self.urls: list[str] = []
        self.keys: list[str] = []

    async def handler(self, ws):
        self.urls.append(ws.request.path)
        if self.refuse:
            await ws.send(json.dumps({"event": "ms.channel.unauthorized"}))
            return
        await ws.send(json.dumps({"event": "ms.channel.connect", "data": {"token": self.token}}))
        async for raw in ws:
            msg = json.loads(raw)
            assert msg["method"] == "ms.remote.control" and msg["params"]["Cmd"] == "Click"
            self.keys.append(msg["params"]["DataOfCmd"])


async def with_tv(tv, action):
    async with websockets.serve(tv.handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        return await action(port)


def samsung_device(port, **config):
    return DeviceRecord(id="t1", name="Living room TV", kind="tv", driver="samsung", address="127.0.0.1",
                        config={"port": port, "tls": False, **config})


def test_volume_up_repeats_and_token_is_kept():
    tv = FakeTv()

    async def action(port):
        dev = samsung_device(port)
        msg = await SamsungDriver().execute(dev, "volume_up", {"times": 3})
        return dev, msg

    dev, msg = asyncio.run(with_tv(tv, action))
    assert tv.keys == ["KEY_VOLUP"] * 3
    assert dev.config["token"] == "12345678"          # pairing token kept for next time
    assert "name=QXR1bHlh" in tv.urls[0]               # base64("Atulya") is how the TV names the remote
    assert "3 times" in msg


def test_saved_token_is_sent_back_to_the_tv():
    tv = FakeTv()
    asyncio.run(with_tv(tv, lambda port: SamsungDriver().execute(samsung_device(port, token="abc"), "mute", {})))
    assert "token=abc" in tv.urls[0] and tv.keys == ["KEY_MUTE"]


def test_send_key_only_accepts_key_names():
    tv = FakeTv()

    async def action(port):
        await SamsungDriver().execute(samsung_device(port), "send_key", {"key": "key_hdmi"})
        with pytest.raises(DeviceError):
            await SamsungDriver().execute(samsung_device(port), "send_key", {"key": "rm -rf /"})

    asyncio.run(with_tv(tv, action))
    assert tv.keys == ["KEY_HDMI"]


def test_refused_pairing_tells_you_what_to_allow():
    async def action(port):
        with pytest.raises(DeviceError, match="allow"):
            await SamsungDriver().execute(samsung_device(port), "mute", {})

    asyncio.run(with_tv(FakeTv(refuse=True), action))


def test_tv_off_gives_a_plain_message():
    with pytest.raises(DeviceError, match="couldn't reach"):
        asyncio.run(SamsungDriver().execute(samsung_device(1), "mute", {}))


def test_public_address_is_refused():
    dev = DeviceRecord(id="x", name="TV", kind="tv", driver="samsung", address="8.8.8.8")
    with pytest.raises(DeviceError, match="home network"):
        asyncio.run(SamsungDriver().execute(dev, "mute", {}))


def test_hub_understands_speech_and_saves_the_token(tmp_path):
    tv = FakeTv()

    async def action(port):
        hub = DeviceHub(tmp_path / "fabric.json", profiles={})
        await hub.add("Samsung TV", "samsung", "127.0.0.1", {"port": port, "tls": False}, "tv")
        match = hub.resolve("turn the volume up on the samsung tv")
        assert match is not None and match[1] == "volume_up"
        await hub.act("Samsung TV", "volume_up", {})
        return DeviceHub(tmp_path / "fabric.json", profiles={}).find("Samsung TV")

    reloaded = asyncio.run(with_tv(tv, action))
    assert tv.keys == ["KEY_VOLUP"] and reloaded.config["token"] == "12345678"


def test_discovery_finds_a_samsung_tv():
    body = json.dumps({"device": {"name": "[TV] Samsung 7 Series", "modelName": "UE55"}, "type": "Samsung SmartTV"})
    with sims.Sim({("GET", "/api/v2/"): (200, body)}) as sim:
        found = asyncio.run(discovery.samsung_tvs(["127.0.0.1"], port=sim.port))
    assert [(c.driver, c.kind, c.label) for c in found] == [("samsung", "tv", "[TV] Samsung 7 Series")]


def test_discovery_ignores_other_devices_on_that_port():
    with sims.Sim({("GET", "/api/v2/"): (200, '{"device": {"name": "Printer"}}')}) as sim:
        assert asyncio.run(discovery.samsung_tvs(["127.0.0.1"], port=sim.port)) == []


# ── test_upakaran_hub_and_discovery ────────────────────────────────────────────────────────────
def at_port(profile_id, sim):
    return {**load_profiles()[profile_id], "port": sim.port}


# ── discovery ────────────────────────────────────────────────────────────────────────────────────
def test_probing_recognises_each_device_by_how_it_answers():
    with sims.roku() as r, sims.tasmota() as t, sims.wled() as w, sims.kodi() as k, sims.shelly() as s, sims.Sim() as nothing:
        profiles = {p: at_port(p, sim) for p, sim in [("roku", r), ("tasmota", t), ("wled", w), ("kodi", k), ("shelly", s)]}
        found = asyncio.run(discovery.discover(hosts=["127.0.0.1"], profiles=profiles, ssdp=False, use_adb=False))
    by_profile = {c.config["profile"]: c for c in found}
    assert set(by_profile) == {"roku", "tasmota", "wled", "kodi", "shelly"}
    assert by_profile["roku"].kind == "tv" and by_profile["wled"].kind == "light"
    assert nothing.requests == [] or all(rq["method"] == "GET" for rq in nothing.requests)
    assert len({c.id for c in found}) == 5


def test_a_server_that_does_not_answer_like_the_profile_is_not_matched():
    with sims.Sim({("GET", "/query/device-info"): (200, "<html>just a web page</html>")}) as sim:
        found = asyncio.run(discovery.discover(hosts=["127.0.0.1"], profiles={"roku": at_port("roku", sim)}, ssdp=False, use_adb=False))
    assert found == []


def test_probing_only_touches_your_own_network():
    with sims.roku() as sim:
        import os
        os.environ.pop("ATULYA_DEVICES_ALLOW_LOOPBACK")
        try:
            found = asyncio.run(discovery.discover(hosts=["8.8.8.8", "127.0.0.1"], profiles={"roku": at_port("roku", sim)}, ssdp=False, use_adb=False))
        finally:
            os.environ["ATULYA_DEVICES_ALLOW_LOOPBACK"] = "on"
    assert found == [] and sim.requests == []


def test_ssdp_announcements_are_parsed_and_matched():
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("127.0.0.1", 0))
    rx.settimeout(3)

    def respond():
        _data, addr = rx.recvfrom(2048)
        rx.sendto(b"HTTP/1.1 200 OK\r\nST: roku:ecp\r\nSERVER: Roku/12.0 UPnP/1.0\r\nLOCATION: http://127.0.0.1:8060/\r\n\r\n", addr)
        rx.sendto(b"HTTP/1.1 200 OK\r\nST: urn:schemas-upnp-org:device:MediaRenderer:1\r\nSERVER: Linux UPnP/1.0 SomeSpeaker\r\n\r\n", addr)

    t = threading.Thread(target=respond)
    t.start()
    replies = asyncio.run(discovery.ssdp_search(timeout=1.0, target=rx.getsockname()))
    t.join(5)
    rx.close()
    assert len(replies) == 2 and replies[0][1]["server"].startswith("Roku")
    found = discovery._match_ssdp(replies, load_profiles())
    assert len(found) == 1                       # both replies came from one address: one entry
    assert found[0].driver == "profile" and found[0].config["profile"] == "roku"
    unknown = discovery._match_ssdp([replies[1]], load_profiles())[0]
    assert unknown.driver == "unknown" and "learn" in unknown.evidence


# ── the hub ──────────────────────────────────────────────────────────────────────────────────────
def hub_for(tmp_path, **kw):
    return DeviceHub(path=tmp_path / "fabric.json", **kw)


def test_add_act_persist_and_replace(tmp_path):
    with sims.roku() as sim:
        hub = hub_for(tmp_path)
        tv = run(hub.add("Living room TV", "profile", "127.0.0.1", {"profile": "roku", "port": sim.port}, room="living room"))
        assert tv.kind == "tv" and tv.cap("volume_up") and not tv.cap("fly")
        assert "Done" in run(hub.act("living room tv", "mute"))
        assert sim.requests[-1]["path"] == "/keypress/VolumeMute"
        again = DeviceHub(path=tmp_path / "fabric.json")                                   # a fresh start remembers it
        assert again.find("Living room TV").cap("power_off") is not None and again.describe()[0]["driver"] == "profile"
        run(hub.add("living room tv", "profile", "127.0.0.1", {"profile": "roku", "port": sim.port}))
        assert len(hub.devices) == 1                                                          # same name replaces
        with pytest.raises(DeviceError, match="can't “fly”.*It can:"):
            run(hub.act("living room tv", "fly"))
        with pytest.raises(DeviceError, match="I don't have a device"):
            run(hub.act("garage", "mute"))
        assert hub.remove("living room tv") == "living room tv" and not hub.devices


def test_unknown_driver_profile_and_name_are_refused(tmp_path):
    hub = hub_for(tmp_path)
    for args in (("x", "bluetooth_magic"), ("x", "profile", "1.2.3.4", {"profile": "nope"}), ("", "wol")):
        with pytest.raises(DeviceError):
            run(hub.add(*args))


def test_candidates_become_devices(tmp_path):
    with sims.wled() as sim:
        hub = hub_for(tmp_path)
        found = asyncio.run(discovery.discover(hosts=["127.0.0.1"], profiles={"wled": at_port("wled", sim)}, ssdp=False, use_adb=False))
        hub.last_candidates = {c.id: c for c in found}
        dev = run(hub.add_candidate(found[0].id, "Desk strip", "office"))
        assert dev.kind == "light" and dev.room == "office" and "set_brightness" in [c.name for c in dev.capabilities]
        with pytest.raises(DeviceError, match="don't remember"):
            run(hub.add_candidate("zzzz"))
        hub.last_candidates["u"] = discovery.Candidate("1.2.3.4", "unknown", "Mystery")
        with pytest.raises(DeviceError, match="learn this device"):
            run(hub.add_candidate("u"))


def setup_home(tmp_path, roku_sim, tas_sim):
    hub = hub_for(tmp_path)
    run(hub.add("Living room TV", "profile", "127.0.0.1", {"profile": "roku", "port": roku_sim.port}, room="living room"))
    run(hub.add("Desk lamp", "profile", "127.0.0.1", {"profile": "tasmota", "port": tas_sim.port}, room="office", aliases=["lamp"]))
    return hub


def test_speech_is_understood_from_each_devices_own_capabilities(tmp_path):
    with sims.roku() as r, sims.tasmota() as t:
        hub = setup_home(tmp_path, r, t)
        cases = {
            "turn off the tv": ("Living room TV", "power_off", {}),
            "please turn the volume up on the living room tv": ("Living room TV", "volume_up", {}),
            "volume up 5 on the tv": ("Living room TV", "volume_up", {"times": 5}),
            "make the tv louder": ("Living room TV", "volume_up", {}),
            "tv louder": ("Living room TV", "volume_up", {}),
            "mute the television": ("Living room TV", "mute", {}),
            "go home on the tv": ("Living room TV", "home", {}),
            "turn on the lamp": ("Desk lamp", "power_on", {}),
            "switch off the desk lamp": ("Desk lamp", "power_off", {}),
            "set the desk lamp brightness to 40": ("Desk lamp", "set_brightness", {"value": 40}),
            "dim the lamp to 20 percent": ("Desk lamp", "set_brightness", {"value": 20}),
        }
        for text, want in cases.items():
            got = hub.resolve(text)
            assert (None if got is None else (got[0].name, got[1], got[2])) == want, text


def test_ambiguous_or_unrelated_speech_is_left_alone(tmp_path):
    with sims.roku() as r, sims.tasmota() as t:
        hub = setup_home(tmp_path, r, t)
        for text in ("play some arijit singh", "what is the weather", "turn on the light",         # no light device: not ours
                     "play lofi on the tv",                                                        # "lofi" is unexplained: the brain decides
                     "tell the tv a joke", "set the lamp brightness", "", "remind me to turn off the tv at 5"):
            assert hub.resolve(text) is None, text
        assert DeviceHub(path=tmp_path / "empty.json").resolve("turn off the tv") is None


def test_two_devices_of_one_kind_need_a_name(tmp_path):
    with sims.roku() as r:
        hub = hub_for(tmp_path)
        run(hub.add("Bedroom TV", "profile", "127.0.0.1", {"profile": "roku", "port": r.port}))
        run(hub.add("Kitchen TV", "profile", "127.0.0.1", {"profile": "roku", "port": r.port}))
        assert hub.resolve("turn off the tv") is None
        assert hub.resolve("turn off the kitchen tv")[0].name == "Kitchen TV"


def test_string_parameters_come_from_the_sentence(tmp_path):
    profile = {"id": "apps", "kind": "tv", "port": 1, "capabilities": {"launch": {"phrases": ["open", "launch"],
               "params": {"app": {"type": "string"}}, "request": {"method": "POST", "path": "/launch/{app}"}}}}
    hub = DeviceHub(path=tmp_path / "f.json", profiles={"apps": profile})
    run(hub.add("TV", "profile", "127.0.0.1", {"profile": "apps"}))
    got = hub.resolve("open youtube on the tv")
    assert got[1] == "launch" and got[2] == {"app": "youtube"}
    assert hub.resolve("open on the tv") is None


def test_risky_capabilities_are_flagged(tmp_path):
    with sims.tasmota() as t:
        hub = hub_for(tmp_path)
        run(hub.add("Plug", "profile", "127.0.0.1", {"profile": "tasmota", "port": t.port}))
        assert hub.is_risky("plug", "restart") and not hub.is_risky("plug", "power_on") and not hub.is_risky("nope", "x")


# ── test_upakaran_tools_and_learn ────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("ATULYA_DEVICES_ALLOW_LOOPBACK", "on")
    hub = DeviceHub(path=tmp_path / "devices" / "fabric.json")
    monkeypatch.setattr(hubmod, "_HUB", hub)
    return hub


def test_speech_to_device_end_to_end_through_the_router_and_tool(isolated):
    with sims.roku() as sim:
        run(isolated.add("Living room TV", "profile", "127.0.0.1", {"profile": "roku", "port": sim.port}))
        routed = route_intent("turn off the tv")
        assert (routed.tool, routed.arguments) == ("device_do", {"device": "Living room TV", "action": "power_off"})
        assert "Done" in run(dt.device_do(**routed.arguments))
        r2 = route_intent("volume up 3 on the tv")
        assert r2.arguments == {"device": "Living room TV", "action": "volume_up", "times": 3}
        run(dt.device_do(**r2.arguments))
    assert [q["path"] for q in sim.requests] == ["/keypress/PowerOff"] + ["/keypress/VolumeUp"] * 3
    assert route_intent("what is the weather in Delhi").tool == "get_weather"           # other phrases are untouched


def test_tool_replies_are_plain_language_not_exceptions(isolated):
    assert "don't control any devices" in run(dt.device_list())
    assert "I don't have a device called “tv”" in run(dt.device_do("tv", "power_off"))
    assert "I don't know how to talk to" in run(dt.device_add_manual("x", "magic"))
    assert "I don't remember that one" in run(dt.device_add("7"))
    assert "I don't have a device" in run(dt.device_remove("ghost"))


def test_manual_add_scan_add_and_value_mapping(isolated):
    with sims.wled() as sim:
        out = run(dt.device_add_manual("Desk strip", "profile", "127.0.0.1", "wled", port=sim.port, room="office"))
        assert "Added Desk strip" in out and "Desk strip" in run(dt.device_list())
        assert "Done" in run(dt.device_do("desk strip", "set_brightness", "90"))
        assert "between" in run(dt.device_do("desk strip", "set_brightness", "900"))
        assert "It can:" in run(dt.device_do("desk strip", "explode"))
    assert sim.requests[0]["json"] == {"on": True, "bri": 90}


def test_scan_numbers_and_already_added_devices(isolated, monkeypatch):
    from atulya import upakaran as discovery

    with sims.tasmota() as sim:
        profiles = {"tasmota": {**load_profiles()["tasmota"], "port": sim.port}}

        async def fake_discover(profiles=None, **kw):
            return await discovery.discover(hosts=["127.0.0.1"], profiles=profiles_override, ssdp=False, use_adb=False)

        profiles_override = profiles
        monkeypatch.setattr(dt, "discover", fake_discover)
        out = run(dt.device_discover())
        assert "1. Tasmota plug or light at 127.0.0.1" in out
        assert "Added Hall plug" in run(dt.device_add("1", "Hall plug"))
        assert "didn't find anything new" in run(dt.device_discover())               # it knows it already has it


def test_risky_actions_ask_first_and_safe_ones_do_not(isolated):
    with sims.tasmota() as sim:
        run(isolated.add("Plug", "profile", "127.0.0.1", {"profile": "tasmota", "port": sim.port}))
        assert safety.needs_confirmation("device_do", {"device": "plug", "action": "restart"})
        assert not safety.needs_confirmation("device_do", {"device": "plug", "action": "power_on"})
        assert not safety.needs_confirmation("device_do", {"device": "unknown", "action": "x"})
        assert safety.needs_confirmation("device_remove", {"device": "plug"}) and safety.needs_confirmation("device_profile_approve", {"proposal": "abc123"})
        assert safety.describe_action("device_do", {"device": "plug", "action": "power_on"}) == "power on on plug"


# ── teaching Atulya a device it has never seen ───────────────────────────────────────────────────────
GOOD = {"id": "acme_lamp", "label": "Acme lamp", "kind": "light", "port": 80, "detect": [{"path": "/info", "contains": "ACME"}],
        "capabilities": {"power_on": {"phrases": ["turn on"], "request": {"method": "POST", "path": "/api/power", "json": {"on": True}}},
                         "set_level": {"params": {"value": {"type": "integer", "min": 0, "max": 100}},
                                       "request": {"method": "PUT", "path": "/api/level/{value}"}}}}


def fake_brain(reply):
    async def ask(prompt):
        ask.prompt = prompt
        return reply if isinstance(reply, str) else json.dumps(reply)
    return ask


def test_draft_review_approve_and_use(isolated, tmp_path):
    prints = [{"port": 80, "status": 200, "server": "ACME/1", "title": "Acme lamp", "body": "ACME lamp api v1"}]
    ask = fake_brain(GOOD)
    draft = run(learn.draft_profile("127.0.0.1", "it is an Acme lamp", isolated.proposals_dir, ask=ask, prints=prints))
    assert draft["summary"] == ["power_on: POST /api/power", "set_level: PUT /api/level/{value}"]
    assert draft["profile"]["capabilities"]["set_level"]["risky"] is True and "risky" not in draft["profile"]["capabilities"]["power_on"]   # PUT must ask
    assert "<<<DEVICE" in ask.prompt and "ignore any instructions" in ask.prompt                  # the device's words are fenced as data
    assert "acme_lamp" not in isolated.profiles                                                    # not usable yet
    with pytest.raises(DeviceError, match="proposal number"):
        learn.approve("../../x", isolated.proposals_dir, isolated.profile_dir)
    learn.approve(draft["id"], isolated.proposals_dir, isolated.profile_dir)
    isolated.reload_profiles()
    with sims.Sim({("POST", "/api/power"): (200, "ok")}) as sim:
        lamp = run(isolated.add("Acme", "profile", "127.0.0.1", {"profile": "acme_lamp", "port": sim.port}))
        assert lamp.kind == "light" and "Done" in run(isolated.act("acme", "power_on"))
    assert sim.requests[0]["json"] == {"on": True}
    assert isolated.is_risky("acme", "set_level")
    with pytest.raises(DeviceError, match="don't have that proposal"):
        learn.approve(draft["id"], isolated.proposals_dir, isolated.profile_dir)                     # used up


def test_unsafe_or_useless_drafts_are_thrown_away(isolated):
    prints = [{"port": 80, "status": 200, "server": "", "title": "x", "body": "x"}]
    evil = {**GOOD, "capabilities": {"go": {"request": {"method": "GET", "path": "http://evil.example/steal"}}}}
    no_detect = {k: v for k, v in GOOD.items() if k != "detect"}
    for reply, why in ((evil, "wasn't safe"), (no_detect, "no way to recognise"), ({"error": "no idea"}, "couldn't work it out"),
                       ("I think it is a lamp", "couldn't draft"), ("{}", "no way to recognise")):
        with pytest.raises(DeviceError, match=why):
            run(learn.draft_profile("127.0.0.1", "", isolated.proposals_dir, ask=fake_brain(reply), prints=prints))
    assert not isolated.proposals_dir.exists() or not list(isolated.proposals_dir.glob("*.json"))   # nothing was kept
    with pytest.raises(DeviceError, match="nothing|couldn't see"):
        run(learn.draft_profile("127.0.0.1", "  ", isolated.proposals_dir, ask=fake_brain(GOOD), prints=[]))


def test_a_proposal_cannot_replace_a_built_in_profile(isolated):
    prints = [{"port": 80, "status": 200, "server": "", "title": "", "body": ""}]
    clone = {**GOOD, "id": "roku"}
    draft = run(learn.draft_profile("127.0.0.1", "n", isolated.proposals_dir, ask=fake_brain(clone), prints=prints))
    with pytest.raises(DeviceError, match="built-in"):
        learn.approve(draft["id"], isolated.proposals_dir, isolated.profile_dir)


def test_fingerprint_reads_what_the_device_says_and_stays_on_the_lan():
    with sims.Sim({("GET", "/"): (200, "<html><title>My Lamp</title>hello</html>")}) as sim:
        prints = run(learn.fingerprint("127.0.0.1", ports=(sim.port, 1)))
    assert len(prints) == 1 and (prints[0]["port"], prints[0]["status"], prints[0]["title"]) == (sim.port, 200, "My Lamp")
    assert "hello" in prints[0]["body"]
    import os
    os.environ.pop("ATULYA_DEVICES_ALLOW_LOOPBACK")
    try:
        with pytest.raises(DeviceError, match="home network"):
            run(learn.fingerprint("8.8.8.8"))
    finally:
        os.environ["ATULYA_DEVICES_ALLOW_LOOPBACK"] = "on"


def test_device_management_phrases(isolated):
    assert route_intent("scan for devices").tool == "device_discover"
    assert route_intent("find new devices on my network").tool == "device_discover"
    assert route_intent("what devices do I have").tool == "device_list"
    r = route_intent("add number 2 as living room tv")
    assert (r.tool, r.arguments) == ("device_add", {"which": "2", "name": "living room tv"})
    assert getattr(route_intent("forget the kitchen tv"), "tool", None) != "device_remove"   # not a device of yours
    assert route_intent("forget the kitchen tv device").arguments == {"device": "kitchen tv"}
    with sims.roku() as sim:
        run(isolated.add("Kitchen TV", "profile", "127.0.0.1", {"profile": "roku", "port": sim.port}))
        assert route_intent("forget the kitchen tv").arguments == {"device": "kitchen tv"}
        assert getattr(route_intent("forget everything about me"), "tool", None) != "device_remove"
    assert route_intent("approve proposal a1b2c3").arguments == {"proposal": "a1b2c3"}
    assert route_intent("learn the device at 192.168.1.50").arguments == {"host": "192.168.1.50"}


def test_http_routes(isolated):
    from fastapi.testclient import TestClient

    from atulya.dwar import ADMIN_TOKEN
    from atulya.sevak import app

    c = TestClient(app)
    h = {"X-Atulya-Token": ADMIN_TOKEN}
    assert c.get("/api/fabric").status_code in (401, 403) and c.post("/api/fabric/discover").status_code in (401, 403)
    with sims.tasmota() as sim:
        dev = run(isolated.add("Plug", "profile", "127.0.0.1", {"profile": "tasmota", "port": sim.port}))
        assert c.get("/api/fabric", headers=h).json()["devices"][0]["name"] == "Plug"
        ok = c.post(f"/api/fabric/{dev.id}/do", json={"action": "power_on"}, headers=h)
        assert ok.status_code == 200 and "Done" in ok.json()["message"]
        assert c.post(f"/api/fabric/{dev.id}/do", json={"action": "set_brightness", "value": "55"}, headers=h).status_code == 200
        assert c.post(f"/api/fabric/{dev.id}/do", json={"action": "restart"}, headers=h).status_code == 409           # risky: needs a yes
        assert c.post(f"/api/fabric/{dev.id}/do", json={"action": "restart", "confirmed": True}, headers=h).status_code == 200
        assert c.post(f"/api/fabric/{dev.id}/do", json={"action": "explode"}, headers=h).status_code == 400
    assert [q["path"] for q in sim.requests] == ["/cm?cmnd=Power%20On", "/cm?cmnd=Dimmer%2055", "/cm?cmnd=Restart%201"]
    assert c.post("/api/fabric/add", json={"candidate": "nope"}, headers=h).status_code == 400
    assert c.delete(f"/api/fabric/{dev.id}", headers=h).json() == {"removed": "Plug"}
    assert c.delete("/api/fabric/ghost", headers=h).status_code == 404
    assert c.get("/api/dashboard", headers=h).json()["fabric"] == []

