import pytest
from tools.plugins.productivity.expenses import ExpenseStore, parse_transaction_sms
from tools.plugins.system.smart_home import execute_smart_home
from tools.plugins.toolkit import PluginContext
from tools.plugins.system.agents import AgentHub


def test_smart_home_scenes_and_actions(monkeypatch):
    import asyncio
    import httpx
    from tools.plugins.system import smart_home

    calls = []

    def handler(request):
        calls.append((request.url.path, request.read().decode()))
        return httpx.Response(200, json=[])

    original = httpx.AsyncClient
    monkeypatch.setattr(smart_home, "HASS_URL", "http://ha.local:8123")
    monkeypatch.setattr(smart_home, "HASS_TOKEN", "token")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw))

    # A scene really calls Home Assistant for every step, and says so only once it is confirmed.
    movie = asyncio.run(execute_smart_home("living room", "movie_mode"))
    assert "Scene 'movie_mode' confirmed by Home Assistant" in movie
    assert calls and all(path.startswith("/api/services/") for path, _ in calls)
    assert "Not done (needs a paired device): tv play" in movie  # the TV step is reported, never faked

    # Direct action
    calls.clear()
    lamp = asyncio.run(execute_smart_home("Desk Lamp", "turn_on", brightness=75))
    assert "Desk Lamp" in lamp and "75%" in lamp
    assert calls[0][0] == "/api/services/light/turn_on" and '"brightness_pct":75' in calls[0][1].replace(" ", "")


def test_expense_store_and_sms_parser(project_temp_dir):
    store = ExpenseStore(project_temp_dir)
    # Manual log
    e = store.log("user1", 350.50, "Blue Tokai Coffee", "Food & Dining", notes="Cappuccino & Croissant")
    assert e["amount"] == 350.50
    assert e["merchant"] == "Blue Tokai Coffee"

    # List recent
    recent = store.list_recent("user1")
    assert len(recent) == 1
    assert recent[0]["merchant"] == "Blue Tokai Coffee"

    # Summary
    summary = store.summary("user1")
    assert summary["total_spent"] == 350.50
    assert summary["total_transactions"] == 1
    assert "Food & Dining" in summary["by_category"]

    # SMS Parser tests (HDFC / GPay / Swiggy / Uber format)
    sms1 = "Dear Customer, Rs. 420.00 spent on your HDFC Bank Card at SWIGGY on 14-OCT-26. Avl bal: Rs 45,000."
    parsed1 = parse_transaction_sms(sms1)
    assert parsed1 is not None
    assert parsed1["amount"] == 420.0
    assert "SWIGGY" in parsed1["merchant"].upper()
    assert parsed1["category"] == "Food & Dining"

    sms2 = "Paid Rs 310 to Uber India via UPI ref 42819283."
    parsed2 = parse_transaction_sms(sms2)
    assert parsed2 is not None
    assert parsed2["amount"] == 310.0
    assert "UBER" in parsed2["merchant"].upper()
    assert parsed2["category"] == "Travel & Commute"

    # Negative amount error
    with pytest.raises(ValueError):
        store.log("user1", -10, "Invalid")


def test_visual_inspect_and_cast_to_tv(project_temp_dir, monkeypatch):
    monkeypatch.setenv("ATULYA_DATA_DIR", str(project_temp_dir))
    hub = AgentHub(project_temp_dir)
    hub.pair("alice", "Living Room TV", ["open_url", "media_control"])
    hub.pair("alice", "Phone", ["take_photo"])

    from tools.plugins.toolkit import _cast_to_tv, _visual_inspect
    import asyncio
    ctx = PluginContext("alice", None, None, "alice")

    # Cast to TV
    res_tv = asyncio.run(_cast_to_tv({"tv": "Living Room TV", "url": "https://youtube.com/watch?v=demo"}, ctx))
    assert "Queued a cast to Living Room TV" in res_tv and "not confirmed" in res_tv

    # Visual inspect
    res_cam = asyncio.run(_visual_inspect({"device": "Phone", "question": "Who is at the door?"}, ctx))
    assert "Queued a photo capture on Phone" in res_cam and "Not taken yet" in res_cam
