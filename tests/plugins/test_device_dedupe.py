import pytest

from tools.plugins.system.agents import AgentHub


def test_near_duplicate_device_names_are_rejected(tmp_path):
    hub = AgentHub(tmp_path)
    hub.pair("owner", "My Laptop", ["ping"])
    for name in ("my laptop", "My-Laptop", "MY_LAPTOP", "mylaptop"):
        with pytest.raises(ValueError, match="already paired"):
            hub.pair("owner", name, ["ping"])
    assert [d["name"] for d in hub.devices("owner")] == ["My Laptop"]


def test_same_name_allowed_after_revoke_and_for_other_owner(tmp_path):
    hub = AgentHub(tmp_path)
    hub.pair("owner", "Desktop", ["ping"])
    hub.pair("someone-else", "Desktop", ["ping"])
    assert hub.revoke("owner", "Desktop")
    hub.pair("owner", "desktop", ["ping"])
    assert [d["name"] for d in hub.devices("owner")] == ["desktop"]


def test_repaired_device_does_not_inherit_old_jobs(tmp_path):
    hub = AgentHub(tmp_path)
    hub.pair("owner", "Desktop", ["ping"])
    hub.enqueue("owner", "Desktop", "ping")
    hub.revoke("owner", "Desktop")
    hub.pair("owner", "Desktop", ["ping"])
    assert {job["device"] for job in hub.jobs("owner")} == {"Desktop (revoked)"}
