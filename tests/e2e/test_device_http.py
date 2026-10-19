"""Real HTTP server and separate companion process on this PC, without production data."""

import os
import socket
import subprocess
import sys
import threading
import time

import httpx
import uvicorn
from fastapi import FastAPI

from atulya.auth import AuthStore, SESSION_COOKIE
from atulya.server import SessionAuthMiddleware
from atulya.device_api import register_device_routes


def test_real_http_pc_pair_ping_receipt_and_revoke(project_temp_dir, record_property):
    auth = AuthStore(project_temp_dir)
    auth.ensure_user("admin", "Owner", "admin")
    auth.ensure_user("other", "Other")
    app = FastAPI()
    app.add_middleware(SessionAuthMiddleware, auth_store=auth)
    register_device_routes(app, project_temp_dir)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="off"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            assert thread.is_alive() and time.monotonic() < deadline, "Test HTTP server failed to start"
            time.sleep(0.01)
        with httpx.Client(base_url=origin, trust_env=False) as client:
            assert client.get("/api/devices").status_code == 401
            client.cookies.set(SESSION_COOKIE, auth.create_session("admin"))
            pair = client.post("/api/devices/pair", json={"name": "This-PC", "abilities": ["ping"]})
            assert pair.status_code == 201
            token = pair.json()["token"]
            ping_started = time.perf_counter()
            job = client.post("/api/devices/This-PC/test").json()["job"]
            env = dict(os.environ, ATULYA_TEST_ORIGIN=origin, ATULYA_AGENT_TOKEN=token)
            code = """
import os, httpx
from tools.device_companion import poll_once
with httpx.Client(base_url=os.environ['ATULYA_TEST_ORIGIN'], trust_env=False,
                 headers={'Authorization': 'Bearer ' + os.environ['ATULYA_AGENT_TOKEN']}) as client:
    client.post('/api/agents/register').raise_for_status()
    assert poll_once(client)[0]['success']
"""
            result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=20)
            assert result.returncode == 0, result.stderr
            snapshot = client.get("/api/devices").json()
            receipt = next(item for item in snapshot["jobs"] if item["id"] == job["id"])
            assert receipt["status"] == "executed"
            assert "companion active" in receipt["output"]
            record_property("pc_ping_receipt_ms", round((time.perf_counter() - ping_started) * 1000, 1))
            assert snapshot["devices"][0]["status"] == "online"
            client.cookies.set(SESSION_COOKIE, auth.create_session("other"))
            assert client.post("/api/devices/This-PC/test").status_code == 422
            assert client.get("/api/devices").json()["jobs"] == []
            client.cookies.set(SESSION_COOKIE, auth.create_session("admin"))
            assert client.delete("/api/devices/This-PC").json()["revoked"] == 1
            assert client.post("/api/agents/poll", headers={"Authorization": "Bearer " + token}).status_code == 401
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
