from atulya.inbox import Inbox
from atulya.profiles import ProfileStore
from tools.plugins.productivity.briefing import apply_briefing_schedule
from tools.plugins.productivity.routines import RoutineStore


def test_briefing_settings_round_trip_and_schedule(tmp_path):
    store = ProfileStore(tmp_path)
    saved = store.set_briefing("admin", time="7:15", topics="india, world", channel="app", city="Pune")
    assert saved["time"] == "07:15"
    assert saved["topics"] == ["india", "world"]
    assert saved["channel"] == "app"
    assert saved["city"] == "Pune"
    note = apply_briefing_schedule(tmp_path, saved)
    item = RoutineStore(tmp_path).list_items()[0]
    assert item["when"] == "07:15" and item["enabled"] is True and "Added" in note
    off = store.set_briefing("admin", channel="off")
    apply_briefing_schedule(tmp_path, off)
    assert RoutineStore(tmp_path).list_items()[0]["enabled"] is False


def test_inbox_dedupes_and_delivers_once(tmp_path):
    box = Inbox(tmp_path)
    first = box.add("admin", "Morning", "Short rain note", "briefing", dedupe="rain:2026-10-22")
    again = box.add("admin", "Morning", "Short rain note", "briefing", dedupe="rain:2026-10-22")
    assert first == again
    pulled = box.pull("admin")
    assert len(pulled) == 1 and pulled[0]["title"] == "Morning"
    assert box.pull("admin") == []
