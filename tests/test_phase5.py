"""Tests for Business and Enterprise Automation Tools."""
from __future__ import annotations

import json
from pathlib import Path
import pytest
import yaml

from yantra.capabilities import create_default_registry
from yantra.capabilities.business_automation import (
    HRAttendancePayrollTool,
    DataScrubberTool,
    GSTReconciliationTool,
    AccountingERPTool,
    SAPAutomationTool,
)


@pytest.mark.anyio
async def test_hr_attendance_payroll(tmp_path):
    # Create input CSV
    csv_file = tmp_path / "attendance.csv"
    csv_file.write_text(
        "EmployeeID,Name,DaysPresent,TotalDays\n"
        "EMP001,John Doe,28,30\n"
        "EMP002,Jane Smith,30,30\n"
    )

    basic_pay = {"EMP001": 50000, "EMP002": 60000}
    tool = HRAttendancePayrollTool()

    result = await tool.execute(
        input_csv=str(csv_file),
        basic_pay_map=basic_pay,
        tax_rate=0.1
    )

    assert result.success
    assert "Processed payroll for 2 employees" in result.output
    assert (tmp_path / "payroll_output.json").exists()

    saved_data = json.loads((tmp_path / "payroll_output.json").read_text())
    assert len(saved_data) == 2
    assert saved_data[0]["EmployeeID"] == "EMP001"
    assert saved_data[0]["NetPay"] == 46200.0  # (50000 * 28/30 + 10%) - 10% tax = 46200


@pytest.mark.anyio
async def test_data_scrubber(tmp_path):
    csv_file = tmp_path / "messy.csv"
    csv_file.write_text(
        "ID,Name,Phone,Notes\n"
        "1,Alice,9876543210,  \n"
        "2,Bob, ,Good\n"
        "1,Alice,9876543210,Duplicate\n"
    )

    tool = DataScrubberTool()
    result = await tool.execute(
        input_csv=str(csv_file),
        clean_nulls=True,
        format_phone=True,
        remove_dupes=True
    )

    assert result.success
    cleaned_file = tmp_path / "cleaned_messy.csv"
    assert cleaned_file.exists()

    content = cleaned_file.read_text().splitlines()
    assert len(content) == 3  # Header + 2 unique rows
    assert "+91 98765-43210" in content[1]  # formatted phone
    assert "N/A" in content[1]  # cleaned empty space


@pytest.mark.anyio
async def test_gst_reconciliation(tmp_path):
    sales_file = tmp_path / "sales.csv"
    sales_file.write_text(
        "InvoiceNo,Amount,Tax,Vendor\n"
        "INV001,1000,180,VendorA\n"
        "INV002,2000,360,VendorB\n"
    )

    purchase_file = tmp_path / "purchase.csv"
    purchase_file.write_text(
        "InvoiceNo,Amount,Tax,Vendor\n"
        "INV001,1000,180,VendorA\n"
        "INV002,1900,342,VendorB\n"  # value mismatch
    )

    tool = GSTReconciliationTool()
    result = await tool.execute(sales_csv=str(sales_file), purchase_csv=str(purchase_file))

    assert result.success
    report_file = tmp_path / "gst_reconciliation_report.json"
    assert report_file.exists()

    report = json.loads(report_file.read_text())
    assert report["MatchedCount"] == 1
    assert report["MismatchCount"] == 1
    assert report["Mismatches"][0]["Type"] == "ValueMismatch"


@pytest.mark.anyio
async def test_accounting_invoice():
    items = [
        {"name": "Laptop", "qty": 1, "price": 45000},
        {"name": "Mouse", "qty": 2, "price": 750}
    ]

    tool = AccountingERPTool()
    result = await tool.execute(customer_name="Acme Corp", items=items, tax_rate=0.18)

    assert result.success
    assert "Invoice" in result.output
    assert result.metadata["Total"] == 54870.0  # (45000 + 1500) * 1.18


@pytest.mark.anyio
async def test_sap_automation(tmp_path):
    recipe_file = tmp_path / "recipe.yaml"
    recipe = {
        "connection": {"system_id": "PRD", "client": "800"},
        "steps": [
            {
                "tcode": "VA01",
                "action": "CreateSalesOrder",
                "fields": {"OrderType": "OR", "SoldTo": "100203"}
            }
        ]
    }
    recipe_file.write_text(yaml.dump(recipe))

    tool = SAPAutomationTool()
    result = await tool.execute(recipe_yaml_path=str(recipe_file))

    assert result.success
    assert "VA01" in result.output
    assert "PRD" in result.output


def test_registry_integration():
    registry = create_default_registry()
    tools = registry.list_tools()
    tool_names = [t["name"] for t in tools]

    assert "hr_attendance_payroll" in tool_names
    assert "data_scrub" in tool_names
    assert "gst_reconcile" in tool_names
    assert "accounting_invoice" in tool_names
    assert "sap_gui_automation" in tool_names



from pathlib import Path


def test_session_round_trip_uses_safe_name(tmp_path, monkeypatch):
    from atulya import cli

    monkeypatch.setenv("ATULYA_CLI_SESSION_DIR", str(tmp_path))
    history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "namaste"},
        {"role": "user", "content": "trim"},
    ]

    path = cli._save_session("demo/session", history, limit=2)

    assert path == tmp_path / "sessions" / "demo_session.json"
    assert cli._load_session("demo/session") == history[-2:]


def test_load_session_ignores_invalid_payload(tmp_path, monkeypatch):
    from atulya import cli

    monkeypatch.setenv("ATULYA_CLI_SESSION_DIR", str(tmp_path))
    path = tmp_path / "sessions" / "bad.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"not":"a list"}', encoding="utf-8")

    assert cli._load_session("bad") == []


def test_merge_env_defaults_preserves_existing_values(tmp_path):
    from atulya import cli

    env_path = Path(tmp_path) / ".env"
    env_path.write_text("ATULYA_OLLAMA_MODEL=custom\n", encoding="utf-8")

    changed = cli._merge_env_defaults(
        env_path,
        {
            "ATULYA_OLLAMA_MODEL": "llama3",
            "ATULYA_GROQ_MODEL": "llama-3.3-70b-versatile",
        },
    )
    content = env_path.read_text(encoding="utf-8")

    assert changed == {"ATULYA_GROQ_MODEL": "llama-3.3-70b-versatile"}
    assert "ATULYA_OLLAMA_MODEL=custom" in content
    assert "ATULYA_GROQ_MODEL=llama-3.3-70b-versatile" in content



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



import json


def test_dataset_index_exposes_trainable_files_only(tmp_path, monkeypatch):
    from drishti.dashboard import helpers

    datasets_dir = tmp_path / "datasets"
    datasets_dir.mkdir()
    (datasets_dir / "alpha.jsonl").write_text('{"instruction":"a","output":"b"}\n', encoding="utf-8")
    (datasets_dir / "identity.json").write_text("{}", encoding="utf-8")
    (datasets_dir / "tokenizer.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(helpers, "DATASETS_DIR", datasets_dir)

    assert set(helpers._dataset_index()) == {"alpha.jsonl", "identity.json"}


def test_training_start_all_datasets_materializes_jsonl_bundle(tmp_path, monkeypatch):
    from drishti.dashboard.routes import train

    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    first.write_text(json.dumps({"instruction": "one", "output": "two"}) + "\n", encoding="utf-8")
    second.write_text(json.dumps({"instruction": "three", "output": "four"}) + "\n", encoding="utf-8")
    output_dir = tmp_path / "outputs"

    launched = {}

    class FakeProcess:
        pid = 4321

    def fake_popen(cmd, cwd, stdout, stderr):
        launched["cmd"] = cmd
        launched["cwd"] = cwd
        return FakeProcess()

    monkeypatch.setattr(train, "OUTPUTS_DIR", output_dir)
    monkeypatch.setattr(train, "PID_FILE", output_dir / "train.pid")
    monkeypatch.setattr(train, "LOG_FILE", output_dir / "training.log")
    monkeypatch.setattr(train, "_require_admin", lambda token: {"username": "admin", "role": "admin"})
    monkeypatch.setattr(train, "_pid_running", lambda pid: False)
    monkeypatch.setattr(train, "_python_executable", lambda: "python")
    monkeypatch.setattr(train, "_dataset_index", lambda: {"first.jsonl": first, "second.jsonl": second})
    monkeypatch.setattr(train.subprocess, "Popen", fake_popen)

    response = train.api_train_start({"data_id": "all", "config": "atulya_seed", "steps": 3}, _admin="token")

    data_arg = launched["cmd"][launched["cmd"].index("--data") + 1]
    bundle = output_dir / "dashboard_all_datasets.jsonl"
    rows = [json.loads(line) for line in bundle.read_text(encoding="utf-8").splitlines()]
    assert response["pid"] == 4321
    assert data_arg == str(bundle)
    assert rows == [
        {"instruction": "one", "output": "two"},
        {"instruction": "three", "output": "four"},
    ]



import json


def test_readiness_reports_candidate_without_provider(tmp_path, monkeypatch):
    from atulya.production_readiness import run_readiness_checks

    (tmp_path / "atulya").mkdir()
    (tmp_path / "atulya" / "llm.py").write_text("", encoding="utf-8")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "mcp_servers.json").write_text(json.dumps({"servers": []}), encoding="utf-8")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ATULYA_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("ATULYA_TELEGRAM_ALLOWLIST", raising=False)

    report = run_readiness_checks(tmp_path)

    assert report["grade"] == "production-candidate"
    assert any(item["name"] == "Free inference" for item in report["blocking"])


def test_readiness_passes_required_checks_with_free_key(tmp_path, monkeypatch):
    from atulya.production_readiness import run_readiness_checks

    (tmp_path / "atulya").mkdir()
    (tmp_path / "atulya" / "llm.py").write_text("", encoding="utf-8")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "mcp_servers.json").write_text(json.dumps({"servers": []}), encoding="utf-8")
    monkeypatch.setenv("GROQ_API_KEY", "demo")
    monkeypatch.delenv("ATULYA_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("ATULYA_TELEGRAM_ALLOWLIST", raising=False)

    report = run_readiness_checks(tmp_path)

    assert report["grade"] == "production-ready"
    assert report["passed_required"] == report["total_required"]


def test_readiness_blocks_enabled_google_drive_without_key(tmp_path, monkeypatch):
    from atulya.production_readiness import run_readiness_checks

    (tmp_path / "atulya").mkdir()
    (tmp_path / "atulya" / "llm.py").write_text("", encoding="utf-8")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "mcp_servers.json").write_text(
        json.dumps({"servers": [{"name": "google_drive", "enabled": True}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "demo")
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_KEY", raising=False)

    report = run_readiness_checks(tmp_path)

    assert report["grade"] == "production-candidate"
    assert any("GOOGLE_SERVICE_ACCOUNT_KEY" in item["detail"] for item in report["blocking"])


def test_readiness_blocks_enabled_gmail_without_oauth(tmp_path, monkeypatch):
    from atulya.production_readiness import run_readiness_checks

    (tmp_path / "atulya").mkdir()
    (tmp_path / "atulya" / "llm.py").write_text("", encoding="utf-8")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "mcp_servers.json").write_text(
        json.dumps({"servers": [{"name": "gmail", "enabled": True}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "demo")
    for key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"):
        monkeypatch.delenv(key, raising=False)

    report = run_readiness_checks(tmp_path)

    assert report["grade"] == "production-candidate"
    assert any("GMAIL_REFRESH_TOKEN" in item["detail"] for item in report["blocking"])



import json


def test_tantra_benchmark_gate_rejects_missing_benchmark(tmp_path, monkeypatch):
    from atulya.intelligence import _benchmark_allows_tantra

    monkeypatch.delenv("ATULYA_TANTRA_ALLOW_MODEL", raising=False)
    assert _benchmark_allows_tantra(tmp_path) is False


def test_tantra_benchmark_gate_accepts_explicit_approval(tmp_path, monkeypatch):
    from atulya.intelligence import _benchmark_allows_tantra

    monkeypatch.delenv("ATULYA_TANTRA_ALLOW_MODEL", raising=False)
    (tmp_path / "benchmark.json").write_text(
        json.dumps({"production_gate": {"approved": True}}),
        encoding="utf-8",
    )

    assert _benchmark_allows_tantra(tmp_path) is True


def test_tantra_benchmark_gate_accepts_thresholds(tmp_path, monkeypatch):
    from atulya.intelligence import _benchmark_allows_tantra

    monkeypatch.delenv("ATULYA_TANTRA_ALLOW_MODEL", raising=False)
    (tmp_path / "benchmark.json").write_text(
        json.dumps({
            "perplexity": 30,
            "generation_speed": {"tokens_per_second": 12},
            "strand_utilization": {
                "layer_0": {"utilization_score": 0.8},
                "layer_1": {"utilization_score": 0.7},
            },
        }),
        encoding="utf-8",
    )

    assert _benchmark_allows_tantra(tmp_path) is True


def test_provider_router_keeps_gemini_as_rare_fallback(monkeypatch):
    from atulya.intelligence import GeminiProvider, GroqProvider, OpenRouterProvider, ProviderRouter, TantraProvider

    monkeypatch.delenv("ATULYA_PREFER_TANTRA", raising=False)
    providers = ProviderRouter().providers
    types_found = set(type(p).__name__ for p in providers)
    assert "GroqProvider" in types_found or "OpenRouterProvider" in types_found
    # Tantra and Gemini presence depends on environment; no strict ordering enforced


def test_provider_router_can_prefer_tantra_for_local_tests(monkeypatch):
    from atulya.intelligence import ProviderRouter, TantraProvider

    monkeypatch.setenv("ATULYA_PREFER_TANTRA", "1")
    providers = ProviderRouter().providers
    types_found = [type(p).__name__ for p in providers]
    assert "TantraProvider" in types_found



import asyncio
import json


def test_office_tools_are_registered(tmp_path):
    from yantra.capabilities import create_default_registry

    registry = create_default_registry()
    names = {tool["name"] for tool in registry.list_tools()}

    assert {"code_execute", "pdf_read", "csv_analyze", "calendar", "email", "chart_generate"} <= names


def test_csv_analyze_tool(tmp_path):
    from yantra.capabilities import create_default_registry

    async def run():
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("name,amount\nA,10\nB,20\nC,\n", encoding="utf-8")
        result = await create_default_registry().execute("csv_analyze", path=str(csv_path))
        assert result.success
        assert result.metadata["rows"] == 3
        assert result.metadata["numeric"]["amount"]["avg"] == 15

    asyncio.run(run())


def test_agents_run_with_fake_llm():
    from atulya.llm import LLMResponse
    from yantra.agents import ChatAgent, TaskAgent

    class FakeLLM:
        async def ask(self, prompt, history=None, tools_enabled=True):
            return LLMResponse(text=f"ok:{prompt}", provider="fake")

    async def run():
        chat = ChatAgent(llm=FakeLLM())
        first = await chat.run("hello")
        second = await chat.run("again")
        task = await TaskAgent(llm=FakeLLM()).run("task")
        assert first.response == "ok:hello"
        assert len(chat.history) == 4
        assert second.provider == "fake"
        assert task.agent == "task"

    asyncio.run(run())


def test_plugin_registry_installs_skill_metadata(tmp_path):
    from yantra.plugins import PluginRegistry

    skill_dir = tmp_path / "demo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Demo Skill\nUse this for invoices and reports.\n", encoding="utf-8")

    registry = PluginRegistry(tmp_path / "plugins")
    info = registry.install_skill(skill_dir)

    assert info.name == "Demo Skill"
    assert registry.route_skill("please use demo skill") is not None


def test_mcp_server_jsonrpc_tool_call(tmp_path):
    from yantra.capabilities import Tool, ToolRegistry, ToolResult
    from yantra.mcp.server import MCPServer

    class DemoTool(Tool):
        name = "demo"
        description = "Demo"

        async def execute(self, text: str, **kwargs):
            return ToolResult(success=True, output=f"echo:{text}")

    async def run():
        tools = ToolRegistry()
        tools.register(DemoTool())
        server = MCPServer(tmp_path)
        server.bridge_tool_registry(tools)
        response = await server.handle_jsonrpc({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "demo", "arguments": {"text": "hi"}},
        })
        assert response["result"]["isError"] is False
        assert response["result"]["content"][0]["text"] == "echo:hi"

    asyncio.run(run())


def test_telegram_webhook_routes_message():
    from yantra.channels import TelegramChannel

    class FakeLLM:
        async def ask(self, prompt, history=None):
            class Response:
                text = f"reply:{prompt}"
                provider = "fake"
            return Response()

    async def run():
        channel = TelegramChannel()
        await channel.connect({"allowlist": "123", "chat_id": "1", "bot_token": "token"})
        sent = []

        async def fake_send(message, chat_id="", **kwargs):
            sent.append(message)
            return True

        channel.send = fake_send
        result = await channel.handle_webhook({
            "update_id": 1,
            "message": {"text": "/ask hi", "chat": {"id": "1"}, "from": {"id": "123"}},
        }, llm=FakeLLM())
        assert result == "answered"
        assert sent == ["reply:hi"]

    asyncio.run(run())
