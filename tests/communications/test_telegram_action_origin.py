"""AUDIT S3: a pending action is bound to the channel identity that asked for it."""
import asyncio

from tools.plugins.registry import PluginContext
from tools.plugins.toolkit import TOOLS, ActionQueue, Toolbox


def test_only_the_requesting_telegram_id_can_take_the_action(tmp_path, monkeypatch):
    monkeypatch.setenv("DISPLAY", ":test")
    queue = ActionQueue(tmp_path)
    view = queue.view()
    context = PluginContext("tg", None, None, "admin", actions=view, channel="web", is_admin=True, origin="tg:111")
    reply = asyncio.run(Toolbox(TOOLS, context).call("cast_to_tv", {"tv": "Living Room TV", "url": "https://x.test"}))
    assert "Approval requested" in reply
    [action] = view.created
    assert action.origin == "tg:111"
    assert queue.take(action.id, "admin", origin="tg:222") is None       # another allow-listed id: refused
    assert queue.take(action.id, "admin", origin="tg:111") is action     # still pending for the real requester
    assert queue.take(action.id, "admin", origin="tg:111") is None       # single use


def test_web_actions_keep_working_without_origin(tmp_path):
    queue = ActionQueue(tmp_path)
    action = queue.add("open_app", {"name": "Notepad"}, "Open app: Notepad", "admin")
    assert action.origin == "" and queue.take(action.id, "admin") is action
