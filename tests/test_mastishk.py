"""Tests for atulya/mastishk/."""

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


def test_telegram_start_replies_to_allowlisted_owner():
    from atulya.sandesh import ChannelMessage, TelegramChannel

    async def run():
        channel = TelegramChannel()
        await channel.connect({"allowlist": "123", "bot_token": "test-token"})
        sent = []

        async def fake_send(message, chat_id="", **kwargs):
            sent.append((message, chat_id))
            return True

        channel.send = fake_send
        result = await channel.handle_message(
            ChannelMessage("1", "telegram", "123", "/start", metadata={"chat_id": "456"}))
        assert result == "help"
        # The wording gains commands over time (/send, /link, …), so assert what
        # a user needs to be told rather than pinning the whole sentence.
        assert len(sent) == 1
        text, chat_id = sent[0]
        assert chat_id == "456"
        assert text.startswith("Atulya OS is online.")
        for command in ("/ask", "/status", "/help"):
            assert command in text

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
        assert sent == ["Atulya is working on it...", "reply:status"]

    asyncio.run(run())


def test_telegram_brain_failure_is_logged(caplog):
    from atulya.sandesh import ChannelMessage, TelegramChannel

    class BrokenLLM:
        async def ask(self, prompt, history=None):
            raise RuntimeError("brain offline")

    async def run():
        channel = TelegramChannel()
        await channel.connect({"allowlist": "123", "bot_token": "test-token"})

        async def fake_send(*args, **kwargs):
            return True

        channel.send = fake_send
        return await channel.handle_message(
            ChannelMessage("1", "telegram", "123", "hello", metadata={"chat_id": "10"}), BrokenLLM())

    with caplog.at_level("ERROR", logger="atulya.sandesh"):
        assert asyncio.run(run()) == "brain_error"
    assert "Telegram message handling failed" in caplog.text
    assert "RuntimeError: brain offline" in caplog.text


def test_telegram_preserves_sender_history(monkeypatch):
    from atulya import dwar
    from atulya.sandesh import ChannelMessage, TelegramChannel

    # The channel loads any disk-backed history on first contact; this test is
    # about continuity between two turns, so start from a clean slate instead of
    # whatever the real kosh/ happens to hold.
    monkeypatch.setattr(dwar, "list_messages", lambda user, limit=20: [])

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

        # This test is about in-memory continuity between two turns.
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
        assert sent == ["Atulya is working on it...", "reply:hi\n\nvia Local GGUF"]

    asyncio.run(run())


def test_telegram_approval_is_one_shot_and_bound_to_sender():
    from atulya.sandesh import ChannelMessage, TelegramChannel

    pending = {"tool": "pc_open_app", "arguments": {"app": "calculator"}}

    class FakeLLM:
        def __init__(self):
            self.approved = []

        async def ask(self, prompt, history=None, **kwargs):
            self.approved.append(kwargs.get("approved_tool_call"))

            class Response:
                needs_approval = not bool(kwargs.get("approved_tool_call"))
                pending_tool = pending if needs_approval else None
                text = "Opening calculator."
                provider = "fake"
            return Response()

    async def run():
        channel = TelegramChannel()
        await channel.connect({"allowlist": "123,456", "bot_token": "test-token"})
        sent = []

        async def fake_send(message, chat_id="", **kwargs):
            sent.append((message, chat_id))
            return True

        channel.send = fake_send
        llm = FakeLLM()
        first = ChannelMessage("1", "telegram", "123", "open calculator", metadata={"chat_id": "10"})
        assert await channel.handle_message(first, llm) == "approval_requested"
        other = ChannelMessage("2", "telegram", "456", "yes", metadata={"chat_id": "20"})
        assert await channel.handle_message(other, llm) == "no_pending_approval"
        yes = ChannelMessage("3", "telegram", "123", "yes", metadata={"chat_id": "10"})
        assert await channel.handle_message(yes, llm) == "approved"
        assert llm.approved == [None, pending]
        assert await channel.handle_message(yes, llm) == "no_pending_approval"

    asyncio.run(run())


def test_telegram_voice_approval_avoids_a_text_working_message():
    from atulya.sandesh import ChannelMessage, TelegramChannel

    pending = {"tool": "pc_open_app", "arguments": {"app": "calculator"}}

    class FakeLLM:
        async def ask(self, prompt, history=None, **kwargs):
            class Response:
                text = "Opening calculator."
                tool_steps = []
            return Response()

    async def run():
        channel = TelegramChannel()
        await channel.connect({"allowlist": "123", "bot_token": "test-token"})
        channel._reply_modes["123"] = True
        channel._pending_approvals["123"] = (pending, __import__("time").time() + 60)
        sent = []
        spoken = []

        async def fake_send(message, chat_id="", **kwargs):
            sent.append(message)
            return True

        async def fake_speak(text, chat_id):
            spoken.append(text)
            return True

        channel.send = fake_send
        channel._speak_reply = fake_speak
        result = await channel.handle_message(
            ChannelMessage("2", "telegram", "123", "yes", metadata={"chat_id": "10"}), FakeLLM())
        assert result == "approved"
        assert sent == []
        assert spoken == ["Opening calculator."]

    asyncio.run(run())


def test_openrouter_image_analysis_skips_models_without_image_support(monkeypatch):
    from atulya.mastishk import OpenRouterProvider

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ATULYA_OPENROUTER_MODEL", "text-only,vision-model")
    provider = OpenRouterProvider()
    calls = []

    def fake_ask_image(model, prompt, image_bytes, mime_type):
        calls.append((model, prompt, image_bytes, mime_type))
        if model == "text-only":
            raise RuntimeError("model does not support images")
        return "A test image description."

    monkeypatch.setattr(provider, "_ask_image", fake_ask_image)

    async def run():
        result = await provider.analyze_image("What is this?", b"image-bytes", "image/png")
        assert result == "A test image description."

    asyncio.run(run())
    assert [call[0] for call in calls] == ["text-only", "vision-model"]
    assert all(call[1:] == ("What is this?", b"image-bytes", "image/png") for call in calls)


def test_telegram_photo_download_uses_largest_photo(monkeypatch):
    from atulya.sandesh import ChannelMessage, TelegramChannel

    async def run():
        channel = TelegramChannel()
        seen = []

        async def fake_download(file_id, announced_size=0, max_bytes=20 * 1024 * 1024):
            seen.append((file_id, announced_size))
            return b"photo", "photos/image.jpg"

        channel._download_file = fake_download
        message = ChannelMessage("1", "telegram", "123", "", metadata={"raw": {"message": {
            "photo": [{"file_id": "small", "file_size": 100}, {"file_id": "large", "file_size": 500}],
        }}})
        image, mime_type = await channel._download_image(message)
        assert image == b"photo" and mime_type == "image/jpeg"
        assert seen == [("large", 500)]

    asyncio.run(run())


def test_telegram_streams_plain_chat_into_one_editable_message():
    from atulya.mastishk import LLMEvent
    from atulya.sandesh import ChannelMessage, TelegramChannel

    class FakeLLM:
        async def stream(self, prompt, history=None, tools_enabled=True):
            assert tools_enabled is False
            yield LLMEvent("token", content="A streamed ")
            yield LLMEvent("token", content="answer.")
            yield LLMEvent("done", metadata={"provider": "OpenRouter"})

        async def remember(self, prompt, answer):
            self.remembered = (prompt, answer)

    async def run():
        channel = TelegramChannel()
        await channel.connect({"allowlist": "123", "bot_token": "test-token"})
        sent = []
        edits = []

        async def fake_send_id(text, chat_id):
            sent.append((text, chat_id))
            return 99

        async def fake_edit(chat_id, message_id, text):
            edits.append((chat_id, message_id, text))
            return True

        async def fake_send(message, chat_id="", **kwargs):
            sent.append((message, chat_id))
            return True

        channel._send_text_with_id = fake_send_id
        channel._edit_text = fake_edit
        channel.send = fake_send
        llm = FakeLLM()
        result = await channel.handle_message(
            ChannelMessage("1", "telegram", "123", "What is 2 plus 2?", metadata={"chat_id": "10"}), llm)
        assert result == "answered"
        assert edits[-1] == ("10", 99, "A streamed answer.")
        assert len(edits) == 1
        assert llm.remembered == ("What is 2 plus 2?", "A streamed answer.")

    asyncio.run(run())


def test_telegram_remembers_user_facts_and_persists_sender_history(tmp_path, monkeypatch):
    import atulya.dwar as history_store
    from atulya.buddhi import ProfileStore
    from atulya.sandesh import ChannelMessage, TelegramChannel

    monkeypatch.setenv("ATULYA_PROFILE_DIR", str(tmp_path / "profiles"))
    monkeypatch.setenv("ATULYA_VAULT_DIR", str(tmp_path / "vault"))
    monkeypatch.setattr(history_store, "HISTORY_FILE", tmp_path / "chat_history.json")

    class FakeLLM:
        async def ask(self, prompt, history=None, **kwargs):
            raise AssertionError("a direct profile statement should not need the model")

    async def run():
        channel = TelegramChannel()
        await channel.connect({"allowlist": "123", "bot_token": "test-token"})
        sent = []

        async def fake_send(message, chat_id="", **kwargs):
            sent.append((message, chat_id))
            return True

        async def fake_send_id(message, chat_id):
            return 99

        async def fake_edit(chat_id, message_id, message):
            sent.append((message, chat_id))
            return True

        async def quiet_typing(chat_id):
            return None

        channel.send = fake_send
        channel._send_text_with_id = fake_send_id
        channel._edit_text = fake_edit
        channel._keep_typing = quiet_typing
        result = await channel.handle_message(ChannelMessage(
            "1", "telegram", "123", "I'm Ananya",
            metadata={"chat_id": "10", "raw": {"message": {"from": {
                "id": 123, "first_name": "Ananya", "username": "ananya"}}}},
        ), FakeLLM())
        return channel, result, sent

    channel, result, sent = asyncio.run(run())
    assert result == "answered"
    assert "remember" in sent[-1][0].lower()
    profile = ProfileStore(tmp_path / "profiles").view("telegram:123")
    assert any(fact["key"] == "name" and fact["value"] == "Ananya" for fact in profile["facts"])
    messages = history_store.list_messages({"username": "telegram:123"})
    # The store keeps the raw reply; Telegram receives it HTML-escaped, so the
    # two agree once the escape is undone.
    from html import unescape

    assert [row["text"] for row in messages[-2:]] == ["I'm Ananya", unescape(sent[-1][0])]
    assert channel._telegram_identity(ChannelMessage(
        "2", "telegram", "123", "", metadata={"raw": {"message": {"from": {"first_name": "Ananya"}}}},
    ))["display_name"] == "Ananya"


def test_long_term_recall_is_scoped_to_the_current_user(tmp_path):
    from atulya.bhava import current_user
    from atulya.mastishk import AtulyaLLM

    async def run():
        llm = AtulyaLLM(use_memory=True, memory_dir=str(tmp_path / "memory"))
        token = current_user.set("alice")
        await llm._store_exchange("My private phrase is silver maple", "I will remember silver maple.")
        current_user.reset(token)

        token = current_user.set("bob")
        bob_results = await llm._retrieve_memory_context("private phrase silver maple")
        current_user.reset(token)
        token = current_user.set("alice")
        alice_results = await llm._retrieve_memory_context("private phrase silver maple")
        current_user.reset(token)
        await llm._memory.close()
        return bob_results, alice_results

    bob_results, alice_results = asyncio.run(run())
    assert bob_results == []
    assert any("silver maple" in item for item in alice_results)


def test_streaming_chat_retrieves_scoped_memory_and_stores_reply(tmp_path):
    from atulya.bhava import current_user
    from atulya.mastishk import AtulyaLLM

    class StreamRouter:
        def __init__(self):
            self.prompt = ""

        async def stream(self, prompt, system_prompt="", preferred_provider=""):
            self.prompt = prompt
            yield "You said silver maple.", "test"

    async def run():
        llm = AtulyaLLM(use_memory=True, memory_dir=str(tmp_path / "memory"))
        llm.router = StreamRouter()
        token = current_user.set("alice")
        await llm._store_exchange("My private phrase is silver maple", "I will remember silver maple.")
        events = [event async for event in llm.stream("What did I say about my private phrase?", tools_enabled=False)]
        recalled = "silver maple" in llm.router.prompt
        stored = await llm._retrieve_memory_context("What did I say about my private phrase?", limit=10)
        current_user.reset(token)
        await llm._memory.close()
        return events, recalled, stored

    events, recalled, stored = asyncio.run(run())
    assert recalled
    assert events[-1].type == "done"
    assert any("You said silver maple" in item for item in stored)


def test_telegram_unchanged_stream_edit_does_not_trigger_duplicate_send(monkeypatch):
    import atulya.sandesh as channels
    from atulya.sandesh import TelegramChannel

    async def fake_post(url, payload, timeout=10.0):
        return 400, {"ok": False, "description": "Bad Request: message is not modified"}

    async def run():
        channel = TelegramChannel()
        await channel.connect({"bot_token": "test-token"})
        monkeypatch.setattr(channels, "_post_json", fake_post)
        return await channel._edit_text("10", 99, "Same final answer")

    assert asyncio.run(run()) is True


def test_telegram_file_send_is_disabled_without_explicit_opt_in(monkeypatch):
    from atulya.sandesh import ChannelMessage, TelegramChannel

    monkeypatch.delenv("ATULYA_TELEGRAM_ALLOW_SEND", raising=False)
    monkeypatch.delenv("ATULYA_ALLOWED_FOLDERS", raising=False)

    async def run():
        channel = TelegramChannel()
        await channel.connect({"allowlist": "123", "bot_token": "test-token"})
        sent = []

        async def fake_send(message, chat_id="", **kwargs):
            sent.append(message)
            return True

        channel.send = fake_send
        result = await channel.handle_message(
            ChannelMessage("1", "telegram", "123", '/send "C:\\private\\file.pdf"', metadata={"chat_id": "10"}))
        assert result == "file_send_denied"
        assert "ATULYA_ALLOWED_FOLDERS" in sent[-1]

    asyncio.run(run())


def test_telegram_long_poll_http_timeout_exceeds_telegram_wait(monkeypatch):
    from atulya.sandesh import TelegramChannel
    import atulya.sandesh as channels

    seen = {}

    async def fake_get(url, params, timeout):
        seen.update(url=url, params=params, timeout=timeout)
        return 200, {"ok": True, "result": []}

    async def run():
        channel = TelegramChannel()
        await channel.connect({"bot_token": "test-token"})
        assert await channel.receive() == []

    monkeypatch.setattr(channels, "_get_json", fake_get)
    asyncio.run(run())
    assert seen["params"]["timeout"] == 30
    assert seen["timeout"] > seen["params"]["timeout"]


def test_server_telegram_polling_loop_repeats_and_cancels_cleanly():
    from atulya.sevak import _poll_telegram

    class FakeChannel:
        def __init__(self):
            self.calls = 0
            self.called = asyncio.Event()

        async def poll_and_reply(self, llm=None):
            self.calls += 1
            self.called.set()

    async def run():
        channel = FakeChannel()
        task = asyncio.create_task(_poll_telegram(channel, llm=None))
        await asyncio.wait_for(channel.called.wait(), timeout=1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert channel.calls == 1

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


def test_loading_the_local_model_does_not_freeze_the_server(tmp_path, monkeypatch):
    """The model takes seconds to load. It must load off the event loop, or the screen cannot even open meanwhile."""
    import asyncio
    import time

    from atulya.mastishk import LocalGGUFProvider

    provider = LocalGGUFProvider(tmp_path / "fake.gguf")
    monkeypatch.setattr(provider, "_load", lambda: time.sleep(0.4))
    monkeypatch.setattr(provider, "_complete", lambda kwargs: {"choices": [{"message": {"content": "hi"}}]})

    async def scenario():
        ticks = 0

        async def ticker():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.02)
                ticks += 1

        task = asyncio.create_task(ticker())
        answer = await provider.chat("hello", "system")
        task.cancel()
        return answer, ticks

    answer, ticks = asyncio.run(scenario())
    assert answer == "hi"
    assert ticks >= 8   # the loop kept running while the 0.4 s load happened (blocked loop: 0-1 ticks)


def test_confirmations_for_file_and_pc_tools_are_readable():
    from atulya.mastishk import describe_action

    assert describe_action("file_write", {"path": "notes.txt"}) == "write the file notes.txt"
    assert describe_action("file_edit", {"path": "a.py"}) == "change the file a.py"
    assert describe_action("pc_screenshot", {}) == "take a screenshot of your screen"
    assert describe_action("exec", {"command": "dir"}) == "run this on your computer: dir"


# -- feedback reaches the next turn -----------------------------------------
def test_what_the_user_complained_about_reaches_the_next_turn(monkeypatch, tmp_path):
    from atulya import kriya, mastishk

    monkeypatch.setattr(kriya, "_DATA_DIR", tmp_path)
    kriya.record_feedback("down", "flight status", "", "too brief")

    notes = mastishk._recent_feedback()

    assert "flight status" in notes and "too brief" in notes


def test_a_good_answer_teaches_nothing(monkeypatch, tmp_path):
    from atulya import kriya, mastishk

    monkeypatch.setattr(kriya, "_DATA_DIR", tmp_path)
    kriya.record_feedback("up", "what is 2+2", "four")

    assert mastishk._recent_feedback() == ""


def test_an_unreadable_feedback_file_costs_a_lesson_not_a_reply(monkeypatch):
    from atulya import kriya, mastishk

    def boom(name):
        raise RuntimeError("disk gone")

    monkeypatch.setattr(kriya, "_load_json", boom)

    assert mastishk._recent_feedback() == ""
