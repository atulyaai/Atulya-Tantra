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
    ctx = PluginContext("alice", None, None, "alice")

    reply = asyncio.run(toolkit._rename_device({"device": "my phone", "new_name": "Atul’s Phone"}, ctx))
    assert reply == "Renamed 'Phone 22115225 a1b2' to 'Atul's Phone'."
    assert [row["name"] for row in hub.devices("alice")] == ["Atul's Phone"]
    assert hub.authenticate(token) == {"owner": "alice", "name": "Atul's Phone"}  # same credential keeps working
    assert hub.jobs("alice")[0]["id"] == job["id"] and hub.jobs("alice")[0]["device"] == "Atul's Phone"

    hub.pair("alice", "Laptop", ["ping"])
    assert "already have a device called" in asyncio.run(
        toolkit._rename_device({"device": "Laptop", "new_name": "Atul's Phone"}, ctx))
    assert "Which device?" in asyncio.run(toolkit._rename_device({"device": "tablet", "new_name": "X"}, ctx))
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


def reply(delay, acknowledge):
    brain = Brain(SlowToolProvider())

    async def run():
        return "".join([chunk async for chunk in brain.stream(
            [Message(role="user", content="weather?")], toolbox=Box(delay), acknowledge=acknowledge)])
    return asyncio.run(run())


def test_no_filler_when_typing_or_when_tools_are_quick(monkeypatch):
    monkeypatch.setattr("tools.plugins.brain.engine.FILLER_AFTER_SECONDS", 0.2)
    assert reply(0.0, acknowledge=False) == "Clear, 25 °C."
    assert reply(0.5, acknowledge=False) == "Clear, 25 °C."   # typed: never a filler
    assert reply(0.0, acknowledge=True) == "Clear, 25 °C."    # spoken but quick: no filler
    assert reply(0.5, acknowledge=True) == "Checking the weather. Clear, 25 °C."  # spoken and slow
    assert "One moment" not in reply(0.5, acknowledge=True)


def test_play_music_starts_the_song_in_the_player(project_temp_dir, monkeypatch):
    monkeypatch.setenv("ATULYA_DATA_DIR", str(project_temp_dir))

    async def found(query):
        return {"video_id": "dQw4w9WgXcQ", "title": "Kesariya - Official"}

    monkeypatch.setattr("atulya.music.find_youtube", found)
    actions: list = []
    token = toolkit.UI_ACTIONS.set(actions)
    try:
        web = asyncio.run(toolkit._find_music({"query": "kesariya"}, PluginContext("alice", None, None, "alice")))
    finally:
        toolkit.UI_ACTIONS.reset(token)
    assert web.startswith("Started 'Kesariya - Official' in the Atulya player")
    play = next(item for item in actions if item["type"] == "play_music")
    assert play["track"]["video_id"] == "dQw4w9WgXcQ"
    assert any(item["type"] == "link" and item["url"].endswith("watch?v=dQw4w9WgXcQ") for item in actions)

    telegram = asyncio.run(toolkit._find_music(
        {"query": "kesariya"}, PluginContext("alice", None, None, "alice", channel="telegram")))
    assert "Telegram cannot play audio" in telegram
