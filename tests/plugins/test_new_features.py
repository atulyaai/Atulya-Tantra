import pytest
from tools.plugins.productivity.expenses import ExpenseStore, parse_transaction_sms
from tools.plugins.system.smart_home import execute_smart_home
from tools.plugins.toolkit import PluginContext
from tools.plugins.system.agents import AgentHub


def test_smart_home_scenes_and_actions(monkeypatch):
    import asyncio
    import httpx
    from tools.plugins.system import smart_home
    # Scenes are not wired to Home Assistant yet: honest "unsupported", never "Triggered".
    movie = asyncio.run(execute_smart_home("living room", "movie_mode"))
    assert "unsupported" in movie and "Triggered" not in movie

    # Direct action reports success only when Home Assistant accepts it.
    monkeypatch.setenv("HASS_URL", "https://hass.example")
    monkeypatch.setenv("HASS_TOKEN", "t")
    sent = []
    real_client = httpx.AsyncClient

    def fake_client(**kwargs):
        def handler(request):
            sent.append(request.url.path)
            return httpx.Response(200, json=[])
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(smart_home.httpx, "AsyncClient", fake_client)
    lamp = asyncio.run(execute_smart_home("Desk Lamp", "turn_on", brightness=75))
    assert sent == ["/api/services/light/turn_on"]
    assert "Desk Lamp" in lamp
    assert "75%" in lamp


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
    assert "Queued job" in res_tv and "not confirmed" in res_tv
    assert "Casting to" not in res_tv

    # Visual inspect
    res_cam = asyncio.run(_visual_inspect({"device": "Phone", "question": "Who is at the door?"}, ctx))
    assert "Queued photo job" in res_cam and "not confirmed" in res_cam
    assert "Triggered" not in res_cam
