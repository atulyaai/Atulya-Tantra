"""Built-in command registry tests; no provider or network calls."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
import asyncio
import httpx
from conftest import authenticate_test_admin

from tools.plugins.personal.memory import PersonalMemory
from tools.plugins.productivity.calendar import CalendarStore
from tools.plugins.registry import PluginContext, PluginRegistry, build_default_registry
from atulya.server import create_app
from atulya.settings import Settings


def _run_immediate(coroutine):
    """Run a no-I/O command coroutine without creating a Windows event loop."""
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    raise AssertionError("Built-in deterministic command unexpectedly suspended")


def test_default_registry_dispatches_shared_memory_calendar_and_utility_commands(project_temp_dir: Path) -> None:
    registry = build_default_registry()
    context = PluginContext(
        "test_user", PersonalMemory(project_temp_dir / "data"), CalendarStore(project_temp_dir / "data")
    )

    async def exercise() -> None:
        assert await registry.dispatch("remember that I prefer concise answers", context) == "I'll remember that."
        recalled = await registry.dispatch("what do you remember about answers", context)
        assert recalled is not None and "I prefer concise answers" in recalled
        assert await registry.dispatch("calculate 24 * 7", context) == "168"
        assert await registry.dispatch("what time is it", context)
        assert await registry.dispatch("this is ordinary chat", context) is None
        future = (datetime.now().astimezone() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
        added = await registry.dispatch(f"add meeting: Registry check | {future}", context)
        assert added is not None and "Meeting added: Registry check" in added
        listed = await registry.dispatch("my meetings", context)
        assert listed is not None and "Registry check" in listed

    _run_immediate(exercise())
    assert {manifest["id"] for manifest in registry.manifests} == {
        "personal-memory", "productivity-calendar", "online-information", "local-utilities"
    }


def test_registry_rejects_duplicate_manifest_ids(project_temp_dir: Path) -> None:
    manifest = project_temp_dir / "plugin.json"
    manifest.write_text(
        '{"id":"sample","name":"Sample","version":"1","category":"test",'
        '"commands":[],"permissions":[],"enabled":true}',
        encoding="utf-8",
    )

    async def no_op(_command: str, _context: PluginContext) -> None:
        return None

    registry = PluginRegistry()
    registry.register(manifest, no_op)
    with pytest.raises(ValueError, match="Duplicate plugin id"):
        registry.register(manifest, no_op)


def test_registry_skips_disabled_plugin(project_temp_dir: Path) -> None:
    manifest = project_temp_dir / "plugin.json"
    manifest.write_text(
        '{"id":"sample","name":"Sample","version":"1","category":"test",'
        '"commands":[],"permissions":[],"enabled":false}',
        encoding="utf-8",
    )

    async def handler(_command: str, _context: PluginContext) -> str:
        return "should not run"

    registry = PluginRegistry()
    registry.register(manifest, handler)
    assert registry.manifests == [{
        "id": "sample", "name": "Sample", "version": "1", "category": "test",
        "commands": [], "permissions": [], "enabled": False,
    }]
    registry.set_enabled("sample", True)
    assert registry.manifests[0]["enabled"] is True
    registry.set_enabled("sample", False)
    assert registry.manifests[0]["enabled"] is False
    with pytest.raises(ValueError, match="Unknown"):
        registry.set_enabled("missing-plugin", True)


def test_builtin_plugin_settings_persist_through_local_api(project_temp_dir: Path) -> None:
    settings = Settings(
        assistant_name="Atulya", host="127.0.0.1", port=8501,
        data_dir=project_temp_dir / "data", models_dir=project_temp_dir / "models",
        model_provider="", model_name="", model_base_url="", model_api_key="",
    )
    app = create_app(settings)

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            authenticate_test_admin(client, app)
            initial = await client.get("/api/plugins")
            assert initial.status_code == 200
            assert all(plugin["enabled"] for plugin in initial.json()["plugins"])
            updated = await client.post("/api/plugins/online-information", json={"enabled": False})
            assert updated.status_code == 200
            assert updated.json()["plugin"]["enabled"] is False
            assert (project_temp_dir / "data" / "plugin_settings.json").is_file()
            missing = await client.post("/api/plugins/unknown-plugin", json={"enabled": True})
            assert missing.status_code == 404

    asyncio.run(exercise())
