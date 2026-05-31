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
