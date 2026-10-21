from atulya import readiness
from atulya.maintenance import Maintenance
from tools.plugins.system.agents import AgentHub
import pytest


def test_readiness_is_scoped_and_reports_connection_blockers(project_temp_dir, monkeypatch):
    monkeypatch.setattr(readiness, "connection_status", lambda user, directory: {"configured": True, "connected": False})
    hub = AgentHub(project_temp_dir)
    hub.pair("alice", "Alice-PC", ["ping"])
    report = readiness.runtime_readiness(project_temp_dir, "alice")
    assert any("offline" in f["message"] for f in report["findings"])
    hub.poll("alice", "Alice-PC")
    report = readiness.runtime_readiness(project_temp_dir, "alice")
    assert not any("offline" in f["message"] for f in report["findings"])
    assert readiness.runtime_readiness(project_temp_dir, "bob")["devices"] == []
    assert all(f["next_step"] for f in report["findings"])


def test_backend_repair_checks_syntax_and_preserves_rollback(project_temp_dir):
    root = project_temp_dir / "root"
    source = root / "tools/plugins/brain/engine.py"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"value = 1\r\n")
    manager = Maintenance(root, project_temp_dir / "data", project_temp_dir / "models")
    with pytest.raises(ValueError, match="Python syntax"):
        manager.propose("tools/plugins/brain/engine.py", "def broken(", "Invalid")
    proposal = manager.propose("tools/plugins/brain/engine.py", "value = 2\n", "Fix value")
    assert "regression tests" in proposal["check"]
    manager.apply(proposal["id"])
    assert source.read_bytes() == b"value = 2\n"
    manager.apply(proposal["id"], rollback=True)
    assert source.read_bytes() == b"value = 1\r\n"
    with pytest.raises(ValueError, match="protected"):
        manager.read("atulya/auth.py")
