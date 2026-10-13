import asyncio
from datetime import datetime, timedelta, timezone

import httpx

from tools.plugins.communications.channels.telegram import TelegramChannel
from tools.plugins.productivity.reminders import ReminderStore


def test_reminder_requests_normal_notifications_and_records_telegram_receipt(project_temp_dir, monkeypatch):
    import json
    store = ReminderStore(project_temp_dir)
    rid = store.add("12345", "12345", "Receipt test", datetime.now(timezone.utc) - timedelta(seconds=1))
    channel = TelegramChannel(token="test", allowed_user_ids={"12345"}, brain=None, history=None,
                              reminders=store, status_summary=lambda: "ready")
    original_client = httpx.AsyncClient
    def handler(request):
        payload = json.loads(request.content)
        assert payload["disable_notification"] is False
        channel._stopping.set()
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 123}})
    async def sleep(_seconds):
        pass
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr(asyncio, "sleep", sleep)
    asyncio.run(channel._deliver_reminders())
    item = store.history("12345")[0]
    assert item["id"] == rid and item["delivered_at"]
    assert item["telegram_message_id"] == 123
    assert item["retry_count"] == 1
