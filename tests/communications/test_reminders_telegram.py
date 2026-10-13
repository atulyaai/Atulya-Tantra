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


def test_telegram_mini_app_signature_is_verified(tmp_path) -> None:
    import hashlib
    import hmac
    import json
    import time
    from urllib.parse import urlencode

    from atulya.history import ConversationHistory
    from tools.plugins.communications.channels.telegram import TelegramChannel
    from tools.plugins.productivity.reminders import ReminderStore

    token = "123:secret-test-token"
    channel = TelegramChannel(token=token, allowed_user_ids={"111"}, brain=None, history=ConversationHistory(tmp_path),
                              reminders=ReminderStore(tmp_path), status_summary=lambda: "", data_dir=tmp_path)

    def signed(auth_date: int, user_id: int = 111) -> str:
        fields = {"auth_date": str(auth_date), "query_id": "q1", "user": json.dumps({"id": user_id, "first_name": "AJ"})}
        check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
        secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        return urlencode(fields)

    good = signed(int(time.time()))
    assert channel.verify_webapp_data(good)["id"] == 111
    assert channel.web_identity("111") == "owner" and channel.web_identity("999") is None
    assert channel.verify_webapp_data(good.replace("AJ", "XX")) is None          # tampered
    assert channel.verify_webapp_data(signed(int(time.time()) - 200000)) is None  # expired


def test_telegram_approve_button_runs_only_for_its_owner_once(tmp_path) -> None:
    import asyncio

    from atulya.history import ConversationHistory
    from tools.plugins.communications.channels.telegram import TelegramChannel
    from tools.plugins.productivity.reminders import ReminderStore
    from tools.plugins.registry import build_default_registry
    from tools.plugins.toolkit import ActionQueue

    queue = ActionQueue(tmp_path)
    channel = TelegramChannel(token="1:t", allowed_user_ids={"111", "222"}, brain=None, history=ConversationHistory(tmp_path),
                              reminders=ReminderStore(tmp_path), status_summary=lambda: "", data_dir=tmp_path,
                              command_plugins=build_default_registry(), personal_memory=object(), calendar=object(),
                              actions=queue)
    posts = []

    class FakeClient:
        async def post(self, url, json):
            posts.append((url.rsplit("/", 1)[-1], json))

            class Ok:
                def raise_for_status(self):
                    return None
            return Ok()

    action = queue.add("search_files", {"query": "zz-no-such-file-zz"}, "Search files for: zz", "admin")

    async def press(user, data):
        await channel._handle_callback(FakeClient(), {"id": "q", "from": {"id": user}, "data": data,
                                                      "message": {"chat": {"id": user}, "message_id": 5}})
    asyncio.run(press(333, f"act:{action.id}:1"))                 # a stranger: refused
    assert posts[-1][1]["text"] == "Not allowed."
    asyncio.run(press(111, f"act:{action.id}:1"))
    # Server Telegram has no local-PC control grant, including for stale queued actions.
    assert posts[-1][1]["text"] == "That action is no longer available."
    asyncio.run(press(111, f"act:{action.id}:1"))                 # single use
    assert "expired or was already handled" in posts[-1][1]["text"]
