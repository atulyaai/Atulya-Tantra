import json
import sys
from types import SimpleNamespace

import httpx
import pytest

from tools import device_companion
from tools.plugins.information import google_api
from tools.plugins.system.agents import AgentHub


def test_lost_receipt_response_retries_without_repeating_action():
    calls, receipts = [], []
    pending = {}
    first = True

    def handle(request):
        nonlocal first
        if request.url.path.endswith("/poll"):
            return httpx.Response(200, json={"jobs": [{"id": "one", "kind": "ping"}] if not calls else []})
        receipts.append(request.content)
        if first:
            first = False
            raise httpx.ReadError("Response lost after acceptance")
        return httpx.Response(200, json={"ok": True})

    def execute(kind, detail, folder):
        calls.append(kind)
        return "pong"

    with httpx.Client(base_url="https://test", transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(httpx.ReadError):
            device_companion.poll_once(client, pending=pending, executor=execute)
        assert device_companion.poll_once(client, pending=pending, executor=execute) == [{"id": "one", "success": True}]
    assert calls == ["ping"]
    assert receipts[0] == receipts[1]
    assert not pending


def test_duplicate_receipt_is_idempotent_but_cannot_change_outcome(project_temp_dir):
    hub = AgentHub(project_temp_dir)
    hub.pair("alice", "PC", ["ping"])
    job = hub.enqueue("alice", "PC", "ping")
    hub.poll("alice", "PC")
    assert hub.complete("alice", "PC", job["id"], "pong")
    assert hub.complete("alice", "PC", job["id"], "pong")
    assert not hub.complete("bob", "PC", job["id"], "pong")
    assert not hub.complete("alice", "PC", job["id"], "changed")


def test_missing_app_returns_a_failed_device_receipt(monkeypatch):
    from tools.plugins.system import actions
    monkeypatch.setattr(actions, "open_app", lambda name: "No installed app matches 'missing'.")
    results = []

    def handle(request):
        if request.url.path.endswith("/poll"):
            return httpx.Response(200, json={"jobs": [{"id": "one", "kind": "open_app", "detail": "missing"}]})
        results.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True})

    with httpx.Client(base_url="https://test", transport=httpx.MockTransport(handle)) as client:
        device_companion.poll_once(client)
    assert results[0]["success"] is False
    assert "No installed app" in results[0]["output"]


def test_camera_write_failure_cannot_claim_a_saved_photo(project_temp_dir, monkeypatch):
    released = []
    camera = SimpleNamespace(isOpened=lambda: True, read=lambda: (True, object()), release=lambda: released.append(True))
    monkeypatch.setitem(sys.modules, "cv2", SimpleNamespace(VideoCapture=lambda _: camera, imwrite=lambda *args: False))
    with pytest.raises(RuntimeError, match="could not be saved"):
        device_companion.execute("take_photo", "", project_temp_dir)
    assert released == [True]


def test_google_uses_data_directory_loaded_after_import(project_temp_dir, monkeypatch):
    monkeypatch.setenv("ATULYA_DATA_DIR", str(project_temp_dir))
    google_api.save_connection("alice", {"refresh_token": "test-refresh", "scope": google_api.READ})
    assert google_api.connection_status("alice")["connected"]
    assert (project_temp_dir / "google_tokens.json").is_file()


def test_device_capabilities_distinguish_pairing_from_a_live_connection(project_temp_dir, monkeypatch):
    from tools.plugins.registry import PluginContext, build_default_registry
    from tools.plugins.toolkit import Toolbox
    monkeypatch.setenv("ATULYA_DATA_DIR", str(project_temp_dir))
    hub = AgentHub(project_temp_dir)
    hub.pair("alice", "Phone", ["ping"])
    box = Toolbox.for_registry(build_default_registry(), PluginContext("alice", None, None, "alice"))
    rows = {row["name"]: row for row in box.capabilities}
    assert rows["ask_device"]["status"] == "needs_connection"
    assert "ping receipt" in rows["ask_device"]["next_step"]
    hub.poll("alice", "Phone")
    rows = {row["name"]: row for row in box.capabilities}
    assert rows["ask_device"]["status"] == "needs_approval"
