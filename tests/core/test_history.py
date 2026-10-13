import asyncio
from pathlib import Path

import httpx
import pytest
from conftest import authenticate_test_admin

from atulya.history import ConversationHistory
from atulya.server import create_app
from atulya.settings import Settings


def test_conversation_history_is_persistent_and_idempotent(project_temp_dir: Path) -> None:
    first = ConversationHistory(project_temp_dir)
    first.append("browser_1", "message_1", "user", "Hello")
    first.append("browser_1", "message_1", "user", "Hello")

    second = ConversationHistory(project_temp_dir)
    restored = second.read("browser_1")
    assert len(restored) == 1
    assert (restored[0]["message_id"], restored[0]["role"], restored[0]["content"]) == (
        "message_1",
        "user",
        "Hello",
    )


def test_conversation_history_delete_is_scoped_and_idempotent(project_temp_dir: Path) -> None:
    history = ConversationHistory(project_temp_dir)
    history.append("browser_1", "message_1", "user", "Private one")
    history.append("browser_2", "message_2", "user", "Private two")

    assert history.delete("browser_1") == 1
    assert history.delete("browser_1") == 0
    assert history.read("browser_1") == []
    assert [item["content"] for item in history.read("browser_2")] == ["Private two"]


def test_history_rejects_path_like_identifiers(project_temp_dir: Path) -> None:
    history = ConversationHistory(project_temp_dir)
    try:
        history.read("../private")
    except ValueError as exc:
        assert "identifiers" in str(exc)
    else:
        raise AssertionError("Invalid conversation IDs must be rejected")


def test_api_registers_chat_and_history_routes(project_temp_dir: Path) -> None:
    settings = Settings(
        assistant_name="Atulya",
        host="127.0.0.1",
        port=8501,
        data_dir=project_temp_dir,
        models_dir=project_temp_dir / "models",
        model_provider="",
        model_name="",
        model_base_url="",
        model_api_key="",
    )
    app = create_app(settings)
    routes = {
        (route.path, tuple(sorted(getattr(route, "methods", None) or ())))
        for route in app.routes
    }
    assert ("/api/chat", ("POST",)) in routes
    assert ("/api/conversations/{conversation_id}", ("GET",)) in routes
    assert ("/api/conversations/{conversation_id}", ("DELETE",)) in routes
    assert ("/api/conversations/{conversation_id}/messages", ("POST",)) in routes
    assert ("/api/status", ("GET",)) in routes
    assert ("/api/models/gesture/gesture_recognizer.task", ("GET",)) in routes


def test_gesture_model_is_served_from_project_model_directory(project_temp_dir: Path) -> None:
    models_dir = project_temp_dir / "models"
    model_path = models_dir / "gesture" / "gesture_recognizer.task"
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"local gesture model")
    from tools.bootstrap import MEDIAPIPE_FILES
    for name in MEDIAPIPE_FILES:
        asset = models_dir / "runtime" / "mediapipe" / name
        asset.parent.mkdir(parents=True, exist_ok=True)
        asset.write_bytes(b"test runtime asset")
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

    app = create_app(settings)

    async def fetch():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            authenticate_test_admin(client, app)
            response = await client.get("/api/models/gesture/gesture_recognizer.task")
            status_response = await client.get("/api/status")
            return response, status_response.json()

    response, status = asyncio.run(fetch())

    assert response.status_code == 200
    assert response.content == b"local gesture model"
    assert response.headers["content-type"] == "application/octet-stream"
    assert status["gesture"] == {"state": "ready", "label": "Model ready · awaiting camera"}


def test_api_rejects_untrusted_host_header(project_temp_dir: Path) -> None:
    settings = Settings(
        assistant_name="Atulya", host="127.0.0.1", port=8501, data_dir=project_temp_dir / "data",
        models_dir=project_temp_dir / "models", model_provider="", model_name="", model_base_url="",
        model_api_key="",
    )
    app = create_app(settings)

    async def fetch() -> int:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://attacker.example") as client:
            response = await client.get("/api/health")
            return response.status_code

    assert asyncio.run(fetch()) == 400


def test_environment_refuses_non_loopback_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATULYA_HOST", "0.0.0.0")
    try:
        Settings.from_environment()
    except ValueError as exc:
        assert "loopback" in str(exc)
    else:
        raise AssertionError("Unauthenticated service must not bind to a network interface")


def test_environment_requires_https_and_explicit_proxy_ips_for_public_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATULYA_PUBLIC_ORIGIN", "http://jarvis.example.test")
    try:
        Settings.from_environment()
    except ValueError as exc:
        assert "HTTPS origin" in str(exc)
    else:
        raise AssertionError("Remote public origins must use HTTPS")

    monkeypatch.setenv("ATULYA_PUBLIC_ORIGIN", "https://jarvis.example.test")
    monkeypatch.setenv("ATULYA_TRUSTED_PROXY_IPS", "*")
    try:
        Settings.from_environment()
    except ValueError as exc:
        assert "wildcard trust" in str(exc)
    else:
        raise AssertionError("Forwarded headers must not trust arbitrary senders")

    monkeypatch.setenv("ATULYA_TRUSTED_PROXY_IPS", "127.0.0.1")
    monkeypatch.setenv("ATULYA_ADMIN_SETUP_TOKEN", "short")
    with pytest.raises(ValueError, match="at least 32 characters"):
        Settings.from_environment()
    setup_token = "0123456789abcdef0123456789abcdef"
    monkeypatch.setenv("ATULYA_ADMIN_SETUP_TOKEN", setup_token)
    settings = Settings.from_environment()
    assert settings.public_origin == "https://jarvis.example.test"
    assert "jarvis.example.test" in settings.trusted_hosts
    assert setup_token not in repr(settings)


def test_mutating_api_rejects_cross_origin_request(project_temp_dir: Path) -> None:
    settings = Settings(
        assistant_name="Atulya", host="127.0.0.1", port=8501, data_dir=project_temp_dir / "data",
        models_dir=project_temp_dir / "models", model_provider="", model_name="", model_base_url="",
        model_api_key="",
    )
    app = create_app(settings)

    async def fetch() -> int:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            response = await client.post(
                "/api/memory", headers={"Origin": "https://attacker.example"},
                json={"conversation_id": "admin", "fact": "Do not save"},
            )
            return response.status_code

    assert asyncio.run(fetch()) == 403


def test_chat_api_enforces_per_ip_rate_limit_and_request_body_cap(project_temp_dir: Path) -> None:
    settings = Settings(
        assistant_name="Atulya", host="127.0.0.1", port=8501, data_dir=project_temp_dir / "data",
        models_dir=project_temp_dir / "models", model_provider="", model_name="", model_base_url="",
        model_api_key="",
    )
    app = create_app(settings)

    async def exercise() -> tuple[int, int]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            authenticate_test_admin(client, app)
            statuses = []
            for _ in range(21):
                response = await client.post(
                    "/api/chat", json={"messages": [{"role": "user", "content": "Hello"}]}
                )
                statuses.append(response.status_code)
            oversized = await client.post("/api/chat", content=b"x" * (3 * 1024 * 1024 + 1))
            return statuses[-1], oversized.status_code

    assert asyncio.run(exercise()) == (429, 413)


def test_tables_missing_created_at_default_are_repaired(project_temp_dir) -> None:
    import sqlite3
    from contextlib import closing

    from tools.plugins.personal.memory import PersonalMemory

    path = project_temp_dir / "personal_memory.sqlite3"
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("CREATE TABLE facts (id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, owner TEXT NOT NULL, "
                   "fact TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(user_id, owner, fact))")
        db.execute("INSERT INTO facts(user_id,owner,fact,created_at) VALUES('admin','web','old fact','2026-01-01')")
    memory = PersonalMemory(project_temp_dir)
    assert memory.remember("web", "new fact", user_id="admin") is True
    assert set(memory.list("web", user_id="admin")) == {"old fact", "new fact"}


def test_merging_chat_memories_with_duplicates_does_not_crash(project_temp_dir) -> None:
    import sqlite3
    from contextlib import closing

    from atulya.server import _merge_web_owners
    from tools.plugins.personal.memory import PersonalMemory

    memory = PersonalMemory(project_temp_dir)
    memory.remember("chatA", "likes chai", user_id="admin")
    memory.remember("chatB", "likes chai", user_id="admin")
    memory.remember("tg123", "telegram fact", user_id="tg_123")
    _merge_web_owners(project_temp_dir)
    with closing(sqlite3.connect(project_temp_dir / "personal_memory.sqlite3")) as db:
        rows = sorted(db.execute("SELECT owner, fact FROM facts").fetchall())
    assert rows == [("tg123", "telegram fact"), ("web", "likes chai")]


def test_encrypted_backup_round_trip(project_temp_dir, monkeypatch) -> None:
    import sqlite3
    from contextlib import closing

    import pytest

    from tools import backup

    monkeypatch.delenv("ATULYA_BACKUP_KEY", raising=False)
    with closing(sqlite3.connect(project_temp_dir / "memo.sqlite3")) as db, db:
        db.execute("CREATE TABLE t(x)")
        db.execute("INSERT INTO t VALUES ('keep me')")
    path, created = backup.create(project_temp_dir)
    assert created and b"keep me" not in path.read_bytes()          # encrypted at rest
    key = backup.recovery_key()
    with pytest.raises(Exception):
        backup.decrypt(path, "A" * 43)                               # wrong key fails
    (project_temp_dir / "memo.sqlite3").unlink()
    assert "memo.sqlite3" in backup.restore(path, key, project_temp_dir)
    with closing(sqlite3.connect(project_temp_dir / "memo.sqlite3")) as db:
        assert db.execute("SELECT x FROM t").fetchone()[0] == "keep me"
