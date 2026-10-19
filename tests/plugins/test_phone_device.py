from tools.plugins.registry import PluginContext
from tools.plugins.system.agents import AgentHub
from tools.plugins.toolkit import TOOLS, Toolbox

PHONE_ABILITIES = ["ping", "battery_status", "open_url", "open_app", "send_sms", "place_call",
                   "media_control", "display_message", "say"]


def test_assistant_knows_whether_a_phone_is_paired(project_temp_dir, monkeypatch):
    monkeypatch.setenv("ATULYA_DATA_DIR", str(project_temp_dir))
    toolbox = Toolbox(TOOLS, PluginContext("alice", None, None, "alice"))
    assert "No phone or computer is paired" in toolbox.instructions()

    hub = AgentHub(project_temp_dir)
    paired = hub.pair("alice", "Phone Pixel 6 a1b2", PHONE_ABILITIES)  # what the Android app registers
    hub.poll("alice", "Phone Pixel 6 a1b2")  # the app is open
    text = Toolbox(TOOLS, PluginContext("alice", None, None, "alice")).instructions()
    assert "Phone Pixel 6 a1b2 — online — " in text and "send_sms" in text

    # Another owner's phone is never offered.
    other = Toolbox(TOOLS, PluginContext("bob", None, None, "bob")).instructions()
    assert "Phone Pixel 6 a1b2" not in other
    assert paired["token"]


def test_phone_job_round_trip_needs_the_device_token(project_temp_dir):
    hub = AgentHub(project_temp_dir)
    token = hub.pair("alice", "Phone Test 0001", PHONE_ABILITIES)["token"]
    assert hub.authenticate(token) == {"owner": "alice", "name": "Phone Test 0001"}
    job = hub.enqueue("alice", "Phone Test 0001", "send_sms", '{"to": "+911234567890", "body": "hi"}')
    assert [item["id"] for item in hub.poll("alice", "Phone Test 0001")] == [job["id"]]
    assert hub.complete("alice", "Phone Test 0001", job["id"], "Denied on the phone.", success=False)
    assert hub.jobs("alice")[0]["status"] == "failed"
    assert hub.revoke("alice", "Phone Test 0001") and hub.authenticate(token) is None
