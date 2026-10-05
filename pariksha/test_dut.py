import pytest
from fastapi.testclient import TestClient

from atulya import dut
from atulya import dwar as users
from atulya.sevak import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ATULYA_AGENT_DATA_DIR", str(tmp_path / "agent"))
    monkeypatch.setattr(users, "USERS_FILE", tmp_path / "users.json")
    monkeypatch.setattr(users, "SESSIONS_FILE", tmp_path / "sessions.json")
    monkeypatch.setattr(users, "ADMIN_TOKEN", "phone-admin")
    users._sessions.clear()
    return TestClient(app)


def test_remote_queue_is_device_scoped_and_results_are_bounded(tmp_path, monkeypatch):
    monkeypatch.setenv("ATULYA_AGENT_DATA_DIR", str(tmp_path))
    first = dut.enqueue("computer-1", "diagnose", {})
    dut.enqueue("computer-2", "list_dir", {"path": "Desktop"})
    queue = dut.poll("computer-1", "read")
    assert [row["id"] for row in queue] == [first["id"]]
    assert queue[0]["permission"] == "read"
    assert not dut.poll("computer-1")
    assert dut.result("computer-2", queue[0]["id"], {"ok": True}) is False
    assert dut.result("computer-1", queue[0]["id"], {"ok": True, "output": "ready"}) is True
    assert dut.recent_results("computer-1")[0]["result"]["output"] == "ready"
    with pytest.raises(ValueError):
        dut.enqueue("computer-1", "shell", {"command": "whoami"})


def test_remote_agent_api_requires_a_paired_computer(client):
    admin = {"X-Atulya-Token": "phone-admin"}
    code = client.post("/api/pairing/code", json={"permission": "full"}, headers=admin).json()["code"]
    phone = client.post("/api/pairing/enroll", json={"code": code, "name": "A phone", "kind": "phone"}).json()
    assert client.get("/agent/commands", headers={"X-Atulya-Token": phone["token"]}).status_code == 403

    code = client.post("/api/pairing/code", json={"permission": "read"}, headers=admin).json()["code"]
    computer = client.post("/api/pairing/enroll", json={"code": code, "name": "Work laptop", "kind": "computer"}).json()
    queued = client.post("/api/agent/computer/commands", json={
        "device_id": computer["device"]["id"], "operation": "diagnose", "arguments": {},
    }, headers=admin)
    assert queued.status_code == 200
    poll = client.get("/agent/commands", headers={"X-Atulya-Token": computer["token"]})
    assert poll.json()["commands"][0]["permission"] == "read"
    command_id = poll.json()["commands"][0]["id"]
    assert client.post(f"/agent/results/{command_id}", json={"result": {"ok": True}},
                       headers={"X-Atulya-Token": computer["token"]}).status_code == 200
