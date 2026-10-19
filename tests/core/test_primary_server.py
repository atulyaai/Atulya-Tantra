import asyncio

from tools.plugins import toolkit
from tools.plugins.registry import PluginContext


def context(user="admin"):
    return PluginContext("web", None, None, user_id=user)


def test_primary_server_needs_no_ssh_configuration(monkeypatch):
    monkeypatch.delenv("ATULYA_SERVERS", raising=False)
    monkeypatch.setattr(toolkit, "STATUS_PROVIDER", lambda: {"service": "online", "cpu": "2%"})
    result = asyncio.run(toolkit._server_status({}, context()))
    assert "Primary server" in result and "online" in result and "2%" in result
    assert "do not require SSH" in result
    assert "No servers are configured" not in result


def test_primary_diagnostics_work_without_a_status_callback(monkeypatch):
    monkeypatch.delenv("ATULYA_SERVERS", raising=False)
    monkeypatch.setattr(toolkit, "STATUS_PROVIDER", None)
    result = asyncio.run(toolkit._server_status({}, context()))
    assert "Primary server" in result and "Atulya process running" in result
    assert "process uptime" in result and "disk" in result


def test_additional_servers_do_not_replace_primary_health(monkeypatch):
    monkeypatch.setenv("ATULYA_SERVERS", "extra=ubuntu@example.invalid=/test/key")
    monkeypatch.setattr(toolkit, "STATUS_PROVIDER", lambda: {"service": "online"})
    monkeypatch.setattr(toolkit, "_ssh_status", lambda target, key: "unreachable")
    result = asyncio.run(toolkit._server_status({}, context()))
    assert "Primary server" in result and "online" in result
    assert "Additional SSH server extra: unreachable" in result


def test_non_owner_cannot_read_primary_status_or_logs(monkeypatch):
    def forbidden():
        raise AssertionError("Must not read system state")
    monkeypatch.setattr(toolkit, "STATUS_PROVIDER", forbidden)
    assert "Only the owner" in asyncio.run(toolkit._server_status({}, context("other")))
    assert "Only the owner" in asyncio.run(toolkit._server_logs({}, context("other")))


def test_logs_follow_configured_data_directory(project_temp_dir, monkeypatch):
    monkeypatch.setenv("ATULYA_DATA_DIR", str(project_temp_dir))
    monkeypatch.delenv("ATULYA_LOG_DIR", raising=False)
    logs = project_temp_dir / "logs"
    logs.mkdir()
    (logs / "server.log").write_text("connection test passed\n", encoding="utf-8")
    result = asyncio.run(toolkit._server_logs({}, context()))
    assert "connection test passed" in result
    assert "untrusted log content" in result
