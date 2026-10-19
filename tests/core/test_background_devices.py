from tools.plugins.system.agents import AgentHub
from fastapi import FastAPI
from fastapi.testclient import TestClient
from atulya.auth import AuthStore
from atulya.device_api import register_device_routes
from atulya.server import SessionAuthMiddleware


def test_background_checks_never_claim_effectful_jobs(project_temp_dir):
    hub = AgentHub(project_temp_dir)
    hub.pair("owner", "phone", ["ping", "battery_status", "send_sms"])
    effect = hub.enqueue("owner", "phone", "send_sms", "example")
    safe = hub.enqueue("owner", "phone", "ping")
    jobs = hub.poll("owner", "phone", passive=True)
    assert [job["id"] for job in jobs] == [safe["id"]]
    assert hub.waiting_for_foreground("owner", "phone") == 1
    assert hub.waiting_for_foreground("other", "phone") == 0
    assert hub.devices("owner")[0]["mode"] == "background"
    assert next(j for j in hub.jobs("owner") if j["id"] == effect["id"])["status"] == "queued"
    assert hub.poll("owner", "phone")[0]["id"] == effect["id"]
    assert hub.devices("owner")[0]["mode"] == "foreground"


def test_background_api_requires_credential_and_preserves_approval_jobs(project_temp_dir):
    auth = AuthStore(project_temp_dir)
    app = FastAPI()
    app.add_middleware(SessionAuthMiddleware, auth_store=auth)
    register_device_routes(app, project_temp_dir)
    hub = AgentHub(project_temp_dir)
    credential = hub.pair("owner", "phone", ["ping", "send_sms"], "android")
    hub.enqueue("owner", "phone", "send_sms", "test")
    with TestClient(app) as client:
        assert client.post("/api/agents/background").status_code == 401
        reply = client.post("/api/agents/background", headers={"Authorization": "Bearer " + credential["token"]})
        assert reply.status_code == 200 and reply.json() == {"jobs": [], "waiting_for_approval": 1}
        hub.revoke("owner", "phone")
        assert client.post("/api/agents/background", headers={"Authorization": "Bearer " + credential["token"]}).status_code == 401


def test_explicit_device_type_is_saved_and_normalizes_old_ui_labels(project_temp_dir):
    hub = AgentHub(project_temp_dir)
    hub.pair("owner", "TV", ["ping"], "tv")
    hub.pair("owner", "Laptop", ["ping"], "laptop")
    types = {d["name"]: d["device_type"] for d in hub.devices("owner")}
    assert types == {"TV": "tv", "Laptop": "pc"}
