from datetime import datetime, timedelta, timezone
from contextlib import closing

from tools.plugins.productivity.web_reminders import WebReminderStore


def test_reminders_persist_and_acknowledgements_are_owner_scoped(project_temp_dir):
    store = WebReminderStore(project_temp_dir)
    due = datetime.now(timezone.utc) + timedelta(minutes=1)
    item = store.add("alice", "Check delivery", due)
    reopened = WebReminderStore(project_temp_dir)
    assert reopened.list("alice")[0]["id"] == item["id"]
    assert reopened.list("bob") == []
    assert not reopened.update("bob", item["id"])
    assert not reopened.update("alice", item["id"], shown=True)
    assert reopened.list("alice", due_only=True) == []
    import sqlite3
    with closing(sqlite3.connect(store.path)) as db, db:
        db.execute("UPDATE reminders SET due_at=? WHERE id=?",
                   ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), item["id"]))
    assert len(reopened.list("alice", due_only=True)) == 1
    assert reopened.update("alice", item["id"], shown=True)
    assert reopened.list("alice", due_only=True) == []
    assert reopened.list("alice")[0]["shown_at"]
