"""Authenticated account ownership for persisted conversation data."""
from __future__ import annotations

import asyncio
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from atulya.history import ConversationHistory
from atulya.server import create_app
from atulya.settings import Settings
from tools.plugins.personal.memory import PersonalMemory
from tools.plugins.productivity.calendar import CalendarStore


def test_history_is_scoped_to_user_and_migrates_existing_rows(project_temp_dir: Path) -> None:
    db_path = project_temp_dir / "conversations.sqlite3"
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute("""CREATE TABLE messages (
            conversation_id TEXT NOT NULL, message_id TEXT NOT NULL,
            role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY(conversation_id,message_id))""")
        db.execute(
            "INSERT INTO messages VALUES(?,?,?,?,?)",
            ("legacy_chat", "legacy_message", "user", "keep this", "2025-01-01T00:00:00Z"),
        )
        db.execute(
            "INSERT INTO messages VALUES(?,?,?,?,?)",
            ("tg12345", "tg1", "user", "telegram history", "2025-01-01T00:00:00Z"),
        )

    history = ConversationHistory(project_temp_dir)
    assert history.read("legacy_chat", user_id="admin")[0]["content"] == "keep this"
    assert history.read("tg12345", user_id="tg_12345")[0]["content"] == "telegram history"

    history.append("shared", "same_message", "user", "admin only", user_id="admin")
    history.append("shared", "same_message", "user", "other user only", user_id="other")
    assert history.read("shared", user_id="admin")[0]["content"] == "admin only"
    assert history.read("shared", user_id="other")[0]["content"] == "other user only"
    assert history.delete("shared", user_id="other") == 1
    assert history.read("shared", user_id="admin")[0]["content"] == "admin only"


def test_memory_and_calendar_scope_records_by_account_and_migrate_telegram_data(project_temp_dir: Path) -> None:
    memory_path = project_temp_dir / "personal_memory.sqlite3"
    with closing(sqlite3.connect(memory_path)) as db, db:
        db.execute("""CREATE TABLE facts (
            id INTEGER PRIMARY KEY, owner TEXT NOT NULL, fact TEXT NOT NULL,
            created_at TEXT NOT NULL, UNIQUE(owner,fact))""")
        db.execute("INSERT INTO facts(owner,fact,created_at) VALUES('legacy_chat','legacy fact','2025-01-01T00:00:00Z')")
        db.execute("INSERT INTO facts(owner,fact,created_at) VALUES('tg12345','telegram fact','2025-01-01T00:00:00Z')")

    memories = PersonalMemory(project_temp_dir)
    assert memories.list("legacy_chat", user_id="admin") == ["legacy fact"]
    assert memories.list("tg12345", user_id="tg_12345") == ["telegram fact"]
    memories.remember("shared", "admin fact", user_id="admin")
    memories.remember("shared", "other fact", user_id="other")
    assert memories.list("shared", user_id="admin") == ["admin fact"]
    assert memories.list("shared", user_id="other") == ["other fact"]
    assert memories.forget("shared", "fact", user_id="other") == 1
    assert memories.list("shared", user_id="admin") == ["admin fact"]

    calendar_path = project_temp_dir / "calendar.sqlite3"
    with closing(sqlite3.connect(calendar_path)) as db, db:
        db.execute("""CREATE TABLE events (
            id INTEGER PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL,
            starts_at TEXT NOT NULL, reminder_minutes INTEGER NOT NULL DEFAULT 15,
            created_at TEXT NOT NULL)""")
        when = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(timespec="seconds")
        db.execute("INSERT INTO events(owner,title,starts_at,created_at) VALUES('tg12345','Legacy Telegram',?,'2025-01-01T00:00:00Z')", (when,))

    calendar = CalendarStore(project_temp_dir)
    assert calendar.list("tg12345", user_id="tg_12345")[0]["title"] == "Legacy Telegram"
    event = calendar.add("shared", "Admin event", datetime.now(timezone.utc) + timedelta(days=2), user_id="admin")
    assert calendar.list("shared", user_id="other") == []
    assert calendar.remove("shared", event["id"], user_id="other") is False
    assert calendar.list("shared", user_id="admin")[0]["title"] == "Admin event"


def test_private_conversation_api_uses_authenticated_user_scope(project_temp_dir: Path) -> None:
    settings = Settings(
        assistant_name="Atulya", host="127.0.0.1", port=8501,
        data_dir=project_temp_dir / "data", models_dir=project_temp_dir / "models",
        model_provider="", model_name="", model_base_url="", model_api_key="",
    )
    app = create_app(settings)

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as admin:
            admin.cookies.set("atulya_session", app.state.auth_store.create_session("admin"))
            other = httpx.AsyncClient(transport=transport, base_url="http://localhost")
            async with other:
                other.cookies.set("atulya_session", app.state.auth_store.create_session("other"))
                payload = {"message_id": "same_message", "role": "user", "content": "secret"}
                assert (await admin.post("/api/conversations/shared/messages", json=payload)).status_code == 204
                assert (await other.get("/api/conversations/shared")).json() == {"messages": []}
                assert (await admin.get("/api/conversations/shared")).json()["messages"][0]["content"] == "secret"

                memory_payload = {"conversation_id": "shared", "fact": "admin only"}
                assert (await admin.post("/api/memory", json=memory_payload)).status_code == 201
                assert (await other.get("/api/memory", params={"conversation_id": "shared"})).json() == {"facts": []}
                assert (await admin.get("/api/memory", params={"conversation_id": "shared"})).json() == {
                    "facts": ["admin only"]
                }

    asyncio.run(exercise())
