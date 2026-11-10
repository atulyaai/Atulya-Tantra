"""Proactive alerts (GOAL M10): quiet hours, per-kind switches, dedupe, and the reason for each one."""
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from atulya import proactive
from atulya.inbox import Inbox

NOW = datetime(2026, 11, 11, 9, 0, tzinfo=timezone.utc)


def at(hour, minute=0, day=11):
    return datetime(2026, 11, day, hour, minute, tzinfo=timezone.utc)


def test_quiet_hours_handle_the_midnight_wrap():
    quiet = {"start": "22:30", "end": "07:00"}
    assert proactive.in_quiet_hours(at(23, 0), quiet) is True
    assert proactive.in_quiet_hours(at(3, 0), quiet) is True
    assert proactive.in_quiet_hours(at(7, 0), quiet) is False
    assert proactive.in_quiet_hours(at(12, 0), quiet) is False
    assert proactive.in_quiet_hours(at(22, 29), quiet) is False
    assert proactive.in_quiet_hours(at(22, 30), quiet) is True


def test_a_same_day_window_and_bad_input_never_silence_everything():
    assert proactive.in_quiet_hours(at(13, 0), {"start": "13:00", "end": "14:00"}) is True
    assert proactive.in_quiet_hours(at(14, 30), {"start": "13:00", "end": "14:00"}) is False
    assert proactive.in_quiet_hours(at(3, 0), {"start": "nonsense", "end": "07:00"}) is False
    assert proactive.in_quiet_hours(at(3, 0), {"start": "07:00", "end": "07:00"}) is False


def test_settings_defaults_merge_and_reject_a_bad_clock(tmp_path):
    saved = proactive.save_settings(tmp_path, {"quiet_start": "21:05", "battery": False})
    assert saved["quiet_hours"]["start"] == "21:05"
    assert saved["kinds"]["battery"] is False
    assert saved["kinds"]["disk"] is True
    assert proactive.load_settings(tmp_path) == saved
    with pytest.raises(ValueError):
        proactive.save_settings(tmp_path, {"quiet_end": "25:00"})
    with pytest.raises(ValueError):
        proactive.save_settings(tmp_path, {"enabled": "yes"})
    # A corrupt file must not take the alert loop down.
    (Path(tmp_path) / "proactive.json").write_text("{not json", encoding="utf-8")
    assert proactive.load_settings(tmp_path)["enabled"] is True


def test_disk_alert_carries_the_measurement_as_its_reason():
    alerts = proactive.build_alerts(NOW, disk_percent=93.4)
    disk = [a for a in alerts if a.kind == "disk"]
    assert len(disk) == 1
    assert "93%" in disk[0].reason and "90%" in disk[0].reason
    assert proactive.build_alerts(NOW, disk_percent=42.0) == []


def test_battery_alert_only_when_discharging():
    low = proactive.build_alerts(NOW, battery_percent=9, battery_charging=False)
    assert [a.kind for a in low] == ["battery"]
    assert "not charging" in low[0].reason
    assert proactive.build_alerts(NOW, battery_percent=9, battery_charging=True) == []


def test_rain_alert_uses_the_forecast_probability():
    rain = {"minutes": 45, "probability": 72, "at": "18:30", "city": "Sangam Vihar", "key": "2026-11-11T18"}
    alerts = proactive.build_alerts(NOW, rain=rain)
    assert [a.kind for a in alerts] == ["rain"]
    assert "Rain in 45 minutes" in alerts[0].title
    assert "72%" in alerts[0].reason and "Sangam Vihar" in alerts[0].reason
    assert alerts[0].dedupe == "rain:2026-11-11T18"


def test_no_rain_alert_when_the_forecast_chance_is_low_or_missing():
    assert proactive.build_alerts(NOW, rain={"minutes": 30, "probability": 5, "at": "10:00", "city": "Pune", "key": "k"}) == []
    assert proactive.build_alerts(NOW, rain=None) == []
    assert proactive.build_alerts(NOW, rain={"minutes": 30}) == []


def test_calendar_alert_only_inside_the_window():
    soon = {"id": 7, "title": "Standup", "starts_at": (NOW + timedelta(minutes=10)).isoformat()}
    later = {"id": 8, "title": "Lunch", "starts_at": (NOW + timedelta(minutes=45)).isoformat()}
    alerts = proactive.build_alerts(NOW, events=[soon, later])
    assert [a.kind for a in alerts] == ["calendar_soon"]
    assert alerts[0].title.startswith("In 10 minutes: Standup")
    assert "Standup" in alerts[0].reason


def test_goal_follow_up_waits_six_hours_and_expires():
    fresh = {"id": "a", "goal": "Sort invoices", "status": "waiting_approval",
             "updated": NOW.timestamp() - 3600}
    stale = {"id": "b", "goal": "Clean downloads", "status": "running",
             "updated": NOW.timestamp() - 8 * 3600}
    ancient = {"id": "c", "goal": "Old", "status": "running",
               "updated": NOW.timestamp() - 5 * 24 * 3600}
    done = {"id": "d", "goal": "Finished", "status": "succeeded",
            "updated": NOW.timestamp() - 8 * 3600}
    alerts = proactive.build_alerts(NOW, goals=[fresh, stale, ancient, done])
    assert len(alerts) == 1
    assert alerts[0].kind == "goal_followup" and "Clean downloads" in alerts[0].title
    assert "8 hours" in alerts[0].reason


def test_tick_respects_switches_quiet_hours_and_dedupe(tmp_path):
    delivered = []
    sent = proactive.tick(tmp_path, NOW, disk_percent=95, deliver=delivered.append)
    assert [a["kind"] for a in sent] == ["disk"] and len(delivered) == 1
    # A second tick on the same day records nothing new and does not deliver again.
    assert proactive.tick(tmp_path, NOW, disk_percent=95, deliver=delivered.append) == []
    assert len(delivered) == 1
    # The rain kind goes through the same switches and dedupe.
    proactive.save_settings(tmp_path, {"rain": False})
    assert proactive.tick(tmp_path, NOW + timedelta(days=1), rain={"minutes": 20, "probability": 80, "at": "15:00", "city": "Pune", "key": "2026-11-12T15"}) == []
    proactive.save_settings(tmp_path, {"rain": True})
    rained = proactive.tick(tmp_path, NOW + timedelta(days=1), rain={"minutes": 20, "probability": 80, "at": "15:00", "city": "Pune", "key": "2026-11-12T15"})
    assert [a["kind"] for a in rained] == ["rain"]
    # Switching the kind off stops the next alert type.
    proactive.save_settings(tmp_path, {"disk": False})
    assert proactive.tick(tmp_path, NOW + timedelta(days=1), disk_percent=95) == []
    # Quiet hours stop everything, including a fresh day's alert.
    proactive.save_settings(tmp_path, {"disk": True, "quiet_start": "08:00", "quiet_end": "10:00"})
    assert proactive.tick(tmp_path, NOW + timedelta(days=2), disk_percent=95) == []


def test_tick_does_nothing_when_the_owner_switches_alerts_off(tmp_path):
    proactive.save_settings(tmp_path, {"enabled": False})
    assert proactive.tick(tmp_path, NOW, disk_percent=99) == []
    assert Inbox(tmp_path).recent("admin") == []


def test_explain_returns_the_stored_reason(tmp_path):
    proactive.tick(tmp_path, NOW, disk_percent=91)
    rows = proactive.explain(tmp_path)
    assert len(rows) == 1
    assert rows[0]["kind"] == "disk"
    assert "91%" in rows[0]["reason"]


def test_a_failing_channel_does_not_drop_the_recorded_alert(tmp_path):
    def boom(_alert):
        raise RuntimeError("telegram down")

    sent = proactive.tick(tmp_path, NOW, disk_percent=92, deliver=boom)
    assert len(sent) == 1
    assert len(Inbox(tmp_path).recent("admin")) == 1


def test_old_inbox_databases_get_the_reason_column(tmp_path):
    path = Path(tmp_path) / "inbox.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE notices (id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, "
                   "title TEXT NOT NULL, body TEXT NOT NULL, kind TEXT NOT NULL, "
                   "dedupe TEXT NOT NULL DEFAULT '', created INTEGER NOT NULL, "
                   "delivered INTEGER NOT NULL DEFAULT 0)")
        db.execute("INSERT INTO notices VALUES(1,'admin','Old','Body','notice','',0,0)")
    box = Inbox(tmp_path)
    assert box.recent("admin")[0]["reason"] == ""
    box.add("admin", "New", "Body", "disk", dedupe="d", reason="because")
    assert {row["title"]: row["reason"] for row in box.recent("admin")}["New"] == "because"


def test_snapshot_providers_survive_a_missing_goal_store(tmp_path):
    values = proactive.snapshot_providers(tmp_path)
    assert set(values) == {"disk_percent", "battery_percent", "battery_charging", "rain", "events", "goals"}
    assert isinstance(values["goals"], list)
    # The settings file is readable JSON after a save, so the web UI can show it.
    proactive.save_settings(tmp_path, {"quiet_start": "23:00"})
    assert json.loads((Path(tmp_path) / "proactive.json").read_text(encoding="utf-8"))["quiet_hours"]["start"] == "23:00"


def admin_ctx(is_admin=True):
    from tools.plugins.registry import PluginContext
    return PluginContext("owner", None, None, "owner-id", is_admin=is_admin)


def test_alert_tools_refuse_everyone_but_the_owner(tmp_path):
    import asyncio

    from tools.plugins.toolkit import TOOLS_BY_NAME
    for name in ("alerts", "set_alerts"):
        reply = asyncio.run(TOOLS_BY_NAME[name].handler({}, admin_ctx(False)))
        assert "Only the owner" in reply


def test_set_alerts_answers_with_what_changed(tmp_path, monkeypatch):
    import asyncio

    from tools.plugins.toolkit import TOOLS_BY_NAME
    monkeypatch.setenv("ATULYA_DATA_DIR", str(tmp_path))
    reply = asyncio.run(TOOLS_BY_NAME["set_alerts"].handler(
        {"quiet_start": "23:15", "quiet_end": "06:45", "battery": False}, admin_ctx()))
    assert "23:15-06:45" in reply and "battery" in reply
    saved = proactive.load_settings(tmp_path)
    assert saved["quiet_hours"] == {"start": "23:15", "end": "06:45"}
    assert saved["kinds"]["battery"] is False
    shown = asyncio.run(TOOLS_BY_NAME["set_alerts"].handler({}, admin_ctx()))
    assert "23:15-06:45" in shown
