"""Samsung Smart TV driver against a simulated TV speaking the remote-control websocket (written from the
public protocol description, not captured from a real set)."""
import asyncio
import json

import pytest
import websockets

from atulya import upakaran_hub as discovery
from atulya.upakaran import DeviceError, DeviceRecord
from atulya.upakaran_hub import DeviceHub
from atulya.upakaran import SamsungDriver
from pariksha.upakaran import sims


@pytest.fixture(autouse=True)
def loopback(monkeypatch):
    monkeypatch.setenv("ATULYA_DEVICES_ALLOW_LOOPBACK", "on")


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


def device(port, **config):
    return DeviceRecord(id="t1", name="Living room TV", kind="tv", driver="samsung", address="127.0.0.1",
                        config={"port": port, "tls": False, **config})


def test_volume_up_repeats_and_token_is_kept():
    tv = FakeTv()

    async def action(port):
        dev = device(port)
        msg = await SamsungDriver().execute(dev, "volume_up", {"times": 3})
        return dev, msg

    dev, msg = asyncio.run(with_tv(tv, action))
    assert tv.keys == ["KEY_VOLUP"] * 3
    assert dev.config["token"] == "12345678"          # pairing token kept for next time
    assert "name=QXR1bHlh" in tv.urls[0]               # base64("Atulya") is how the TV names the remote
    assert "3 times" in msg


def test_saved_token_is_sent_back_to_the_tv():
    tv = FakeTv()
    asyncio.run(with_tv(tv, lambda port: SamsungDriver().execute(device(port, token="abc"), "mute", {})))
    assert "token=abc" in tv.urls[0] and tv.keys == ["KEY_MUTE"]


def test_send_key_only_accepts_key_names():
    tv = FakeTv()

    async def action(port):
        await SamsungDriver().execute(device(port), "send_key", {"key": "key_hdmi"})
        with pytest.raises(DeviceError):
            await SamsungDriver().execute(device(port), "send_key", {"key": "rm -rf /"})

    asyncio.run(with_tv(tv, action))
    assert tv.keys == ["KEY_HDMI"]


def test_refused_pairing_tells_you_what_to_allow():
    async def action(port):
        with pytest.raises(DeviceError, match="allow"):
            await SamsungDriver().execute(device(port), "mute", {})

    asyncio.run(with_tv(FakeTv(refuse=True), action))


def test_tv_off_gives_a_plain_message():
    with pytest.raises(DeviceError, match="couldn't reach"):
        asyncio.run(SamsungDriver().execute(device(1), "mute", {}))


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
