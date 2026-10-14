from fastapi import FastAPI
from fastapi.testclient import TestClient

from atulya.auth import AuthStore, SESSION_COOKIE
from atulya.server import SessionAuthMiddleware
from atulya.device_api import register_device_routes
from atulya.automation_api import register_automation_routes
from atulya.music import register_music_routes
from tools.plugins.productivity.reminders import ReminderStore
from tools.plugins.productivity.web_reminders import WebReminderStore
from tools.plugins.productivity.routines import RoutineStore


def test_new_endpoints_require_owner_and_device_credentials(project_temp_dir):
    auth=AuthStore(project_temp_dir)
    auth.ensure_user("admin","Owner","admin")
    auth.ensure_user("alice","Alice")
    app=FastAPI()
    app.add_middleware(SessionAuthMiddleware,auth_store=auth)
    register_device_routes(app,project_temp_dir)
    register_music_routes(app,project_temp_dir)
    register_automation_routes(app,auth,project_temp_dir,[],ReminderStore(project_temp_dir),WebReminderStore(project_temp_dir))
    routine=RoutineStore(project_temp_dir).add("Read","07:00",action="message",message="Read")
    with TestClient(app) as client:
        assert client.get("/api/devices").status_code==401
        client.cookies.set(SESSION_COOKIE,auth.create_session("alice"))
        assert client.get("/api/automations").status_code==403
        paired=client.post("/api/devices/pair",json={"name":"Laptop","abilities":["ping"]}).json()
        assert "token" in paired
        assert client.post("/api/agents/poll").status_code==401
        assert client.post("/api/agents/poll",headers={"Authorization":"Bearer "+paired["token"]}).status_code==200
        assert client.get("/api/devices").json()["devices"][0]["name"]=="Laptop"
        client.cookies.set(SESSION_COOKIE,auth.create_session("admin"))
        assert client.get("/api/devices").json()["devices"]==[]
        assert client.put("/api/automations/"+routine["id"],json={"enabled":False}).status_code==200
        assert not RoutineStore(project_temp_dir).still_enabled(routine["id"])
        assert client.post("/api/reminders/cancel-all").status_code==200
