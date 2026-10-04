import asyncio
import socket
import threading

import pytest

from atulya import upakaran as discovery
from atulya.upakaran import DeviceError
from atulya.upakaran import DeviceHub
from atulya.upakaran import load_profiles
from pariksha import sims



def run(c):
    return asyncio.run(c)


@pytest.fixture(autouse=True)
def loopback(monkeypatch):
    monkeypatch.setenv("ATULYA_DEVICES_ALLOW_LOOPBACK", "on")


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
