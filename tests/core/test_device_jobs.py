import time
import sqlite3
from contextlib import closing

import pytest

from tools.plugins.system.agents import AgentHub
from tools.device_companion import execute


def test_pairing_scopes_devices_jobs_and_revocation(project_temp_dir):
    hub = AgentHub(project_temp_dir)
    paired = hub.pair("alice", "Laptop", ["ping"])
    assert hub.authenticate(paired["token"]) == {"owner": "alice", "name": "Laptop", "abilities": ["ping"]}
    assert hub.devices("bob") == []
    with pytest.raises(ValueError):
        hub.enqueue("bob", "Laptop", "ping")
    with pytest.raises(ValueError):
        hub.enqueue("alice", "Laptop", "open_url", "https://example.com")
    job = hub.enqueue("alice", "Laptop", "ping")
    assert job["status"] == "queued"
    assert not hub.complete("alice", "Laptop", job["id"], "premature")
    assert AgentHub(project_temp_dir).poll("alice", "Laptop")[0]["id"] == job["id"]
    assert hub.poll("alice", "Laptop") == []
    assert not hub.complete("bob", "Laptop", job["id"], "wrong owner")
    assert hub.complete("alice", "Laptop", job["id"], "pong")
    assert hub.complete("alice", "Laptop", job["id"], "pong")
    assert not hub.complete("alice", "Laptop", job["id"], "different output")
    assert hub.jobs("alice")[0]["status"] == "executed"
    hub.enqueue("alice", "Laptop", "ping")
    assert hub.revoke("alice", "Laptop")
    assert hub.authenticate(paired["token"]) is None
    assert hub.jobs("alice")[0]["status"] == "cancelled"


def test_lost_acknowledgement_is_unconfirmed_never_replayed(project_temp_dir):
    hub = AgentHub(project_temp_dir)
    hub.pair("alice", "Laptop", ["ping"])
    job = hub.enqueue("alice", "Laptop", "ping")
    hub.poll("alice", "Laptop")
    with closing(sqlite3.connect(hub.path)) as db, db:
        db.execute("UPDATE jobs SET updated=? WHERE id=?", (time.time()-150, job["id"]))
    assert hub.poll("alice", "Laptop") == []
    assert hub.jobs("alice")[0]["status"] == "unconfirmed"


def test_laptop_files_are_limited_to_granted_directory(project_temp_dir):
    granted = project_temp_dir / "allowed"
    granted.mkdir()
    (granted / "hello.txt").write_text("private contents")
    assert execute("list_files", ".", granted) == "hello.txt"
    with pytest.raises(ValueError):
        execute("list_files", "..", granted)
    with pytest.raises(ValueError):
        execute("list_files", ".")
    with pytest.raises(ValueError):
        execute("open_url", "javascript:alert(1)")
