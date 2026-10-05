"""Pairing: one-time codes, device tokens that can be cut off, and what a paired device may and may not do."""
import pytest
from fastapi.testclient import TestClient

from atulya import dwar as users
from atulya import raksha as vault
from atulya.sevak import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ATULYA_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(users, "USERS_FILE", tmp_path / "users.json")
    monkeypatch.setattr(users, "SESSIONS_FILE", tmp_path / "sessions.json")
    users._sessions.clear()
    monkeypatch.setattr(users, "ADMIN_TOKEN", "admin-test-token")
    return TestClient(app)


ADMIN = {"X-Atulya-Token": "admin-test-token"}


def pair(client, permission="files", name="Atul's laptop"):
    code = client.post("/api/pairing/code", json={"permission": permission}, headers=ADMIN).json()["code"]
    return client.post("/api/pairing/enroll", json={"code": code, "name": name, "kind": "laptop"}).json()


def test_a_code_works_once_and_gives_a_token(client):
    made = client.post("/api/pairing/code", json={"permission": "files"}, headers=ADMIN).json()
    assert len(made["code"]) == 6 and made["expires_in"] == 600
    first = client.post("/api/pairing/enroll", json={"code": made["code"], "name": "Phone", "kind": "phone"})
    assert first.status_code == 200 and first.json()["token"].startswith("dev_")
    again = client.post("/api/pairing/enroll", json={"code": made["code"], "name": "Other"})
    assert again.status_code == 400


def test_only_an_admin_can_make_codes_or_see_devices(client):
    assert client.post("/api/pairing/code", json={}).status_code in (401, 403)
    assert client.get("/api/pairing/devices").status_code in (401, 403)
    users.create_user("sam", "pw", role="user", display_name="Sam")
    sam = {"X-Atulya-Token": users.create_session("sam")}
    assert client.post("/api/pairing/code", json={}, headers=sam).status_code == 403


def test_the_token_file_holds_only_hashes(client, tmp_path):
    token = pair(client)["token"]
    assert token not in (tmp_path / "paired.json").read_text(encoding="utf-8")


def test_a_paired_device_is_never_an_admin(client):
    token = pair(client, "full")["token"]
    headers = {"X-Atulya-Token": token}
    assert client.get("/api/audit", headers=headers).status_code == 403
    assert client.post("/api/pairing/code", json={}, headers=headers).status_code == 403
    assert client.get("/api/mood", headers=headers).status_code == 200


def test_revoking_cuts_a_device_off_at_once(client):
    done = pair(client)
    headers = {"X-Atulya-Token": done["token"]}
    assert client.get("/api/mood", headers=headers).status_code != 401
    assert client.post(f"/api/pairing/devices/{done['device']['id']}/revoke", headers=ADMIN).status_code == 200
    assert client.get("/api/mood", headers=headers).status_code == 401
    listed = client.get("/api/pairing/devices", headers=ADMIN).json()["devices"]
    assert listed[0]["revoked"] is True


def test_wrong_codes_are_rate_limited(client):
    for _ in range(vault._PAIR_FAILS):
        assert client.post("/api/pairing/enroll", json={"code": "000000"}).status_code == 400
    blocked = client.post("/api/pairing/enroll", json={"code": "000000"})
    assert "Too many" in blocked.json()["detail"]


def test_permission_can_be_changed_and_must_be_valid(client):
    done = pair(client, "read")
    ok = client.post(f"/api/pairing/devices/{done['device']['id']}/permission", json={"permission": "full"}, headers=ADMIN)
    assert ok.status_code == 200
    assert client.get("/api/pairing/devices", headers=ADMIN).json()["devices"][0]["permission"] == "full"
    assert client.post("/api/pairing/code", json={"permission": "root"}, headers=ADMIN).status_code == 400


def test_pairing_is_recorded_in_the_activity_log(client):
    from atulya.kriya import recent, verify_audit

    pair(client)
    assert any(e["event"] == "pairing.enrolled" for e in recent(10)) and verify_audit()["ok"]
