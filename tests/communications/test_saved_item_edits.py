import asyncio
from datetime import datetime, timedelta, timezone

from tools.plugins.productivity.calendar import CalendarStore
from tools.plugins.productivity.reminders import ReminderStore
from tools.plugins.productivity.web_reminders import TelegramReminderAccess
from tools.plugins.registry import PluginContext, build_default_registry
from tools.plugins.toolkit import ActionQueue, Toolbox


def test_requested_telegram_reminder_and_meeting_edits_run_directly_and_persist(project_temp_dir):
    async def exercise():
        store = ReminderStore(project_temp_dir)
        calendar = CalendarStore(project_temp_dir)
        queue = ActionQueue(project_temp_dir)
        view = queue.view()
        ctx = PluginContext("web", None, calendar, "admin", actions=view, channel="telegram",
                            reminders=TelegramReminderAccess(store, "12345", "12345"))
        toolbox = Toolbox.for_registry(build_default_registry(), ctx)
        names = {t["function"]["name"] for t in toolbox.schemas}
        assert "media_control" not in names and "open_app" not in names
        assert "edit_reminder" in names and "remove_meeting" in names
        result = await toolbox.call("create_reminder", {"message": "Test", "delay_minutes": 5})
        assert "Telegram message" in result
        item = store.list_for_user("12345")[0]
        await toolbox.call("edit_reminder", {"id": item["id"], "message": "Changed"})
        assert store.list_for_user("12345")[0]["message"] == "Changed"
        assert not store.cancel("99999", item["id"])
        await toolbox.call("cancel_reminder", {"id": item["id"]})
        assert store.list_for_user("12345") == []
        assert store.claim_due(datetime.now(timezone.utc) + timedelta(hours=1)) == []
        meeting = calendar.add("web", "Test meeting", datetime.now(timezone.utc) + timedelta(hours=1))
        await toolbox.call("edit_meeting", {"id": meeting["id"], "title": "Updated meeting"})
        assert calendar.list("web")[0]["title"] == "Updated meeting"
        await toolbox.call("remove_meeting", {"id": meeting["id"]})
        assert calendar.list("web") == []
        assert view.created == []
    asyncio.run(exercise())
