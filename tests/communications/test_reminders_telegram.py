from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tools.plugins.communications.channels.telegram import TelegramChannel, _parse_due
from tools.plugins.personal.memory import PersonalMemory
from tools.plugins.productivity.calendar import CalendarStore
from tools.plugins.productivity.reminders import ReminderStore
from tools.plugins.registry import build_default_registry


def _run_immediate(coroutine):
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    raise AssertionError("Fake Telegram request unexpectedly suspended")


def test_telegram_uses_shared_command_registry(project_temp_dir: Path) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            pass

    class FakeClient:
        sent: list[dict] = []

        async def post(self, _url: str, *, json: dict) -> FakeResponse:
            self.sent.append(json)
            return FakeResponse()

    client = FakeClient()
    channel = TelegramChannel(
        token="test", allowed_user_ids={"12345"}, brain=None,
        history=None, reminders=ReminderStore(project_temp_dir), status_summary=lambda: "ready",
        command_plugins=build_default_registry(),
        personal_memory=PersonalMemory(project_temp_dir), calendar=CalendarStore(project_temp_dir),
    )

    _run_immediate(channel._handle_message(client, {
        "from": {"id": 12345}, "chat": {"id": 12345, "type": "private"},
        "message_id": 1, "text": "calculate 24 * 7",
    }))
    assert client.sent == [{"chat_id": "12345", "text": "168"}]


def test_reminder_is_private_persistent_and_delivered_once(project_temp_dir: Path) -> None:
    store = ReminderStore(project_temp_dir)
    due = datetime.now(timezone.utc) + timedelta(minutes=10)
    store.add("12345", "12345", "call home", due)

    assert [item["message"] for item in store.list_for_user("12345")] == ["call home"]
    assert store.list_for_user("99999") == []
    assert store.claim_due(datetime.now(timezone.utc)) == []
    ready = store.claim_due(due + timedelta(seconds=1))
    assert [item["message"] for item in ready] == ["call home"]
    assert store.claim_due(due + timedelta(seconds=2)) == []
    store.mark_delivered(int(ready[0]["id"]), due + timedelta(seconds=2))
    assert store.claim_due(due + timedelta(minutes=1)) == []


def test_reminder_retries_with_backoff_and_stops_after_five_failures(project_temp_dir: Path) -> None:
    store = ReminderStore(project_temp_dir)
    due = datetime.now(timezone.utc) + timedelta(minutes=10)
    reminder_id = store.add("12345", "12345", "retry safely", due)
    now = due + timedelta(seconds=1)

    for attempt in range(5):
        claimed = store.claim_due(now)
        assert [int(item["id"]) for item in claimed] == [reminder_id]
        store.retry_failed(reminder_id, now)
        now += timedelta(minutes=2 ** min(attempt, 5), seconds=1)

    assert store.claim_due(now + timedelta(days=1)) == []
    assert store.list_for_user("12345") == []


def test_reminder_time_parser_supports_relative_and_iso() -> None:
    now = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
    assert _parse_due("20m", now) == now + timedelta(minutes=20)
    assert _parse_due("in 2 hours", now) == now + timedelta(hours=2)
    assert _parse_due("2026-10-09T14:00:00+05:30", now).astimezone(timezone.utc) == datetime(2026, 10, 9, 8, 30, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        _parse_due("later", now)


def test_strangers_must_register_after_free_messages(tmp_path, monkeypatch) -> None:
    import asyncio

    from atulya.history import ConversationHistory
    from tools.plugins.communications.channels.telegram import TelegramChannel
    from tools.plugins.productivity.reminders import ReminderStore

    monkeypatch.setenv("ATULYA_TELEGRAM_OPEN", "1")
    channel = TelegramChannel(token="1:test", allowed_user_ids={"111"}, brain=None,
                              history=ConversationHistory(tmp_path), reminders=ReminderStore(tmp_path),
                              status_summary=lambda: "", data_dir=tmp_path)
    sent, owner = [], []

    class FakeClient:
        async def post(self, url, json):
            sent.append(json["text"])

            class Ok:
                def raise_for_status(self):
                    return None
            return Ok()

    async def fake_notify(text):
        owner.append(text)
        return 1
    channel.notify = fake_notify

    async def run():
        for n in range(6):
            await channel._guest_message(FakeClient(), "222", "222", str(n), "hello")
        await channel._guest_message(FakeClient(), "222", "222", "r", "/register Rahul")
        return channel._decide_member("222", True)

    approved = asyncio.run(run())
    assert "register" in sent[5].lower()          # 6th message asks to register
    assert "waiting for the owner" in sent[6]
    assert "/approve 222" in owner[0]
    assert approved == "Rahul is now approved."
