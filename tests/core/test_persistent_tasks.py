import asyncio
import sqlite3
import time
from contextlib import closing

import pytest
from atulya.tasks import TaskStore, run_one
from atulya.tasks import register_task_routes
from atulya.auth import AuthStore, SESSION_COOKIE
from atulya.server import SessionAuthMiddleware
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_task_resumes_after_saved_checkpoint_and_does_not_repeat_completed_check(project_temp_dir):
    store = TaskStore(project_temp_dir)
    identifier = store.create("admin", ["server_health", "devices"])
    job = store.claim()
    store.save_checkpoint(job, [{"check": "server_health", "status": "checked"}])
    with closing(sqlite3.connect(store.path)) as db, db:
        db.execute("UPDATE tasks SET updated=?", (time.time() - 200,))
    calls = []
    async def executor(check, owner, data_dir):
        calls.append(check)
        return {"check": check, "status": "checked"}
    assert asyncio.run(run_one(TaskStore(project_temp_dir), executor))
    [result] = store.list("admin")
    assert result["id"] == identifier and result["status"] == "completed"
    assert result["checkpoint"] == 2 and calls == ["devices"]
    assert store.list("other") == []


def test_cancellation_is_scoped_and_cannot_be_overwritten_by_a_late_result(project_temp_dir):
    store = TaskStore(project_temp_dir)
    identifier = store.create("person", ["devices", "google_connection"])
    assert not store.cancel("other", identifier)
    calls = []
    async def executor(check, owner, data_dir):
        calls.append(check)
        store.cancel(owner, identifier)
        return {"check": check, "status": "checked"}
    asyncio.run(run_one(store, executor))
    [result] = store.list("person")
    assert result["status"] == "cancelled" and result["checkpoint"] == 0
    assert calls == ["devices"]


def test_only_supported_readonly_plans_are_accepted_and_backlog_is_bounded(project_temp_dir):
    store = TaskStore(project_temp_dir)
    for checks in [[], ["devices", "devices"], ["shell"], ["restart"], ["server_health"]]:
        with pytest.raises(ValueError):
            store.create("person", checks)
    for _ in range(3):
        store.create("person", ["devices"])
    with pytest.raises(ValueError, match="already pending"):
        store.create("person", ["devices"])


def test_failed_check_is_visible_and_does_not_claim_success(project_temp_dir):
    store = TaskStore(project_temp_dir)
    store.create("person", ["devices"])
    async def executor(*args):
        raise ConnectionError("network detail must not leak")
    asyncio.run(run_one(store, executor))
    [result] = store.list("person")
    assert result["status"] == "completed"
    assert result["results"] == [{"check": "devices", "status": "failed", "error": "ConnectionError"}]


def test_http_task_worker_executes_and_keeps_results_private(project_temp_dir):
    auth = AuthStore(project_temp_dir)
    auth.ensure_user("admin", "Owner", "admin")
    auth.ensure_user("other", "Other")
    app = FastAPI()
    app.add_middleware(SessionAuthMiddleware, auth_store=auth)
    register_task_routes(app, project_temp_dir)
    with TestClient(app) as client:
        assert client.get("/api/tasks").status_code == 401
        client.cookies.set(SESSION_COOKIE, auth.create_session("admin"))
        assert client.post("/api/tasks", content="not json").status_code == 422
        response = client.post("/api/tasks", json={"checks": ["devices"]})
        assert response.status_code == 202
        identifier = response.json()["id"]
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            [task] = client.get("/api/tasks").json()["tasks"]
            if task["status"] == "completed":
                break
            time.sleep(.05)
        assert task["status"] == "completed" and task["results"][0]["check"] == "devices"
        client.cookies.set(SESSION_COOKIE, auth.create_session("other"))
        assert client.get("/api/tasks").json()["tasks"] == []
        assert not client.delete("/api/tasks/" + identifier).json()["cancelled"]
