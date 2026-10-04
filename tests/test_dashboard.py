import time

from fastapi.testclient import TestClient

from atulya.server.routes.dashboard import build_dashboard


def make(is_admin=True, **over):
    now = time.time()
    args = dict(
        audit=[{"event": "tool", "name": "play_music", "args": {"query": "lofi"}, "t": now},
               {"event": "tool", "name": "pc_hotkey", "t": now},
               {"event": "web_task.step", "goal": "add shoes", "action": "click", "url": "u"},
               {"event": "web_task.handoff", "goal": "add shoes", "url": "u", "reason": "payment is yours"}],
        speeds={"Groq": {"avg": 0.8}, "Local": {"avg": 12.0}, "Dead": {"failed_until": 1e12}}, ready=["Groq"],
        calendar=[{"title": "Standup", "time": now + 600, "duration": 30}, {"title": "Old", "time": now - 99, "duration": 5},
                  {"title": "Far", "time": now + 30 * 86400, "duration": 5}],
        reminders=[{"message": "stretch", "scheduled_time": now + 60}],
        devices={"lamp": {"name": "Lamp", "type": "light", "state": "off"}}, simulated_home=True, pc_on=False,
        is_admin=is_admin, now=now)
    args.update(over)
    return build_dashboard(**args)


def test_tiles_come_from_real_sources():
    d = make()
    assert [e["title"] for e in d["calendar"]["events"]] == ["Standup"]       # past and far-future events dropped
    assert d["calendar"]["reminders"][0]["message"] == "stretch"
    assert d["media"]["now_playing"] == "lofi"
    assert d["system"]["fastest"] == "Groq" and d["system"]["latency"] == 0.8   # measured, fastest first
    assert [b["name"] for b in d["system"]["brains"]] == ["Groq", "Local"]
    assert d["pc"]["recent"][0]["name"] == "pc_hotkey" and d["pc"]["control"] is False
    assert d["web"]["state"] == "finished" and d["web"]["steps"][-1]["note"] == "payment is yours"
    assert d["home"]["simulated"] is True and d["home"]["devices"][0]["id"] == "lamp"


def test_non_admins_do_not_get_system_details():
    d = make(is_admin=False)
    assert "system" not in d and "pc" not in d and "web" not in d and "calendar" in d


def test_idle_web_state_when_nothing_ran():
    assert make(audit=[])["web"]["state"] == "idle"


def test_routes_need_login_and_guard_locks(monkeypatch):
    from atulya.server.app import app
    from atulya.server.state import ADMIN_TOKEN

    c = TestClient(app)
    assert c.get("/api/dashboard").status_code in (401, 403)
    h = {"X-Atulya-Token": ADMIN_TOKEN}
    assert c.get("/api/dashboard", headers=h).json()["sections"]
    assert c.post("/api/dashboard/home", json={"device_id": "front_door", "action": "on"}, headers=h).status_code == 400
    assert c.post("/api/dashboard/home", json={"device_id": "living_room_light", "action": "unlock"}, headers=h).status_code == 400


def test_brain_tool_calls_are_audited(tmp_path, monkeypatch):
    import asyncio

    from atulya.agent.audit import recent
    from atulya.agent.tools import TOOL_REGISTRY
    from atulya.cognition.toolbelt import AgentToolAdapter

    monkeypatch.setenv("ATULYA_AGENT_DATA_DIR", str(tmp_path))
    adapter = AgentToolAdapter("current_time", TOOL_REGISTRY["current_time"])
    assert asyncio.run(adapter.execute()).success
    assert recent(5)[-1]["event"] == "tool" and recent(5)[-1]["name"] == "current_time"


def test_no_brain_message_is_not_ranked_as_a_brain():
    from atulya import intelligence as ai

    ai._SPEED.pop("No brain loaded", None)
    ai._record_speed("No brain loaded", 0.0)
    assert "No brain loaded" not in ai._SPEED


def test_calendar_survives_a_restart(tmp_path, monkeypatch):
    import json

    from atulya.agent import tools

    (tmp_path / "calendar.json").write_text(json.dumps([{"id": "e1", "title": "Client call", "time": 4e9, "duration": 30}]))
    monkeypatch.setattr(tools, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(tools, "_CALENDAR", {})
    tools._bootstrap()
    assert tools._CALENDAR["e1"]["title"] == "Client call"
