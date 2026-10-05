"""Phone sync uses the paired-device store and never shares the bank-SMS inbox route."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from atulya import dwar as users
from atulya import phone
from atulya.sevak import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ATULYA_AGENT_DATA_DIR", str(tmp_path / "agent"))
    monkeypatch.setattr(users, "USERS_FILE", tmp_path / "users.json")
    monkeypatch.setattr(users, "SESSIONS_FILE", tmp_path / "sessions.json")
    monkeypatch.setattr(users, "ADMIN_TOKEN", "phone-admin")
    users._sessions.clear()
    return TestClient(app)


def pair_phone(client, permission="read"):
    code = client.post("/api/pairing/code", json={"permission": permission},
                       headers={"X-Atulya-Token": "phone-admin"}).json()["code"]
    return client.post("/api/pairing/enroll", json={"code": code, "name": "Test phone", "kind": "phone"}).json()


def test_phone_data_requires_phone_token_and_items_array(client):
    assert client.post("/api/phone/sms", json={"items": []}).status_code == 401
    device = pair_phone(client)
    headers = {"X-Atulya-Token": device["token"]}
    assert client.post("/api/phone/sms", json={"message": "not an array"}, headers=headers).status_code == 422
    first = client.post("/api/phone/sms", json={"items": [{"from": "+15550001", "body": "hello"}]}, headers=headers)
    assert first.status_code == 200 and first.json()["added"] == 1
    duplicate = client.post("/api/phone/sms", json={"items": [{"from": "+15550001", "body": "hello"}]}, headers=headers)
    assert duplicate.status_code == 200 and duplicate.json()["duplicates"] == 1
    assert client.get("/api/phone/inbox", headers=headers).status_code == 403
    # Paired devices must not receive the secret used to ingest bank SMS.
    assert client.get("/api/money/inbox", headers=headers).status_code == 403
    assert client.get("/api/phone/inbox", headers={"X-Atulya-Token": "phone-admin"}).json()["items"][0]["item"]["body"] == "hello"


def test_phone_endpoints_reject_wrong_kind_and_bound_batches(client):
    code = client.post("/api/pairing/code", json={}, headers={"X-Atulya-Token": "phone-admin"}).json()["code"]
    other = client.post("/api/pairing/enroll", json={"code": code, "name": "Laptop", "kind": "computer"}).json()
    assert client.post("/api/phone/location", json={"items": []}, headers={"X-Atulya-Token": other["token"]}).status_code == 403
    device = pair_phone(client)
    token = {"X-Atulya-Token": device["token"]}
    assert client.post("/api/phone/location", json={"items": ["not an object"]}, headers=token).status_code == 422
    assert client.post("/api/phone/location", json={"items": [{"body": "x" * 5000}]}, headers=token).status_code == 422
    assert client.post("/api/phone/other", json={"items": []}, headers=token).status_code == 404


def test_phone_commands_require_full_permission_and_are_device_scoped(client):
    read_phone = pair_phone(client, "read")
    full_phone = pair_phone(client, "full")
    admin = {"X-Atulya-Token": "phone-admin"}
    devices = client.get("/api/phone/devices", headers=admin).json()["devices"]
    full_id = full_phone["device"]["id"]
    assert client.post(f"/api/phone/devices/{full_id}/commands", json={"action": "ring"}, headers=admin).status_code == 200
    assert client.get("/api/phone/commands", headers={"X-Atulya-Token": read_phone["token"]}).status_code == 403
    poll = client.get("/api/phone/commands", headers={"X-Atulya-Token": full_phone["token"]})
    command = poll.json()["commands"][0]
    assert command["action"] == "ring"
    assert client.post(f"/api/phone/commands/{command['id']}/result", json={"result": {"ok": True}},
                       headers={"X-Atulya-Token": read_phone["token"]}).status_code == 403
    assert client.post(f"/api/phone/commands/{command['id']}/result", json={"result": {"ok": True}},
                       headers={"X-Atulya-Token": full_phone["token"]}).status_code == 200
    assert all(d["kind"] == "phone" for d in devices)


def test_phone_store_deduplicates_and_clears_by_category(tmp_path, monkeypatch):
    monkeypatch.setenv("ATULYA_AGENT_DATA_DIR", str(tmp_path / "agent"))
    assert phone.add_items("notifications", "device-1", [{"title": "Atulya"}]) == {"received": 1, "added": 1, "duplicates": 0}
    assert phone.add_items("notifications", "device-1", [{"title": "Atulya"}])["duplicates"] == 1
    assert phone.add_items("notifications", "device-2", [{"title": "Atulya"}])["added"] == 1
    assert phone.clear_items("notifications") == 2
    assert phone.list_items() == []
    with pytest.raises(ValueError, match="JSON object"):
        phone.add_items("sms", "device-1", ["not an object"])
