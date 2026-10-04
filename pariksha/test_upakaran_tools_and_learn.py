import asyncio
import json

import pytest

from atulya import kriya as dt
from atulya.kriya import route_intent
from atulya import mastishk as safety
from atulya import upakaran as hubmod
from atulya import upakaran as learn
from atulya.upakaran import DeviceError
from atulya.upakaran import DeviceHub
from atulya.upakaran import load_profiles
from pariksha import sims


def run(c):
    return asyncio.run(c)


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

    from atulya.sevak import app
    from atulya.dwar import ADMIN_TOKEN

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
