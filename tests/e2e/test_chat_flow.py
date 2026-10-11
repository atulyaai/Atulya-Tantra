"""One end-to-end WebUI chat/API/archive flow with a deterministic model stub."""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import httpx
import pytest
from conftest import authenticate_test_admin

import atulya.server as server
from atulya.settings import Settings
from tools.plugins.brain import Brain, Message

if sys.platform == "win32":
    # Keep the test loop compatible with Windows' local async transports.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class DeterministicProvider:
    name = "E2E test provider"
    model = "stub"

    async def complete(self, messages: list[Message]) -> str:
        self.messages = list(messages)
        last_user = next(message.content for message in reversed(messages) if message.role == "user")
        return f"Atulya received: {last_user}"

    async def stream(self, messages: list[Message]):
        self.messages = list(messages)
        last_user = next(message.content for message in reversed(messages) if message.role == "user")
        yield "Atulya received: "
        yield last_user


def test_chat_reply_and_archives_are_separated_by_conversation(
    project_temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    models_dir = project_temp_dir / "models"
    models_dir.mkdir()
    settings = Settings(
        assistant_name="Atulya",
        host="127.0.0.1",
        port=8501,
        data_dir=project_temp_dir / "data",
        models_dir=models_dir,
        model_provider="",
        model_name="",
        model_base_url="",
        model_api_key="",
    )
    provider = DeterministicProvider()
    monkeypatch.setattr(server, "_make_brain", lambda _settings: Brain(provider, assistant_name="Atulya"))
    app = server.create_app(settings)

    async def exercise_flow() -> None:
        # ASGITransport executes the real API stack without opening a socket or
        # starting app lifespan integrations such as Telegram polling.
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            authenticate_test_admin(client, app)
            admin_conversation = "admin_e2e"
            other_conversation = "other_e2e"
            reply = await client.post(
                "/api/chat",
                json={
                    "conversation_id": admin_conversation,
                    "messages": [{"role": "user", "content": "Hello Atulya"}],
                },
            )
            assert reply.status_code == 200
            assert reply.json()["text"] == "Atulya received: Hello Atulya"
            assert reply.json()["provider"] == "E2E test provider"

            # Voice transcripts are posted to the same chat endpoint as typed
            # turns, so deterministic commands should resolve identically.
            calculated = await client.post(
                "/api/chat",
                json={
                    "conversation_id": admin_conversation,
                    "messages": [{"role": "user", "content": "calculate 24 * 7"}],
                },
            )
            assert calculated.status_code == 200
            assert calculated.json() == {"text": "168"}

            streamed = await client.post(
                "/api/chat",
                json={
                    "conversation_id": admin_conversation,
                    "messages": [{"role": "user", "content": "Stream this reply"}],
                    "stream": True,
                },
            )
            assert streamed.status_code == 200
            assert streamed.headers["content-type"].startswith("text/event-stream")
            events = [
                json.loads(line[6:])
                for line in streamed.text.splitlines()
                if line.startswith("data: ")
            ]
            assert "".join(event.get("text", "") for event in events) == "Atulya received: Stream this reply"
            assert events[-1]["done"] is True

            saved_memory = await client.post(
                "/api/memory", json={"conversation_id": admin_conversation, "fact": "My favorite color is blue"}
            )
            assert saved_memory.status_code == 201
            memory_reply = await client.post(
                "/api/chat",
                json={
                    "conversation_id": admin_conversation,
                    "messages": [{"role": "user", "content": "What is my favorite color?"}],
                },
            )
            assert memory_reply.status_code == 200
            assert any(
                message.role == "user" and "My favorite color is blue" in message.content
                for message in provider.messages
            )
            assert not any(
                message.role == "system" and "My favorite color is blue" in message.content
                for message in provider.messages
            )

            for conversation_id, suffix in ((admin_conversation, "admin"), (other_conversation, "other")):
                user_message = "Hello Atulya" if suffix == "admin" else "Private second conversation"
                assistant_message = "Atulya received: Hello Atulya" if suffix == "admin" else "Private reply"
                for message_id, role, content in (
                    (f"u_{suffix}", "user", user_message),
                    (f"a_{suffix}", "assistant", assistant_message),
                ):
                    saved = await client.post(
                        f"/api/conversations/{conversation_id}/messages",
                        json={"message_id": message_id, "role": role, "content": content},
                    )
                    assert saved.status_code == 204

            admin_history = await client.get(f"/api/conversations/{admin_conversation}")
            other_history = await client.get(f"/api/conversations/{other_conversation}")
            assert admin_history.status_code == other_history.status_code == 200
            assert [(item["role"], item["content"]) for item in admin_history.json()["messages"]] == [
                ("user", "Hello Atulya"),
                ("assistant", "Atulya received: Hello Atulya"),
            ]
            assert [(item["role"], item["content"]) for item in other_history.json()["messages"]] == [
                ("user", "Private second conversation"),
                ("assistant", "Private reply"),
            ]

            deleted = await client.delete(f"/api/conversations/{admin_conversation}")
            assert deleted.status_code == 200
            assert deleted.json()["deleted_messages"] == 2
            assert (await client.get(f"/api/conversations/{admin_conversation}")).json()["messages"] == []
            assert len((await client.get(f"/api/conversations/{other_conversation}")).json()["messages"]) == 2

    asyncio.run(exercise_flow())


def test_provider_failure_does_not_expose_secret_in_response_status_or_logs(
    project_temp_dir: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class FailingProvider:
        name = "Failure test provider"
        model = "stub"

        async def complete(self, _messages: list[Message]) -> str:
            raise RuntimeError("upstream failed with api_key=sk-test-secret-value")

    settings = Settings(
        assistant_name="Atulya", host="127.0.0.1", port=8501, data_dir=project_temp_dir / "data",
        models_dir=project_temp_dir / "models", model_provider="", model_name="", model_base_url="",
        model_api_key="",
    )
    monkeypatch.setattr(server, "_make_brain", lambda _settings: Brain(FailingProvider(), assistant_name="Atulya"))
    app = server.create_app(settings)

    async def exercise() -> tuple[str, str, str]:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            authenticate_test_admin(client, app)
            response = await client.post(
                "/api/chat", json={"messages": [{"role": "user", "content": "Hello"}]}
            )
            status = await client.get("/api/status")
            return response.text, status.text, caplog.text

    caplog.set_level(logging.DEBUG)
    response_text, status_text, logs = asyncio.run(exercise())
    assert "sk-test-secret-value" not in response_text + status_text + logs
    assert "model provider failed" in response_text.lower()
