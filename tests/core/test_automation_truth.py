import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

from tools.plugins.productivity.routines import RoutineStore
from tools.plugins.productivity.reminders import ReminderStore
from tools.plugins.productivity.web_reminders import WebReminderStore
from tools.plugins.information.news import parse_items
from tools.plugins.information.weather import compact_weather


def test_new_install_never_subscribes_owner_to_automatic_updates(project_temp_dir):
    store = RoutineStore(project_temp_dir)
    store.ensure_defaults()
    assert store.list_items() == []
    routine = store.add("Read", "07:00", action="message", message="Read")
    now = datetime(2026, 10, 14, 7, 5).astimezone()
    assert store.due(now)[0]["id"] == routine["id"]
    assert store.set_enabled(routine["id"], False)
    assert not store.due(now)
    assert not RoutineStore(project_temp_dir).still_enabled(routine["id"])
    store.ensure_defaults()
    assert len(store.list_items()) == 1


def test_bulk_cancellation_is_private_and_survives_restart(project_temp_dir):
    due = datetime.now(timezone.utc) + timedelta(minutes=10)
    web = WebReminderStore(project_temp_dir)
    web.add("alice", "Alice", due)
    web.add("bob", "Bob", due)
    assert web.cancel_all("alice") == 1
    assert web.cancel_all("alice") == 0
    assert WebReminderStore(project_temp_dir).list("alice")[0]["cancelled_at"]
    assert not web.list("bob")[0]["cancelled_at"]
    telegram = ReminderStore(project_temp_dir)
    telegram.add("123", "123", "Alice", due)
    telegram.add("456", "456", "Bob", due)
    assert telegram.cancel_all("123") == 1
    assert not ReminderStore(project_temp_dir).list_for_user("123")
    assert len(telegram.list_for_user("456")) == 1


def test_news_does_not_relabel_other_city_or_stale_items_as_local():
    now = datetime.now(timezone.utc)
    def item(title, link, age):
        return f"<item><title>{title}</title><link>{link}</link><pubDate>{format_datetime(now - age)}</pubDate></item>"
    xml = ("<rss><channel>" + item("Delhi transport update", "https://example.com/new", timedelta(hours=1))
           + item("Mumbai update", "https://example.com/mumbai", timedelta(hours=1))
           + item("Delhi old", "https://example.com/old", timedelta(days=8))
           + item("Delhi unsafe", "javascript:alert(1)", timedelta(hours=1)) + "</channel></rss>").encode()
    rows = parse_items(xml, "Publisher", "Delhi", now)
    assert [r["url"] for r in rows] == ["https://example.com/new"]
    assert rows[0]["source"] == "Publisher"


def test_weather_default_is_compact_and_only_warns_from_measurements():
    data = {"current": {"temperature_2m": 28, "apparent_temperature": 30, "weather_code": 0,
                        "time": "2026-10-14T08:00"},
            "daily": {"time": ["2026-10-14"], "temperature_2m_min": [22], "temperature_2m_max": [30],
                      "precipitation_probability_max": [10]}}
    report = compact_weather(data, {"current": {"us_aqi": 180}}, "Delhi")
    assert "rain 10%" in report and "AQI 180" in report
    assert "Limit prolonged outdoor" in report
    assert "Thunderstorms" not in report
    assert len(report.splitlines()) <= 6


def test_calendar_routine_does_not_turn_into_news(project_temp_dir):
    from tools.plugins.productivity.calendar import CalendarStore
    from tools.plugins.productivity.routine_execution import render_routine
    calendar = CalendarStore(project_temp_dir)
    assert asyncio.run(render_routine({"action": "calendar"}, "Delhi", calendar)) is None
    calendar.add("web", "Appointment", datetime.now(timezone.utc) + timedelta(minutes=30))
    report = asyncio.run(render_routine({"action": "calendar"}, "Delhi", calendar))
    assert "Appointment" in report["text"] and "World" not in report["text"]
