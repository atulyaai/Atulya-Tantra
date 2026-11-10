"""Rename devices, no "One moment." on every reply, and "play X" that actually plays."""
import asyncio

import pytest

from tools.plugins import toolkit
from tools.plugins.brain import Brain, Message, ToolCall
from tools.plugins.registry import PluginContext
from tools.plugins.system.agents import AgentHub

PHONE = ["ping", "battery_status", "open_app", "send_sms"]


def test_devices_can_be_renamed_by_name_or_as_my_phone(project_temp_dir, monkeypatch):
    monkeypatch.setenv("ATULYA_DATA_DIR", str(project_temp_dir))
    hub = AgentHub(project_temp_dir)
    token = hub.pair("alice", "Phone 22115225 a1b2", PHONE)["token"]
    job = hub.enqueue("alice", "Phone 22115225 a1b2", "ping")
    # Device management is an owner action; the role comes from the auth store and fails closed.
    ctx = PluginContext("alice", None, None, "alice", is_admin=True)

    reply = asyncio.run(toolkit._rename_device({"name": "Phone 22115225 a1b2", "new_name": "Atul’s Phone"}, ctx))
    assert reply == "Renamed 'Phone 22115225 a1b2' to 'Atul's Phone'."
    assert [row["name"] for row in hub.devices("alice")] == ["Atul's Phone"]
    identified = hub.authenticate(token)
    assert identified["owner"] == "alice" and identified["name"] == "Atul's Phone"  # same credential keeps working
    assert hub.jobs("alice")[0]["id"] == job["id"] and hub.jobs("alice")[0]["device"] == "Atul's Phone"

    hub.pair("alice", "Laptop", ["ping"])
    assert "already have a device called" in asyncio.run(
        toolkit._rename_device({"name": "Laptop", "new_name": "Atul's Phone"}, ctx))
    assert "No paired device called" in asyncio.run(
        toolkit._rename_device({"name": "tablet", "new_name": "X"}, ctx))
    assert "Only the owner" in asyncio.run(
        toolkit._rename_device({"name": "Laptop", "new_name": "X"}, PluginContext("alice", None, None, "alice")))
    with pytest.raises(ValueError):
        hub.rename("alice", "Laptop", "<script>")


class SlowToolProvider:
    """First round asks for one tool; the final round answers."""
    name, model = "fake", "fake"

    def __init__(self):
        self.round = 0

    async def stream(self, messages, tools=None):
        self.round += 1
        if self.round == 1:
            yield ToolCall(id="1", name="get_weather", arguments="{}")
        else:
            yield "Clear, 25 °C."


class Box:
    MAX_ROUNDS = 3
    schemas: list = []

    def __init__(self, delay):
        self.delay = delay

    def __bool__(self):
        return True

    def instructions(self):
        return ""

    async def call(self, name, arguments):
        await asyncio.sleep(self.delay)
        return "clear 25"


def reply(delay):
    brain = Brain(SlowToolProvider())

    async def run():
        return "".join([chunk async for chunk in brain.stream(
            [Message(role="user", content="weather?")], toolbox=Box(delay))])
    return asyncio.run(run())


def test_the_acknowledgement_is_spoken_at_once_and_never_says_one_moment():
    # The acknowledgement comes from the user's own words, so it is spoken before the tool finishes.
    assert reply(0.0) == "Checking the weather. Clear, 25 °C."
    assert reply(0.5) == "Checking the weather. Clear, 25 °C."
    assert "One moment" not in reply(0.5)


def test_play_music_never_claims_playback(project_temp_dir, monkeypatch):
    """The music queue is a request; only the client receipt proves playback (tests/core/test_music_search.py)."""
    monkeypatch.setenv("ATULYA_DATA_DIR", str(project_temp_dir))
    from atulya import music

    monkeypatch.setattr(music, "search_music", lambda *args: [
        {"url": "https://youtu.be/dQw4w9WgXcQ", "title": "Kesariya - Official"}])
    actions: list = []
    token = toolkit.UI_ACTIONS.set(actions)
    try:
        web = asyncio.run(toolkit._queue_music(
            {"query": "kesariya"}, PluginContext("alice", None, None, "alice")))
    finally:
        toolkit.UI_ACTIONS.reset(token)
    assert "Queued Kesariya - Official" in web
    assert "no phone playback is confirmed" in web
    assert not any(item.get("type") == "play_music" for item in actions)
