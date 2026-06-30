import asyncio


class FakeRouter:
    async def chat(self, prompt, system_prompt="", **kwargs):
        if "tool please" in prompt and "Tool result" not in prompt:
            return '{"tool":"todo_create","arguments":{"text":"demo"}}', "fake"
        if "write please" in prompt and "Tool result" not in prompt and "User approved tool" not in prompt:
            return '{"tool":"file_write","arguments":{"path":"demo.txt","content":"demo"}}', "fake"
        if "parallel please" in prompt and "Tool result" not in prompt:
            return '{"tools":[{"tool":"a","arguments":{"value":"1"}},{"tool":"b","arguments":{"value":"2"}}]}', "fake"
        return "Final **answer** with `code`.", "fake"


def test_llm_bridge_returns_text():
    from atulya.llm import AtulyaLLM

    async def run():
        llm = AtulyaLLM()
        llm.router = FakeRouter()
        response = await llm.ask("hello", tools_enabled=False)
        assert response.text == "Final **answer** with `code`."
        assert response.provider == "fake"

    asyncio.run(run())


def test_llm_bridge_executes_tool_loop():
    from atulya.llm import AtulyaLLM
    from yantra.capabilities import Tool, ToolRegistry, ToolResult

    class DemoTool(Tool):
        name = "todo_create"
        description = "Demo tool"

        async def execute(self, text: str, **kwargs):
            return ToolResult(success=True, output=f"created:{text}")

    async def run():
        tools = ToolRegistry()
        tools.register(DemoTool())
        llm = AtulyaLLM(tools=tools)
        llm.router = FakeRouter()
        response = await llm.ask("tool please")
        assert response.tool_steps
        assert response.tool_steps[0]["tool"] == "todo_create"
        assert response.text == "Final **answer** with `code`."

    asyncio.run(run())


def test_llm_bridge_requires_approval_for_risky_tool():
    from atulya.llm import AtulyaLLM
    from yantra.capabilities import Tool, ToolRegistry, ToolResult

    class FileWriteTool(Tool):
        name = "file_write"
        description = "Demo write"

        async def execute(self, path: str, content: str, **kwargs):
            raise AssertionError("risky tool should not run before approval")

    async def run():
        tools = ToolRegistry()
        tools.register(FileWriteTool())
        llm = AtulyaLLM(tools=tools)
        llm.router = FakeRouter()
        response = await llm.ask("write please")
        assert response.needs_approval is True
        assert response.pending_tool == {
            "tool": "file_write",
            "arguments": {"path": "demo.txt", "content": "demo"},
        }
        assert response.tool_steps == []

    asyncio.run(run())


def test_llm_bridge_executes_approved_risky_tool():
    from atulya.llm import AtulyaLLM
    from yantra.capabilities import Tool, ToolRegistry, ToolResult

    class FileWriteTool(Tool):
        name = "file_write"
        description = "Demo write"

        async def execute(self, path: str, content: str, **kwargs):
            return ToolResult(success=True, output=f"written:{path}:{content}")

    async def run():
        tools = ToolRegistry()
        tools.register(FileWriteTool())
        llm = AtulyaLLM(tools=tools)
        llm.router = FakeRouter()
        response = await llm.ask(
            "write please",
            approved_tool_call={"tool": "file_write", "arguments": {"path": "demo.txt", "content": "demo"}},
        )
        assert response.needs_approval is False
        assert response.tool_steps[0]["output"] == "written:demo.txt:demo"
        assert response.text == "Final **answer** with `code`."

    asyncio.run(run())


def test_llm_bridge_executes_parallel_safe_tools():
    from atulya.llm import AtulyaLLM
    from yantra.capabilities import Tool, ToolRegistry, ToolResult

    class DemoTool(Tool):
        def __init__(self, name):
            self.name = name
            self.description = "Demo"

        async def execute(self, value: str, **kwargs):
            return ToolResult(success=True, output=f"{self.name}:{value}")

    async def run():
        tools = ToolRegistry()
        tools.register(DemoTool("a"))
        tools.register(DemoTool("b"))
        llm = AtulyaLLM(tools=tools)
        llm.router = FakeRouter()
        response = await llm.ask("parallel please")
        assert [step["output"] for step in response.tool_steps] == ["a:1", "b:2"]
        assert response.text == "Final **answer** with `code`."

    asyncio.run(run())


def test_telegram_allowlist_blocks_unknown_user():
    from yantra.channels import ChannelMessage, TelegramChannel

    async def run():
        channel = TelegramChannel()
        await channel.connect({"allowlist": "123", "chat_id": "1", "bot_token": "token"})
        sent = []

        async def fake_send(message, chat_id="", **kwargs):
            sent.append(message)
            return True

        channel.send = fake_send
        result = await channel.handle_message(ChannelMessage("1", "telegram", "999", "/ask hi", metadata={"chat_id": "1"}))
        assert result == "denied"
        assert "Access denied" in sent[0]

    asyncio.run(run())


def test_telegram_ask_routes_to_llm():
    from yantra.channels import ChannelMessage, TelegramChannel

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
        result = await channel.handle_message(
            ChannelMessage("1", "telegram", "123", "/ask status", metadata={"chat_id": "1"}),
            llm=FakeLLM(),
        )
        assert result == "answered"
        assert sent == ["reply:status"]

    asyncio.run(run())


def test_telegram_preserves_sender_history():
    from yantra.channels import ChannelMessage, TelegramChannel

    class FakeLLM:
        seen = []

        async def ask(self, prompt, history=None):
            self.seen.append(list(history or []))

            class Response:
                text = f"reply:{prompt}"
                provider = "fake"
            return Response()

    async def run():
        channel = TelegramChannel()
        await channel.connect({"allowlist": "123", "chat_id": "1", "bot_token": "token"})
        async def fake_send(*args, **kwargs):
            return True
        channel.send = fake_send
        llm = FakeLLM()
        await channel.handle_message(ChannelMessage("1", "telegram", "123", "/ask first", metadata={"chat_id": "1"}), llm=llm)
        await channel.handle_message(ChannelMessage("2", "telegram", "123", "/ask second", metadata={"chat_id": "1"}), llm=llm)

        assert llm.seen[0] == []
        assert llm.seen[1] == [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "reply:first"},
        ]

    asyncio.run(run())


def test_telegram_can_show_response_provider():
    from yantra.channels import ChannelMessage, TelegramChannel

    class FakeLLM:
        async def ask(self, prompt, history=None):
            class Response:
                text = f"reply:{prompt}"
                provider = "Tantra (Local NP-DNA)"
            return Response()

    async def run():
        channel = TelegramChannel()
        await channel.connect({"allowlist": "123", "chat_id": "1", "bot_token": "token", "show_provider": True})
        sent = []

        async def fake_send(message, chat_id="", **kwargs):
            sent.append(message)
            return True

        channel.send = fake_send
        await channel.handle_message(
            ChannelMessage("1", "telegram", "123", "/ask hi", metadata={"chat_id": "1"}),
            llm=FakeLLM(),
        )
        assert sent == ["reply:hi\n\nvia Tantra (Local NP-DNA)"]

    asyncio.run(run())
