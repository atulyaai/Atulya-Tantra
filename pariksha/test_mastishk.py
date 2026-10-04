"""Tests for atulya/mastishk.py."""

import asyncio
import os

from fastapi.testclient import TestClient

from atulya.adhar import set_env_value
from atulya.mastishk import BY_ID, CATALOG


# ── test_providers ────────────────────────────────────────────────────────────
def test_catalog_is_consistent():
    ids = [s.id for s in CATALOG]
    assert len(ids) == len(set(ids)) and "mistral" in ids and "qwen" in ids and "anthropic" in ids
    assert all(s.base_url for s in CATALOG if not s.builtin and s.id != "custom")


def test_set_env_value_updates_adds_and_removes(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("# keep me\nA=1\nGROQ_API_KEY=old\n", encoding="utf-8")
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("MISTRAL_API_KEY", "placeholder")  # registers the restore, so set_env_value below cannot leak a key
    monkeypatch.delenv("MISTRAL_API_KEY")
    set_env_value("GROQ_API_KEY", "new", f)
    set_env_value("MISTRAL_API_KEY", "m", f)
    assert f.read_text().splitlines() == ["# keep me", "A=1", "GROQ_API_KEY=new", "MISTRAL_API_KEY=m"]
    set_env_value("A", "", f)
    assert "A=1" not in f.read_text() and "A" not in os.environ
    for bad in ("x\ny", "a=b\r"):
        try:
            set_env_value("K", bad, f)
        except ValueError:
            continue
        raise AssertionError("newline injection accepted")
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)


def test_generic_provider_follows_the_catalog(monkeypatch):
    from atulya.mastishk import OpenAICompatProvider, ProviderRouter

    p = OpenAICompatProvider(BY_ID["mistral"])
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    assert not p.is_available()
    monkeypatch.setenv("MISTRAL_API_KEY", "k")
    assert p.is_available() and p.URL == "https://api.mistral.ai/v1/chat/completions" and p.name() == "Mistral"
    monkeypatch.setenv("ATULYA_MISTRAL_MODEL", "a, b")
    assert p.models() == ["a", "b"]
    assert sum(isinstance(x, OpenAICompatProvider) for x in ProviderRouter().providers) >= 10


def test_routes_are_admin_only_and_never_return_keys(tmp_path, monkeypatch):
    import atulya.adhar as ef
    from atulya.dwar import ADMIN_TOKEN
    from atulya.sevak import app

    monkeypatch.setattr(ef, "env_path", lambda: tmp_path / ".env")
    monkeypatch.setattr("atulya.dwar.set_env_value", lambda k, v: ef.set_env_value(k, v, tmp_path / ".env"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    c = TestClient(app)
    assert c.get("/api/providers").status_code in (401, 403)
    h = {"X-Atulya-Token": ADMIN_TOKEN}
    r = c.post("/api/providers/deepseek", json={"key": "sk-secret-12345678"}, headers=h)
    assert r.status_code == 200 and r.json()["configured"] and "secret" not in r.text and r.json()["key_hint"] == "…5678"
    listing = c.get("/api/providers", headers=h)
    assert "sk-secret" not in listing.text
    body = listing.json()
    assert body["advice"] is None and "groq" in body["recommended"] and isinstance(body["brains"], list)   # a key is linked: no nagging
    assert c.post("/api/providers/nope", json={}, headers=h).status_code == 404
    assert c.post("/api/providers/deepseek/test", headers=h).status_code == 200
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)


# ── test_llm_bridge ────────────────────────────────────────────────────────────
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
    from atulya.mastishk import AtulyaLLM

    async def run():
        llm = AtulyaLLM()
        llm.router = FakeRouter()
        response = await llm.ask("hello", tools_enabled=False)
        assert response.text == "Final **answer** with `code`."
        assert response.provider == "fake"

    asyncio.run(run())


def test_llm_bridge_executes_tool_loop():
    from atulya.kaushal import Tool, ToolRegistry, ToolResult
    from atulya.mastishk import AtulyaLLM

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
    from atulya.kaushal import Tool, ToolRegistry
    from atulya.mastishk import AtulyaLLM

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
    from atulya.kaushal import Tool, ToolRegistry, ToolResult
    from atulya.mastishk import AtulyaLLM

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
    from atulya.kaushal import Tool, ToolRegistry, ToolResult
    from atulya.mastishk import AtulyaLLM

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
    from atulya.sandesh import ChannelMessage, TelegramChannel

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
    from atulya.sandesh import ChannelMessage, TelegramChannel

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
    from atulya.sandesh import ChannelMessage, TelegramChannel

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
    from atulya.sandesh import ChannelMessage, TelegramChannel

    class FakeLLM:
        async def ask(self, prompt, history=None):
            class Response:
                text = f"reply:{prompt}"
                provider = "Local GGUF"
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
        assert sent == ["reply:hi\n\nvia Local GGUF"]

    asyncio.run(run())



def test_speed_report_advises_a_fast_key_only_when_local_is_slow_and_no_cloud_is_linked():
    from atulya.mastishk import BY_ID, SLOW_SECONDS, speed_report

    speeds = {"Atulya Local (Qwen3-4B)": {"avg": 28.0}, "Groq": {"avg": 1.2}, "No brain loaded": {"avg": 0.0}}
    report = speed_report(speeds, linked_cloud=0)
    assert [r["name"] for r in report["brains"]] == ["Groq", "Atulya Local (Qwen3-4B)"]   # fastest first, no fake brain
    assert report["advice"]["kind"] == "slow_local" and report["advice"]["seconds"] == 28.0
    assert all(i in BY_ID for i in report["recommended"]) and report["recommended"][0] == "groq"
    assert speed_report(speeds, linked_cloud=1)["advice"] is None                      # a cloud key is linked: stay quiet
    fast = {"Atulya Local (Qwen3-0.6B)": {"avg": SLOW_SECONDS - 1}}
    assert speed_report(fast, linked_cloud=0)["advice"] is None                        # local is fast enough
    assert speed_report({}, linked_cloud=0)["advice"]["kind"] == "unmeasured"
    assert speed_report({}, linked_cloud=2)["advice"] is None
