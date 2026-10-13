import asyncio
from types import SimpleNamespace

from atulya.history import ConversationHistory
from tools.plugins.communications.channels.telegram import TelegramChannel
from tools.plugins.productivity.calendar import CalendarStore
from tools.plugins.productivity.reminders import ReminderStore
from tools.plugins.registry import build_default_registry
from tools.plugins.toolkit import UI_ACTIONS


def test_music_request_prepares_device_button_not_server_playback(project_temp_dir):
    class Brain:
        async def respond_with_tools(self, conversation, toolbox, **kwargs):
            names = {t["function"]["name"] for t in toolbox.schemas}
            assert "find_music" in names and "maintenance_patch" in names
            assert "media_control" not in names and "screen_control" not in names
            result = await toolbox.call("find_music", {"query": "Ammy Virk Punjabi songs"})
            assert "must tap" in result and "already opened" in result
            return SimpleNamespace(text="Tap the music button and start playback on your phone.")
    class Client:
        def __init__(self):
            self.messages = []
        async def post(self, url, *, json):
            self.messages.append(json)
            return SimpleNamespace(raise_for_status=lambda: None)
    channel = TelegramChannel(token="test", allowed_user_ids={"12345"}, brain=Brain(),
                              history=ConversationHistory(project_temp_dir), reminders=ReminderStore(project_temp_dir),
                              calendar=CalendarStore(project_temp_dir), personal_memory=object(), maintenance=object(),
                              command_plugins=build_default_registry(), status_summary=lambda: "ready")
    client = Client()
    async def exercise():
        previous = UI_ACTIONS.get()
        await channel._handle_message(client, {"from": {"id": 12345}, "chat": {"id": 12345, "type": "private"},
                                               "message_id": 9, "text": "Play Ammy Virk Punjabi songs"})
        assert UI_ACTIONS.get() is previous
    asyncio.run(exercise())
    button = client.messages[0]["reply_markup"]["inline_keyboard"][0][0]
    assert button["url"] == "https://www.youtube.com/results?search_query=Ammy+Virk+Punjabi+songs"
    assert "music" in button["text"].lower()
