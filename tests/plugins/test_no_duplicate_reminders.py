from datetime import datetime, timedelta, timezone

from tools.plugins.productivity.calendar import CalendarStore
from tools.plugins.productivity.reminders import ReminderStore
from tools.plugins.productivity.web_reminders import WebReminderStore

SOON = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=2)


def test_web_reminder_saved_twice_is_one_row(tmp_path):
    store = WebReminderStore(tmp_path)
    first = store.add("u1", "Call mom", SOON)
    second = store.add("u1", "call mom", SOON)
    assert second["id"] == first["id"] and second["duplicate"]
    assert len(store.list("u1")) == 1
    assert store.add("u1", "Call mom", SOON + timedelta(hours=1))["id"] != first["id"]


def test_telegram_reminder_saved_twice_is_one_row(tmp_path):
    store = ReminderStore(tmp_path)
    assert store.add("1", "2", "Pay rent", SOON) == store.add("1", "2", "Pay rent", SOON)
    assert len(store.list_for_user("1")) == 1


def test_meeting_saved_twice_is_one_event(tmp_path):
    store = CalendarStore(tmp_path)
    first = store.add("owner", "Standup", SOON)
    second = store.add("owner", "Standup", SOON)
    assert second["id"] == first["id"] and second["duplicate"]
    assert len(store.list("owner")) == 1
