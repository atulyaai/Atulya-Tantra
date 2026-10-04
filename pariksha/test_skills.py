"""Music, tracking, briefing, PC control and the audit log."""
import asyncio
import json

import pytest

from atulya import lekha as audit_mod
from atulya import sahayak as pc_control, kriya as tools, sahayak as tracking
from atulya.maryada import assess


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("ATULYA_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(tools, "_DATA_DIR", tmp_path)
    return tmp_path


def run(coro):
    return asyncio.run(coro)


def test_skill_tools_are_registered():
    for name in ("play_music", "media_control", "track_add", "track_check", "morning_briefing", "pc_open_app"):
        assert name in tools.TOOL_REGISTRY


def test_play_music_opens_search(monkeypatch):
    opened = []
    import webbrowser

    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url) or True)
    out = run(tools.execute_tool("play_music", query="lofi beats", service="spotify"))
    assert "Spotify" in out and "lofi" in opened[0]


def test_media_control_rejects_unknown_action():
    assert "I can do" in run(tools.execute_tool("media_control", action="explode"))


def test_extract_price():
    assert tracking.extract_price("<b>Price: ₹1,299.50</b>") == 1299.5
    assert tracking.extract_price("nothing here") is None


def test_tracking_refuses_local_network():
    assert not tracking._is_public_url("http://127.0.0.1:8501/")
    assert not tracking._is_public_url("http://192.168.1.5/admin")
    assert not tracking._is_public_url("file:///etc/passwd")
    assert "public" in run(tools.execute_tool("track_add", label="x", url="http://localhost/"))


def test_track_add_check_remove(monkeypatch):
    monkeypatch.setattr(tracking, "_is_public_url", lambda url: True)
    prices = iter(["$100", "$80"])
    monkeypatch.setattr(tracking, "_fetch", lambda url: next(prices))
    out = run(tools.execute_tool("track_add", label="Phone", url="https://shop.example/p", alert_below=90))
    tid = out.split("id ")[1].rstrip(").")
    assert "Phone" in run(tools.execute_tool("track_list"))
    assert "100" in run(tools.execute_tool("track_check"))
    second = run(tools.execute_tool("track_check"))
    assert "down from 100" in second and "below your target" in second
    assert "Stopped" in run(tools.execute_tool("track_remove", track_id=tid))
    assert "not tracking" in run(tools.execute_tool("track_list"))


def test_briefing_includes_sections():
    out = run(tools.execute_tool("morning_briefing"))
    assert "Calendar:" in out and "Reminders:" in out


def test_pc_control_off_by_default(monkeypatch):
    monkeypatch.delenv("ATULYA_PC_CONTROL", raising=False)
    assert run(tools.execute_tool("pc_type", text="hi")) == pc_control.DISABLED


def test_pc_control_allowlist_and_blocked_hotkeys(monkeypatch):
    monkeypatch.setenv("ATULYA_PC_CONTROL", "on")
    assert "only open" in run(tools.execute_tool("pc_open_app", app="powershell"))
    assert "won't" in run(tools.execute_tool("pc_hotkey", keys="alt+f4"))


def test_pc_control_always_needs_confirmation():
    for name in ("pc_open_app", "pc_type", "pc_hotkey", "pc_screenshot"):
        assert assess(name, {}).needs_confirmation


def test_audit_log_records_tools_and_hides_secrets(data_dir):
    run(tools.execute_tool("current_time"))
    audit_mod.audit("login", password="hunter2", user="aj")
    events = audit_mod.recent()
    assert any(e.get("name") == "current_time" for e in events)
    login = [e for e in events if e["event"] == "login"][0]
    assert login["password"] == "***" and "hunter2" not in json.dumps(events)
