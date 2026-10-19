import asyncio
import sqlite3
import time
from contextlib import closing

import pytest
from atulya.operations import Operations, deliver_alerts
from tools.operations_worker import poll_once, execute
from tools.plugins.registry import PluginContext
from tools.plugins.toolkit import Toolbox, TOOLS, ActionQueue


def test_restart_needs_owner_allowlist_worker_and_actual_approval(project_temp_dir, monkeypatch):
    monkeypatch.setenv("ATULYA_DATA_DIR", str(project_temp_dir))
    ops = Operations(project_temp_dir)
    with pytest.raises(ValueError, match="not connected"):
        ops.enqueue_restart("admin", "atulya")
    ops.heartbeat()
    with pytest.raises(ValueError, match="owner"):
        ops.enqueue_restart("other", "atulya")
    with pytest.raises(ValueError, match="allowlisted"):
        ops.enqueue_restart("admin", "sshd; touch /tmp/invalid")
    queue = ActionQueue(project_temp_dir)
    view = queue.view()
    box = Toolbox(TOOLS, PluginContext("web", None, None, actions=view))
    answer = asyncio.run(box.call("restart_service", {"service": "atulya"}))
    assert "NOT run" in answer and ops.status()["jobs"] == []
    [approval] = view.drain_new()
    answer = asyncio.run(box.run_approved(approval))
    assert "Queued approved restart" in answer
    [job] = ops.status()["jobs"]
    assert job["status"] == "queued"
    called = []
    result = poll_once(ops, executor=lambda j: (called.append(j["target"]) or True, "healthy"))
    assert result["success"] and called == ["atulya.service"]
    assert ops.status()["jobs"][0]["status"] == "executed"


def test_crashed_operation_is_not_replayed_and_pending_requests_expire(project_temp_dir):
    ops = Operations(project_temp_dir)
    ops.heartbeat()
    identifier = ops.enqueue_restart("admin", "atulya")
    assert ops.claim()["id"] == identifier
    with closing(sqlite3.connect(ops.path)) as db, db:
        db.execute("UPDATE jobs SET updated=?", (time.time() - 180,))
    assert ops.status()["jobs"][0]["status"] == "unconfirmed"
    assert ops.claim() is None
    with closing(sqlite3.connect(ops.path)) as db, db:
        db.execute("UPDATE jobs SET status='queued',created=?", (time.time() - 600,))
    assert ops.claim() is None
    assert ops.status()["jobs"][0]["status"] == "expired"


def test_worker_rejects_unknown_commands_without_a_subprocess(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No command may execute")
    monkeypatch.setattr("tools.operations_worker.subprocess.run", forbidden)
    assert execute({"kind": "shell", "target": "whoami", "owner": "admin"})[0] is False
    assert execute({"kind": "restart", "target": "ssh.service", "owner": "admin"})[0] is False


def test_monitor_deduplicates_and_records_provider_acceptance(project_temp_dir):
    ops = Operations(project_temp_dir)
    ops.observe("disk", False, "normal")
    assert not ops.pending_alerts()
    for _ in range(4):
        ops.observe("disk", True, "critical disk")
    assert len(ops.status()["alerts"]) == 1
    sent = []
    async def notify(message):
        sent.append(message)
        return 1
    asyncio.run(deliver_alerts(ops, notify))
    asyncio.run(deliver_alerts(ops, notify))
    assert sent == ["critical disk"]
    assert ops.status()["alerts"][0]["status"] == "provider_accepted"
    ops.observe("disk", False, "recovered")
    asyncio.run(deliver_alerts(ops, notify))
    assert sent == ["critical disk", "recovered"]
    ops.set_alerts(False)
    ops.observe("disk", True, "muted event")
    ops.set_alerts(True)
    asyncio.run(deliver_alerts(ops, notify))
    assert len(sent) == 2
