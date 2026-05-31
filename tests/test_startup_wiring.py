import asyncio
import json


def test_automation_runner_executes_due_job(tmp_path):
    from drishti.dashboard.automation_runner import AutomationRunner

    class FakeLLM:
        async def ask(self, command, tools_enabled=True):
            class Response:
                text = f"done:{command}"
                provider = "fake"
            return Response()

    async def run():
        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text(json.dumps([
            {"id": "1", "name": "demo", "schedule": "60", "command": "say hi", "enabled": True, "next_run": 1}
        ]))
        runner = AutomationRunner(jobs_file, FakeLLM())
        await runner.tick()
        jobs = json.loads(jobs_file.read_text())
        assert jobs[0]["run_count"] == 1
        assert jobs[0]["last_result"] == "done:say hi"
        assert jobs[0]["last_provider"] == "fake"

    asyncio.run(run())


def test_mcp_config_ships_disabled_by_default():
    data = json.loads(open("config/mcp_servers.json", encoding="utf-8").read())
    assert len(data["servers"]) >= 8
    assert all("enabled" in server for server in data["servers"])
    assert all("timeout" in server for server in data["servers"])
    assert not any(server["enabled"] for server in data["servers"])
    by_name = {server["name"]: server for server in data["servers"]}
    assert by_name["google_drive"]["env"]["MCP_MODE"] == "stdio"
    assert by_name["google_drive"]["env"]["DISABLE_CONSOLE_OUTPUT"] == "true"
    assert by_name["gmail"]["env"]["MCP_MODE"] == "stdio"


def test_mcp_http_url_is_not_double_suffixed(monkeypatch):
    from yantra.mcp.external_client import MCPClient, MCPClientConfig

    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"jsonrpc":"2.0","id":1,"result":{"tools":[]}}'

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        return FakeResponse()

    async def run():
        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        client = MCPClient(MCPClientConfig(name="demo", transport="http", url="http://127.0.0.1:4000/mcp/rpc"))
        client._http_session = True
        await client._request_http({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert captured["url"] == "http://127.0.0.1:4000/mcp/rpc"

    asyncio.run(run())


def test_automation_runner_run_job_reports_missing_command(tmp_path):
    from drishti.dashboard.automation_runner import AutomationRunner

    class FakeLLM:
        async def ask(self, command, tools_enabled=True):
            raise AssertionError("empty job should not call LLM")

    async def run():
        runner = AutomationRunner(tmp_path / "jobs.json", FakeLLM())
        job = {}
        await runner.run_job(job)
        assert job["last_error"] == "No command configured"

    asyncio.run(run())
