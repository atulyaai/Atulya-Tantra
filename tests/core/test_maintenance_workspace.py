import asyncio
from types import SimpleNamespace

import pytest

from atulya.maintenance import Maintenance
from atulya.mcp_connections import MCPConnections


def test_protected_files_and_stale_proposals_are_never_overwritten(project_temp_dir):
    root = project_temp_dir / "project"
    path = root / "webui" / "controls.css"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"body {color:white}\r\n")
    manager = Maintenance(root, project_temp_dir / "data", project_temp_dir / "models")
    for name in [".env", "tools/bootstrap.py", "atulya/auth.py", "webui/scene/a.js",
                 "../webui/controls.css", str(path)]:
        with pytest.raises(ValueError):
            manager.read(name)
    proposal = manager.propose("webui/controls.css", "body {color:black}\n", "Improve contrast")
    assert path.read_bytes() == b"body {color:white}\r\n"
    path.write_text("changed by someone else", encoding="utf-8")
    with pytest.raises(ValueError, match="changed since"):
        manager.apply(proposal["id"])
    assert path.read_text() == "changed by someone else"


def test_review_apply_and_rollback_preserve_original_bytes(project_temp_dir):
    root = project_temp_dir / "project"
    path = root / "webui" / "controls.css"
    path.parent.mkdir(parents=True)
    original = b"body {color:white}\r\n"
    path.write_bytes(original)
    manager = Maintenance(root, project_temp_dir / "data", project_temp_dir / "models")
    proposal = manager.propose("webui/controls.css", "body {color:black}\n", "Contrast")
    assert manager.apply(proposal["id"])["state"] == "applied"
    assert path.read_bytes() == b"body {color:black}\n"
    assert manager.apply(proposal["id"], rollback=True)["state"] == "rolled_back"
    assert path.read_bytes() == original


def test_mcp_grants_are_required_and_rechecked_on_every_call(project_temp_dir, monkeypatch):
    calls = []
    class Client:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def list_tools(self):
            return SimpleNamespace(tools=[SimpleNamespace(name="echo", description="Echo", input_schema={"type": "object"})])
        async def call_tool(self, name, arguments):
            calls.append((name, arguments))
            return SimpleNamespace(is_error=False, content=[SimpleNamespace(type="text", text="confirmed")])
    import mcp
    monkeypatch.setattr(mcp, "Client", Client)
    async def exercise():
        manager = MCPConnections(project_temp_dir)
        with pytest.raises(ValueError):
            await manager.add("Bad", "https://user:password@example.org/mcp")
        item = await manager.add("Test", "https://example.org/mcp")
        await manager.discover(item["id"])
        with pytest.raises(ValueError, match="not been granted"):
            await manager.call(item["id"], "echo", {})
        await manager.grant(item["id"], "echo", True)
        assert "confirmed" in await manager.call(item["id"], "echo", {"value": "test"})
        await manager.grant(item["id"], "echo", False)
        with pytest.raises(ValueError):
            await manager.call(item["id"], "echo", {})
        assert len(calls) == 1
        await manager.remove(item["id"])
        assert manager.load() == []
    asyncio.run(exercise())
