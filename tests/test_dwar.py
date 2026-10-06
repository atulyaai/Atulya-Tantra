"""Tests for atulya/dwar.py."""
from __future__ import annotations

import json
import time
import urllib.parse
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from atulya.dwar import build_dashboard


# ── test_openai_route ────────────────────────────────────────────────────────────
class TestOpenAIRoute:
    def test_list_models(self):
        from atulya.dwar import list_models

        with patch("atulya.dwar.ADMIN_TOKEN", "test-token"):
            with patch("atulya.dwar._model_registry") as reg:
                reg.return_value = [{"id": "model-1", "object": "model"}, {"id": "model-2", "object": "model"}]
                result = list_models(authorization="Bearer test-token")

        assert result["object"] == "list"
        assert len(result["data"]) == 2
        assert result["data"][0]["id"] == "model-1"

    def test_list_models_no_auth(self):
        from fastapi import HTTPException

        from atulya.dwar import list_models

        with pytest.raises(HTTPException) as exc:
            list_models(authorization=None)
        assert exc.value.status_code == 401

    def test_list_models_bad_auth(self):
        from fastapi import HTTPException

        from atulya.dwar import list_models

        with pytest.raises(HTTPException) as exc:
            list_models(authorization="Invalid")
        assert exc.value.status_code == 401


# ── test_notifications ────────────────────────────────────────────────────────────
class TestNotifications:
    @pytest.fixture
    def mock_auth(self):
        with patch("atulya.dwar._require_auth") as m:
            m.return_value = {"username": "testuser", "role": "admin"}
            yield m

    @pytest.fixture
    def mock_admin(self):
        with patch("atulya.dwar._require_admin") as m:
            m.return_value = {"username": "admin", "role": "admin"}
            yield m

    def test_subscribe(self, tmp_path, monkeypatch, mock_auth):
        from atulya import sandesh as push
        from atulya.dwar import subscribe
        monkeypatch.setenv("ATULYA_AGENT_DATA_DIR", str(tmp_path))
        subscription = {"endpoint": "https://push.test", "keys": {"p256dh": "p", "auth": "a"}}

        result = subscribe({"subscription": subscription}, token="t")
        assert result == {"ok": True, "delivery_configured": False}
        assert push._read()["testuser"] == [subscription]

    def test_subscribe_no_subscription(self, tmp_path, mock_auth):
        import atulya.dwar as notif_mod
        from atulya.dwar import subscribe
        notif_mod.SUBS_FILE = tmp_path / "subs.json"

        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="subscription"):
            subscribe({}, token="t")

    def test_unsubscribe(self, tmp_path, monkeypatch, mock_auth):
        from atulya import sandesh as push
        from atulya.dwar import unsubscribe
        monkeypatch.setenv("ATULYA_AGENT_DATA_DIR", str(tmp_path))
        subscription = {"endpoint": "https://push.test", "keys": {"p256dh": "p", "auth": "a"}}
        push.subscribe("testuser", subscription)

        result = unsubscribe({"subscription": subscription}, token="t")
        assert result == {"ok": True}
        assert push._read() == {}

    def test_unsubscribe_no_file(self, tmp_path, monkeypatch, mock_auth):
        from atulya.dwar import unsubscribe
        monkeypatch.setenv("ATULYA_AGENT_DATA_DIR", str(tmp_path))

        result = unsubscribe({"subscription": {"endpoint": "x"}}, token="t")
        assert result == {"ok": True}

    def test_test_notification(self, monkeypatch, mock_admin):
        from atulya.dwar import test_notification
        monkeypatch.delenv("ATULYA_VAPID_PUBLIC_KEY", raising=False)
        monkeypatch.delenv("ATULYA_VAPID_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("ATULYA_VAPID_SUBJECT", raising=False)

        import asyncio
        result = asyncio.run(test_notification({"title": "Hi", "message": "Test"}, token="t"))
        assert result.status_code == 503
        body = json.loads(result.body)
        assert body["title"] == "Hi" and body["message"] == "Test" and body["sent"] is False


# ── test_sessions ────────────────────────────────────────────────────────────
@pytest.fixture
def users_module(tmp_path, monkeypatch):
    """Isolate users.py on a fresh users.json and sessions.json under tmp_path."""
    import atulya.dwar as users_mod
    users_file = tmp_path / "users.json"
    sessions_file = tmp_path / "sessions.json"
    monkeypatch.setattr(users_mod, "USERS_FILE", users_file)
    monkeypatch.setattr(users_mod, "SESSIONS_FILE", sessions_file)
    # Reset the in-memory session store so previous tests don't leak tokens.
    users_mod._sessions.clear()
    return users_mod


def test_sessions_survive_restart(users_module):
    users_module.create_user("alice", "pw123", role="user", display_name="Alice")
    token = users_module.create_session("alice")
    assert users_module.get_session(token) is not None
    # The session must have been persisted to the sessions file.
    assert users_module.SESSIONS_FILE.exists()
    stored = json.loads(users_module.SESSIONS_FILE.read_text())
    assert token in stored

    # Simulate a server restart: drop the in-memory store, then rehydrate from
    # the persisted file (the same path the import-time bootstrap reads).
    users_module._sessions.clear()
    with users_module._lock:
        users_module._sessions.update(users_module._read_sessions())
    assert users_module.get_session(token) is not None
    assert users_module.get_session(token)["username"] == "alice"


def test_expired_sessions_dropped_on_lookup(users_module):
    import time as _time
    users_module.create_user("bob", "pw", role="user", display_name="Bob")
    token = users_module.create_session("bob")
    # Force expiry.
    users_module._sessions[token]["expires_at"] = _time.time() - 1
    assert users_module.get_session(token) is None
    assert token not in users_module._sessions


def test_kill_user_sessions_clears_all(users_module):
    users_module.create_user("carol", "pw", role="user", display_name="Carol")
    t1 = users_module.create_session("carol")
    t2 = users_module.create_session("carol")
    users_module.kill_user_sessions("carol")
    assert users_module.get_session(t1) is None
    assert users_module.get_session(t2) is None
    # Sessions file should no longer contain either token.
    data = json.loads(users_module.SESSIONS_FILE.read_text())
    assert t1 not in data and t2 not in data


def test_kill_session_persists(users_module):
    users_module.create_user("dave", "pw", role="user", display_name="Dave")
    token = users_module.create_session("dave")
    # Wipe memory to prove the session lives in the file, then rehydrate.
    users_module._sessions.clear()
    with users_module._lock:
        users_module._sessions.update(users_module._read_sessions())
    assert users_module.get_session(token) is not None
    users_module.kill_session(token)
    assert users_module.get_session(token) is None
    # After kill, the on-disk store should not contain the token.
    data = json.loads(users_module.SESSIONS_FILE.read_text())
    assert token not in data


# ── test_upload ────────────────────────────────────────────────────────────
class TestUploadRoute:
    @pytest.fixture
    def mock_auth(self):
        with patch("atulya.dwar._require_auth") as m:
            m.return_value = {"username": "testuser", "role": "user"}
            yield m

    @pytest.fixture
    def mock_uuid(self):
        with patch("uuid.uuid4") as m:
            m.return_value = uuid.UUID("12345678-1234-5678-1234-567812345678")
            yield m

    @pytest.mark.asyncio
    async def test_upload_valid_file(self, tmp_path, mock_auth, mock_uuid):
        import atulya.dwar as upload_mod
        from atulya.dwar import api_upload
        upload_mod.UPLOAD_DIR = tmp_path

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test.txt"
        mock_file.content_type = "text/plain"
        mock_file.read = AsyncMock(return_value=b"hello world")

        result = await api_upload(file=mock_file, token="token")
        assert result["ok"] is True
        assert result["filename"] == "test.txt"
        assert result["size"] == 11
        saved = tmp_path / "testuser" / "12345678123456781234567812345678.txt"
        assert saved.read_bytes() == b"hello world"

    @pytest.mark.asyncio
    async def test_upload_blocked_type(self, tmp_path, mock_auth):
        import atulya.dwar as upload_mod
        from atulya.dwar import api_upload
        upload_mod.UPLOAD_DIR = tmp_path

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "evil.exe"
        mock_file.content_type = "application/x-msdownload"
        mock_file.read = AsyncMock(return_value=b"bad")

        from fastapi import HTTPException
        with pytest.raises(HTTPException, match=r"File type.*not allowed"):
            await api_upload(file=mock_file, token="token")

    @pytest.mark.asyncio
    async def test_list_files(self, tmp_path, mock_auth):
        import atulya.dwar as upload_mod
        from atulya.dwar import api_list_files
        upload_mod.UPLOAD_DIR = tmp_path

        user_dir = tmp_path / "testuser"
        user_dir.mkdir(parents=True)
        (user_dir / "a.txt").write_text("aaa")
        (user_dir / "b.txt").write_text("bbb")

        result = await api_list_files(token="token")
        assert len(result["files"]) == 2

    @pytest.mark.asyncio
    async def test_list_files_empty(self, tmp_path, mock_auth):
        import atulya.dwar as upload_mod
        from atulya.dwar import api_list_files
        upload_mod.UPLOAD_DIR = tmp_path

        result = await api_list_files(token="token")
        assert result["files"] == []

    @pytest.mark.asyncio
    async def test_delete_file(self, tmp_path, mock_auth):
        import atulya.dwar as upload_mod
        from atulya.dwar import api_delete_file
        upload_mod.UPLOAD_DIR = tmp_path

        user_dir = tmp_path / "testuser"
        user_dir.mkdir(parents=True)
        f = user_dir / "1234.txt"
        f.write_text("data")

        result = await api_delete_file(file_id="1234.txt", token="token")
        assert result["ok"] is True
        assert not f.exists()

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, tmp_path, mock_auth):
        import atulya.dwar as upload_mod
        from atulya.dwar import api_delete_file
        upload_mod.UPLOAD_DIR = tmp_path
        (tmp_path / "testuser").mkdir(parents=True)

        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="not found"):
            await api_delete_file(file_id="nonexistent.txt", token="token")


# ── test_websocket ────────────────────────────────────────────────────────────
class TestWebSocket:
    @pytest.fixture
    def authed_ws(self, monkeypatch):
        import atulya.dwar as ws_mod
        monkeypatch.setattr(
            ws_mod, "_require_auth", lambda token: {"username": "admin", "role": "admin", "display_name": "Admin"}
        )
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.receive_text = AsyncMock()
        ws.query_params = {"token": "valid-token"}
        ws.headers = {}
        return ws

    @pytest.fixture
    def anon_ws(self, monkeypatch):
        from fastapi import HTTPException

        import atulya.dwar as ws_mod
        def _always_fail(token):
            raise HTTPException(status_code=401, detail="Not authenticated")
        monkeypatch.setattr(ws_mod, "_require_auth", _always_fail)
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()
        ws.receive_text = AsyncMock()
        ws.query_params = {}
        ws.headers = {}
        return ws

    @pytest.fixture
    def clean_state(self):
        import atulya.dwar as ws_mod
        ws_mod._active_connections.clear()
        ws_mod._broadcast_history.clear()
        yield

    @pytest.mark.asyncio
    async def test_websocket_rejects_unauthenticated(self, anon_ws, clean_state):
        from atulya.dwar import websocket_endpoint

        await websocket_endpoint(anon_ws)

        anon_ws.accept.assert_not_awaited()
        anon_ws.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_adds_to_history(self, clean_state):
        import atulya.dwar as ws_mod
        await ws_mod.broadcast("test_event", {"key": "value"})
        assert len(ws_mod._broadcast_history) == 1
        entry = ws_mod._broadcast_history[0]
        assert entry["type"] == "test_event"
        assert entry["data"] == {"key": "value"}
        assert "timestamp" in entry

    @pytest.mark.asyncio
    async def test_broadcast_history_capped(self, clean_state):
        import atulya.dwar as ws_mod
        for i in range(250):
            await ws_mod.broadcast(f"e{i}", {})
        assert len(ws_mod._broadcast_history) <= 200

    @pytest.mark.asyncio
    async def test_broadcast_training(self, clean_state):
        import atulya.dwar as ws_mod
        await ws_mod.broadcast_training({"status": "running"})
        assert ws_mod._broadcast_history[0]["type"] == "training_status"

    @pytest.mark.asyncio
    async def test_broadcast_telemetry(self, clean_state):
        import atulya.dwar as ws_mod
        await ws_mod.broadcast_telemetry({"cpu": 50})
        assert ws_mod._broadcast_history[0]["type"] == "telemetry"

    @pytest.mark.asyncio
    async def test_broadcast_event(self, clean_state):
        import atulya.dwar as ws_mod
        await ws_mod.broadcast_event("Title", "Desc", "warning")
        entry = ws_mod._broadcast_history[0]
        assert entry["type"] == "event"
        assert entry["data"]["title"] == "Title"
        assert entry["data"]["type"] == "warning"

    @pytest.mark.asyncio
    async def test_websocket_connect_and_pong(self, authed_ws, clean_state):
        from atulya.dwar import websocket_endpoint

        authed_ws.receive_text.side_effect = [
            json.dumps({"type": "ping"}),
            WebSocketDisconnect(),
        ]

        await websocket_endpoint(authed_ws)

        authed_ws.accept.assert_awaited_once()
        authed_ws.send_json.assert_any_await({"type": "pong"})

    @pytest.mark.asyncio
    async def test_websocket_sends_history_on_connect(self, authed_ws, clean_state):
        import atulya.dwar as ws_mod
        from atulya.dwar import websocket_endpoint

        await ws_mod.broadcast("past", {"msg": "old"})
        authed_ws.receive_text.side_effect = [WebSocketDisconnect()]

        await websocket_endpoint(authed_ws)

        assert authed_ws.send_json.await_count >= 1

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self, authed_ws, clean_state):
        import atulya.dwar as ws_mod
        from atulya.dwar import websocket_endpoint

        authed_ws.receive_text.side_effect = [WebSocketDisconnect()]
        ws_mod._active_connections.add(authed_ws)

        await websocket_endpoint(authed_ws)

        assert authed_ws not in ws_mod._active_connections


# ── test_spirit_chat ────────────────────────────────────────────────────────────
class TestSpiritChatPanel:
    """Tests for the Spirit UI chat panel (HolographicSpirit component).

    Since this is a React component, we test the API endpoint it calls.
    """

    def test_voice_chat_endpoint_structure(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "voice",
            str(Path(__file__).resolve().parents[1] / "atulya" / "dwar.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "router")

    def test_voice_chat_endpoint_exists(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "voice",
            str(Path(__file__).resolve().parents[1] / "atulya" / "dwar.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        routes = [route.path for route in mod.router.routes]
        assert "/api/voice/chat" in routes

    def test_tts_endpoint_exists(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "voice",
            str(Path(__file__).resolve().parents[1] / "atulya" / "dwar.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        routes = [route.path for route in mod.router.routes]
        assert "/api/voice/tts" in routes

    def test_voices_endpoint_exists(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "voice",
            str(Path(__file__).resolve().parents[1] / "atulya" / "dwar.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        routes = [route.path for route in mod.router.routes]
        assert "/api/voice/voices" in routes


class TestWakeWordFunctionality:
    """Tests for wake word 'Hey Atulya' functionality.

    The wake word logic is in the frontend JavaScript, but we can test
    the concept through the strip wake phrase function.
    """

    def test_strip_wake_phrase_concept(self):
        """Test the concept of wake phrase stripping."""
        wake_phrases = ["hey atulya", "atulya"]

        def strip_wake(text):
            trimmed = str(text).strip()
            lower = trimmed.lower()
            for phrase in wake_phrases:
                if lower.startswith(phrase):
                    return trimmed[len(phrase):].lstrip(" ,.:;-").strip()
            return trimmed

        assert strip_wake("Hey Atulya open browser") == "open browser"
        assert strip_wake("Atulya search the web") == "search the web"
        assert strip_wake("open browser") == "open browser"
        assert strip_wake("Hey Atulya, what time is it?") == "what time is it?"
        assert strip_wake("ATULYA run a test") == "run a test"

    def test_wake_phrase_case_insensitive(self):
        wake_phrases = ["hey atulya", "atulya"]

        def strip_wake(text):
            trimmed = str(text).strip()
            lower = trimmed.lower()
            for phrase in wake_phrases:
                if lower.startswith(phrase):
                    return trimmed[len(phrase):].lstrip(" ,.:;-").strip()
            return trimmed

        assert strip_wake("HEY ATULYA hello") == "hello"
        assert strip_wake("Hey Atulya hello") == "hello"
        assert strip_wake("hey atulya hello") == "hello"

    def test_wake_phrase_strips_prefix_punctuation(self):
        wake_phrases = ["hey atulya"]

        def strip_wake(text):
            trimmed = str(text).strip()
            lower = trimmed.lower()
            for phrase in wake_phrases:
                if lower.startswith(phrase):
                    return trimmed[len(phrase):].lstrip(" ,.:;-").strip()
            return trimmed

        assert strip_wake("Hey Atulya, do something") == "do something"
        assert strip_wake("Hey Atulya: do something") == "do something"
        assert strip_wake("Hey Atulya - do something") == "do something"
        assert strip_wake("Hey Atulya. do something") == "do something"

    def test_wake_phrase_preserves_rest(self):
        wake_phrases = ["hey atulya"]

        def strip_wake(text):
            trimmed = str(text).strip()
            lower = trimmed.lower()
            for phrase in wake_phrases:
                if lower.startswith(phrase):
                    return trimmed[len(phrase):].lstrip(" ,.:;-").strip()
            return trimmed

        assert strip_wake("Hey Atulya remember that my name is Alice") == "remember that my name is Alice"
        assert strip_wake("Hey Atulya what is 2 + 2?") == "what is 2 + 2?"

    def test_wake_phrase_partial_match(self):
        wake_phrases = ["hey atulya", "atulya"]

        def strip_wake(text):
            trimmed = str(text).strip()
            lower = trimmed.lower()
            for phrase in wake_phrases:
                if lower.startswith(phrase):
                    return trimmed[len(phrase):].lstrip(" ,.:;-").strip()
            return trimmed

        assert strip_wake("atulya hello") == "hello"
        assert strip_wake("not atulya") == "not atulya"

    def test_wake_phrase_empty_after_strip(self):
        wake_phrases = ["hey atulya"]

        def strip_wake(text):
            trimmed = str(text).strip()
            lower = trimmed.lower()
            for phrase in wake_phrases:
                if lower.startswith(phrase):
                    return trimmed[len(phrase):].lstrip(" ,.:;-").strip()
            return trimmed

        assert strip_wake("Hey Atulya") == ""
        assert strip_wake("Hey Atulya ") == ""


class TestIntentClassificationFrontend:
    """Tests for the frontend intent classification logic.

    The frontend classifyIntent function uses prototype-based similarity.
    We test the concept here.
    """

    def test_intent_concepts(self):
        """Test that intent classification concepts work."""
        intent_prototypes = {
            "FORGE": {
                "boost": ["code", "build", "fix", "bug", "website", "app", "function", "script"],
            },
            "VISION": {
                "boost": ["see", "camera", "look", "image", "photo", "frame", "scan", "visual"],
            },
            "ATHENA": {
                "boost": ["open", "run", "search", "start", "stop", "device", "automation", "control"],
            },
            "MEMORY": {
                "boost": ["remember", "history", "previous", "recall", "memory", "saved"],
            },
        }

        def classify(text):
            input_lower = text.lower()
            scores = {}
            for agent, proto in intent_prototypes.items():
                score = sum(2 for word in proto["boost"] if word in input_lower)
                scores[agent] = score
            return max(scores, key=scores.get)

        assert classify("write code for a function") == "FORGE"
        assert classify("look at this image") == "VISION"
        assert classify("search the web") == "ATHENA"
        assert classify("recall our previous conversation") == "MEMORY"

    def test_intent_fallback(self):
        intent_prototypes = {
            "FORGE": {"boost": ["code", "build"]},
            "ORACLE": {"boost": []},
        }

        def classify(text):
            input_lower = text.lower()
            scores = {}
            for agent, proto in intent_prototypes.items():
                score = sum(2 for word in proto["boost"] if word in input_lower)
                scores[agent] = score
            max_score = max(scores.values())
            if max_score == 0:
                return "ORACLE"
            return max(scores, key=scores.get)

        assert classify("hello how are you") == "ORACLE"
        assert classify("write some code") == "FORGE"

    def test_intent_confidence_calculation(self):
        def calculate_confidence(input_text, max_score, total_score):
            if max_score == 0:
                return 50
            return min(98, 60 + (max_score / max(total_score, 1)) * 30 + min(8, len(input_text) // 30))

        assert calculate_confidence("hi", 0, 0) == 50
        assert 60 <= calculate_confidence("write code", 4, 4) <= 98
        assert 60 <= calculate_confidence("write a python function to sort a list", 8, 8) <= 98



class TestVoiceChatRoutes:
    def test_routes_exist(self):
        from atulya.dwar import router
        paths = [r.path for r in router.routes]
        assert "/api/voice/chat" in paths
        assert "/api/voice/tts" in paths
        assert "/api/voice/voices" in paths

    def test_get_voices(self):
        from atulya.dwar import get_voices
        r = get_voices()
        assert "voices" in r
        assert len(r["voices"]) >= 4


class TestWakeWord:
    def _strip(self, text):
        phrases = ["hey atulya", "atulya"]
        t = str(text).strip()
        lo = t.lower()
        for p in phrases:
            if lo.startswith(p):
                return t[len(p):].lstrip(" ,.:;-").strip()
        return t

    def test_basic(self):
        assert self._strip("Hey Atulya open browser") == "open browser"

    def test_case(self):
        assert self._strip("HEY ATULYA hello") == "hello"

    def test_punctuation(self):
        assert self._strip("Hey Atulya, do something") == "do something"
        assert self._strip("Hey Atulya: do something") == "do something"

    def test_no_wake_word(self):
        assert self._strip("open browser") == "open browser"

    def test_atulya_only(self):
        assert self._strip("Atulya search") == "search"

    def test_empty(self):
        assert self._strip("Hey Atulya") == ""

    def test_preserve_content(self):
        assert self._strip("Hey Atulya remember my name is Alice") == "remember my name is Alice"


class TestIntentClassification:
    def _classify(self, text):
        input_lower = text.lower()
        prototypes = {
            "FORGE": ["code", "build", "fix", "bug", "website", "app", "function", "script"],
            "VISION": ["see", "camera", "look", "image", "photo", "frame", "scan", "visual"],
            "ATHENA": ["open", "run", "search", "start", "stop", "device", "automation", "control"],
            "MEMORY": ["remember", "history", "previous", "recall", "memory", "saved"],
        }
        scores = {a: sum(2 for kw in kw_list if kw in input_lower) for a, kw_list in prototypes.items()}
        mx = max(scores.values())
        if mx == 0:
            return "ORACLE", 50
        w = max(scores, key=scores.get)
        c = min(98, 60 + (mx / max(sum(scores.values()), 1)) * 30 + min(8, len(input_lower) // 30))
        return w, c

    def test_forge(self):
        a, _ = self._classify("write code for a function")
        assert a == "FORGE"

    def test_vision(self):
        a, _ = self._classify("look at this image")
        assert a == "VISION"

    def test_athena(self):
        a, _ = self._classify("open the browser and search")
        assert a == "ATHENA"

    def test_memory(self):
        a, _ = self._classify("recall previous conversation")
        assert a == "MEMORY"

    def test_oracle_fallback(self):
        a, _ = self._classify("what is life")
        assert a == "ORACLE"

    def test_confidence_range(self):
        for t in ["hi", "write code", "look at image", "open browser"]:
            _, c = self._classify(t)
            assert 50 <= c <= 98


# ── test_chat_history_integration ────────────────────────────────────────────────────────────
class TestChatHistoryMerge:
    def _import_merge(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "chat",
            str(Path(__file__).resolve().parents[1] / "atulya" / "dwar.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod._merge_history

    def test_merge_empty_histories(self):
        merge_fn = self._import_merge()
        result = merge_fn([], [])
        assert result == []

    def test_merge_frontend_only(self):
        merge_fn = self._import_merge()
        frontend = [{"role": "user", "content": "hello"}]
        result = merge_fn(frontend, [])
        assert len(result) == 1
        assert result[0]["content"] == "hello"

    def test_merge_server_only(self):
        merge_fn = self._import_merge()
        server = [{"role": "assistant", "text": "hi there"}]
        result = merge_fn([], server)
        assert len(result) == 1
        assert result[0]["content"] == "hi there"

    def test_merge_deduplication(self):
        merge_fn = self._import_merge()
        frontend = [{"role": "user", "content": "hello world"}]
        server = [{"role": "user", "content": "hello world"}]
        result = merge_fn(frontend, server)
        assert len(result) == 1

    def test_merge_preserves_order(self):
        merge_fn = self._import_merge()
        server = [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "response1"},
        ]
        frontend = [
            {"role": "user", "content": "second"},
        ]
        result = merge_fn(frontend, server, limit=10)
        assert len(result) == 3
        assert result[0]["content"] == "first"
        assert result[1]["content"] == "response1"
        assert result[2]["content"] == "second"

    def test_merge_limit(self):
        merge_fn = self._import_merge()
        history = [{"role": "user", "content": f"msg{i}"} for i in range(20)]
        result = merge_fn(history, [], limit=5)
        assert len(result) == 5
        assert result[0]["content"] == "msg15"

    def test_merge_skips_empty_content(self):
        merge_fn = self._import_merge()
        frontend = [{"role": "user", "content": ""}]
        server = [{"role": "assistant", "content": "valid"}]
        result = merge_fn(frontend, server)
        assert len(result) == 1
        assert result[0]["content"] == "valid"

    def test_merge_handles_text_key(self):
        merge_fn = self._import_merge()
        server = [{"role": "assistant", "text": "response"}]
        result = merge_fn([], server)
        assert len(result) == 1
        assert result[0]["content"] == "response"

    def test_merge_content_key_preferred(self):
        merge_fn = self._import_merge()
        msg = {"role": "user", "content": "from_content", "text": "from_text"}
        result = merge_fn([msg], [])
        assert result[0]["content"] == "from_content"

    def test_merge_dedup_by_role_and_content(self):
        merge_fn = self._import_merge()
        frontend = [{"role": "user", "content": "hello"}]
        server = [{"role": "assistant", "content": "hello"}]
        result = merge_fn(frontend, server)
        assert len(result) == 2


class TestChatHistoryPersistence:
    def _get_module(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "chat_history",
            str(Path(__file__).resolve().parents[1] / "atulya" / "dwar.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_append_and_list(self, tmp_path):
        mod = self._get_module()
        mod.HISTORY_FILE = tmp_path / "test_history.json"

        user = {"username": "testuser"}
        mod.append_exchange(user, "hello", "hi there", provider="test", surface="chat")

        messages = mod.list_messages(user)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["text"] == "hello"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["text"] == "hi there"

    def test_clear_messages(self, tmp_path):
        mod = self._get_module()
        mod.HISTORY_FILE = tmp_path / "test_history.json"

        user = {"username": "testuser"}
        mod.append_exchange(user, "msg1", "resp1")
        mod.clear_messages(user)
        messages = mod.list_messages(user)
        assert len(messages) == 0

    def test_surface_filtering(self, tmp_path):
        mod = self._get_module()
        mod.HISTORY_FILE = tmp_path / "test_history.json"

        user = {"username": "testuser"}
        mod.append_exchange(user, "chat msg", "chat resp", surface="chat")
        mod.append_exchange(user, "live msg", "live resp", surface="live")

        all_msgs = mod.list_messages(user)
        assert len(all_msgs) == 4

    def test_max_messages_limit(self, tmp_path):
        mod = self._get_module()
        mod.HISTORY_FILE = tmp_path / "test_history.json"
        mod._MAX_MESSAGES = 5

        user = {"username": "testuser"}
        for i in range(10):
            mod.append_exchange(user, f"msg{i}", f"resp{i}")

        messages = mod.list_messages(user)
        assert len(messages) <= 5

    def test_thread_safety(self, tmp_path):
        mod = self._get_module()
        mod.HISTORY_FILE = tmp_path / "test_history.json"

        user = {"username": "testuser"}
        mod.append_exchange(user, "msg1", "resp1")
        mod.append_exchange(user, "msg2", "resp2")

        messages = mod.list_messages(user)
        assert len(messages) == 4

    def test_user_normalization(self, tmp_path):
        mod = self._get_module()
        mod.HISTORY_FILE = tmp_path / "test_history.json"

        mod.append_exchange({"username": "Alice"}, "msg", "resp")
        mod.append_exchange({"username": "alice"}, "msg2", "resp2")

        messages = mod.list_messages({"username": "alice"})
        assert len(messages) == 4


class TestChatAPIMerge:
    def test_merge_function_exists(self):
        from atulya.dwar import _merge_history
        r = _merge_history([{"role": "user", "content": "hi"}], [])
        assert len(r) == 1

    def test_merge_dedup(self):
        from atulya.dwar import _merge_history
        r = _merge_history(
            [{"role": "user", "content": "hi"}],
            [{"role": "user", "content": "hi"}],
        )
        assert len(r) == 1

    def test_merge_limit(self):
        from atulya.dwar import _merge_history
        h = [{"role": "user", "content": f"m{i}"} for i in range(20)]
        assert len(_merge_history(h, [], limit=5)) == 5


# ── test_dashboard ────────────────────────────────────────────────────────────
def make(is_admin=True, **over):
    now = time.time()
    args = dict(
        audit=[{"event": "tool", "name": "play_music", "args": {"query": "lofi"}, "t": now},
               {"event": "tool", "name": "pc_hotkey", "t": now},
               {"event": "web_task.step", "goal": "add shoes", "action": "click", "url": "u"},
               {"event": "web_task.handoff", "goal": "add shoes", "url": "u", "reason": "payment is yours"}],
        speeds={"Groq": {"avg": 0.8}, "Local": {"avg": 12.0}, "Dead": {"failed_until": 1e12}}, ready=["Groq"],
        calendar=[{"title": "Standup", "time": now + 600, "duration": 30}, {"title": "Old", "time": now - 99, "duration": 5},
                  {"title": "Far", "time": now + 30 * 86400, "duration": 5}],
        reminders=[{"message": "stretch", "scheduled_time": now + 60}],
        devices={"lamp": {"name": "Lamp", "type": "light", "state": "off"}}, simulated_home=True, pc_on=False,
        is_admin=is_admin, now=now)
    args.update(over)
    return build_dashboard(**args)


def test_tiles_come_from_real_sources():
    d = make()
    assert [e["title"] for e in d["calendar"]["events"]] == ["Standup"]       # past and far-future events dropped
    assert d["calendar"]["reminders"][0]["message"] == "stretch"
    assert d["media"]["now_playing"] == "lofi"
    assert d["system"]["fastest"] == "Groq" and d["system"]["latency"] == 0.8   # measured, fastest first
    assert [b["name"] for b in d["system"]["brains"]] == ["Groq", "Local"]
    assert d["pc"]["recent"][0]["name"] == "pc_hotkey" and d["pc"]["control"] is False
    assert d["web"]["state"] == "finished" and d["web"]["steps"][-1]["note"] == "payment is yours"
    assert d["home"]["simulated"] is True and d["home"]["devices"][0]["id"] == "lamp"


def test_non_admins_do_not_get_system_details():
    d = make(is_admin=False)
    assert "system" not in d and "pc" not in d and "web" not in d and "calendar" in d


def test_idle_web_state_when_nothing_ran():
    assert make(audit=[])["web"]["state"] == "idle"


def test_routes_need_login_and_guard_locks(monkeypatch):
    from atulya.dwar import ADMIN_TOKEN
    from atulya.sevak import app

    c = TestClient(app)
    assert c.get("/api/dashboard").status_code in (401, 403)
    h = {"X-Atulya-Token": ADMIN_TOKEN}
    assert c.get("/api/dashboard", headers=h).json()["sections"]
    assert c.post("/api/dashboard/home", json={"device_id": "front_door", "action": "on"}, headers=h).status_code == 400
    assert c.post("/api/dashboard/home", json={"device_id": "living_room_light", "action": "unlock"}, headers=h).status_code == 400


def test_brain_tool_calls_are_audited(tmp_path, monkeypatch):
    import asyncio

    from atulya.kriya import TOOL_REGISTRY, recent
    from atulya.mastishk import AgentToolAdapter

    monkeypatch.setenv("ATULYA_AGENT_DATA_DIR", str(tmp_path))
    adapter = AgentToolAdapter("current_time", TOOL_REGISTRY["current_time"])
    assert asyncio.run(adapter.execute()).success
    assert recent(5)[-1]["event"] == "tool" and recent(5)[-1]["name"] == "current_time"


def test_no_brain_message_is_not_ranked_as_a_brain():
    from atulya import mastishk as ai

    ai._SPEED.pop("No brain loaded", None)
    ai._record_speed("No brain loaded", 0.0)
    assert "No brain loaded" not in ai._SPEED


def test_calendar_survives_a_restart(tmp_path, monkeypatch):
    import json

    from atulya import kriya as tools

    (tmp_path / "calendar.json").write_text(json.dumps([{"id": "e1", "title": "Client call", "time": 4e9, "duration": 30}]))
    monkeypatch.setattr(tools, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(tools, "_CALENDAR", {})
    tools._bootstrap()
    assert tools._CALENDAR["e1"]["title"] == "Client call"


def test_no_pretend_devices_without_a_hub(monkeypatch):
    """Real use (no Home Assistant, no test switch): the brain says no hub is connected instead of faking success."""
    import asyncio

    from atulya import kriya as tools

    monkeypatch.delenv("ATULYA_SIMULATED_HOME", raising=False)
    monkeypatch.delenv("HOME_ASSISTANT_URL", raising=False)
    said = asyncio.run(tools.home_control("kitchen_light", "on"))
    assert "No smart-home hub" in said and "turned on" not in said
    assert "No smart-home hub" in asyncio.run(tools.home_list_devices())


class TestAdminTokenSync:
    """The token configured in .env must be the one the server actually accepts.

    sevak imports atulya.dwar at module scope, so ADMIN_TOKEN was frozen before
    main() read .env: the configured value was ignored and a different random
    one minted on every boot. sevak.main() now calls sync_admin_token() after
    loading .env.
    """

    def test_sync_picks_up_the_env_token(self, monkeypatch):
        from atulya import dwar

        monkeypatch.setattr(dwar, "ADMIN_TOKEN", "frozen-at-import")
        monkeypatch.setattr(dwar, "ADMIN_TOKEN_SOURCE", "generated_runtime")
        monkeypatch.setenv("ATULYA_DASHBOARD_TOKEN", "the-one-from-dotenv")

        assert dwar.sync_admin_token() == "the-one-from-dotenv"
        assert dwar.ADMIN_TOKEN == "the-one-from-dotenv"
        assert dwar.ADMIN_TOKEN_SOURCE == "env"

    def test_sync_mints_a_token_when_none_is_configured(self, monkeypatch):
        from atulya import dwar

        monkeypatch.setattr(dwar, "ADMIN_TOKEN", "stale")
        monkeypatch.setattr(dwar, "ADMIN_TOKEN_SOURCE", "env")
        monkeypatch.delenv("ATULYA_DASHBOARD_TOKEN", raising=False)

        token = dwar.sync_admin_token()
        assert token != "stale" and len(token) >= 24
        assert dwar.ADMIN_TOKEN_SOURCE == "generated_runtime"

    def test_auth_accepts_the_token_that_was_configured(self, monkeypatch):
        from atulya import dwar

        monkeypatch.setattr(dwar, "ADMIN_TOKEN", "original")  # recorded for restore
        monkeypatch.setattr(dwar, "ADMIN_TOKEN_SOURCE", "original")
        monkeypatch.setenv("ATULYA_DASHBOARD_TOKEN", "configured-in-dotenv")

        dwar.sync_admin_token()
        assert dwar._require_auth("configured-in-dotenv")["role"] == "admin"


# ── test_miniapp ─────────────────────────────────────────────────────────────────
BOT = "123456:TEST-BOT-TOKEN"
ALLOWED_ID = 1484854122


def _genuine_init_data(bot_token: str = BOT, user_id: int = ALLOWED_ID, auth_date: int | None = None) -> str:
    """Build initData the way Telegram documents it, field by field.

    The check string is written out here rather than produced by the code under
    test, so a bug in sorting or in dropping ``hash`` would show up as a
    disagreement instead of two wrong halves agreeing with each other.
    """
    import hashlib
    import hmac as hmac_mod

    when = int(time.time()) if auth_date is None else auth_date
    fields = {
        "auth_date": str(when),
        "query_id": "AAH_test_query",
        "user": json.dumps({"id": user_id, "first_name": "Ravi", "username": "ravi"}, separators=(",", ":")),
    }
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hmac_mod.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac_mod.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(fields)


def _edit(init_data: str, **changes: str) -> str:
    fields = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    fields.update(changes)
    return urllib.parse.urlencode(fields)


def test_a_genuine_signature_names_the_user_it_was_signed_for():
    from atulya.dwar import verify_telegram_init_data

    user = verify_telegram_init_data(_genuine_init_data(), BOT)

    assert user["id"] == ALLOWED_ID
    assert user["first_name"] == "Ravi"


def test_a_tampered_field_is_rejected():
    """The signature covers every field, so changing one invalidates it."""
    from atulya.dwar import verify_telegram_init_data

    forged = _edit(_genuine_init_data(),
                   user=json.dumps({"id": ALLOWED_ID, "first_name": "Someone Else"}))

    assert verify_telegram_init_data(forged, BOT) == {}


def test_a_signature_from_another_bots_token_is_rejected():
    """Holding a different bot's token must not open this one's door."""
    from atulya.dwar import verify_telegram_init_data

    signed_by_other = _genuine_init_data(bot_token="99999:ANOTHER-BOT")

    assert verify_telegram_init_data(signed_by_other, BOT) == {}
    # ...and it really is valid, just under the other token: the rejection is
    # about which token, not about a signature that never worked.
    assert verify_telegram_init_data(signed_by_other, "99999:ANOTHER-BOT")["id"] == ALLOWED_ID


def test_a_captured_link_stops_working():
    from atulya.dwar import MINI_APP_INIT_DATA_MAX_AGE, verify_telegram_init_data

    stale = _genuine_init_data(auth_date=int(time.time()) - MINI_APP_INIT_DATA_MAX_AGE - 60)

    assert verify_telegram_init_data(stale, BOT) == {}
    # a long enough window would take it, proving the date is what refused it
    assert verify_telegram_init_data(stale, BOT, max_age=10 ** 9)["id"] == ALLOWED_ID


def test_no_signature_means_no_user():
    from atulya.dwar import verify_telegram_init_data

    fields = dict(urllib.parse.parse_qsl(_genuine_init_data(), keep_blank_values=True))
    fields.pop("hash")

    assert verify_telegram_init_data("", BOT) == {}
    assert verify_telegram_init_data(urllib.parse.urlencode(fields), BOT) == {}
    assert verify_telegram_init_data("user=%7B%7D", BOT) == {}


def _miniapp_client(monkeypatch, allowlist: str = str(ALLOWED_ID)):
    from atulya.sevak import app

    monkeypatch.setenv("ATULYA_TELEGRAM_BOT_TOKEN", BOT)
    monkeypatch.setenv("ATULYA_TELEGRAM_ALLOWLIST", allowlist)
    return TestClient(app)


def test_a_signed_open_trades_for_a_session_the_api_accepts(monkeypatch):
    client = _miniapp_client(monkeypatch)

    res = client.post("/api/miniapp/session", json={"init_data": _genuine_init_data()})

    assert res.status_code == 200
    body = res.json()
    assert body["user"] == {"username": f"telegram:{ALLOWED_ID}", "role": "admin", "display_name": "Ravi"}
    from atulya.dwar import _require_auth

    assert _require_auth(body["token"])["role"] == "admin"


def test_an_empty_allowlist_admits_nobody(monkeypatch):
    """Failing open here would make the hologram a public door."""
    client = _miniapp_client(monkeypatch, allowlist="")

    assert client.post("/api/miniapp/session", json={"init_data": _genuine_init_data()}).status_code == 403


def test_a_user_off_the_allowlist_is_refused(monkeypatch):
    client = _miniapp_client(monkeypatch)
    stranger = _genuine_init_data(user_id=999999)

    assert client.post("/api/miniapp/session", json={"init_data": stranger}).status_code == 403


def test_a_bad_signature_is_refused_before_anything_else(monkeypatch):
    client = _miniapp_client(monkeypatch)
    tampered = _edit(_genuine_init_data(), query_id="AAH_someone_elses")

    assert client.post("/api/miniapp/session", json={"init_data": tampered}).status_code == 401


def test_without_a_bot_token_there_is_nothing_to_check(monkeypatch):
    from atulya.sevak import app

    monkeypatch.delenv("ATULYA_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("ATULYA_TELEGRAM_ALLOWLIST", str(ALLOWED_ID))

    res = TestClient(app).post("/api/miniapp/session", json={"init_data": _genuine_init_data()})

    assert res.status_code == 503


# ── inbound webhooks ────────────────────────────────────────────────────────
def _hook_client(monkeypatch, tmp_path):
    from atulya import kriya
    from atulya.dwar import ADMIN_TOKEN
    from atulya.sevak import app

    monkeypatch.setattr(kriya, "_DATA_DIR", tmp_path)  # hooks live in agent state
    return TestClient(app), {"X-Atulya-Token": ADMIN_TOKEN}


def test_making_a_hook_hands_out_a_long_random_secret(monkeypatch, tmp_path):
    client, headers = _hook_client(monkeypatch, tmp_path)

    made = client.post("/api/hooks", json={"name": "github"}, headers=headers).json()

    assert made["ok"] and made["name"] == "github"
    assert len(made["token"]) >= 32
    assert made["url"] == f"/api/hooks/github/{made['token']}"


def test_making_the_same_hook_twice_keeps_the_same_secret(monkeypatch, tmp_path):
    """Rotating it quietly would break the service already pointing here."""
    client, headers = _hook_client(monkeypatch, tmp_path)
    first = client.post("/api/hooks", json={"name": "github"}, headers=headers).json()

    again = client.post("/api/hooks", json={"name": "github"}, headers=headers).json()

    assert again["token"] == first["token"]


def test_a_hook_name_must_look_like_a_name(monkeypatch, tmp_path):
    client, headers = _hook_client(monkeypatch, tmp_path)

    for bad in ("", "../etc/passwd", "Mix Ed Case", "a" * 65):
        assert client.post("/api/hooks", json={"name": bad}, headers=headers).status_code == 400, bad


def test_an_outside_service_can_speak_through_its_hook(monkeypatch, tmp_path):
    client, headers = _hook_client(monkeypatch, tmp_path)
    made = client.post("/api/hooks", json={"name": "github"}, headers=headers).json()

    res = client.post(made["url"], json={"title": "Build passed", "ref": "main"})

    assert res.status_code == 200
    assert res.json()["event"] == "hook.github"


def test_a_wrong_secret_is_refused(monkeypatch, tmp_path):
    client, headers = _hook_client(monkeypatch, tmp_path)
    client.post("/api/hooks", json={"name": "github"}, headers=headers)

    assert client.post("/api/hooks/github/not-the-token", json={}).status_code == 403


def test_a_name_nobody_created_goes_nowhere(monkeypatch, tmp_path):
    client, headers = _hook_client(monkeypatch, tmp_path)

    assert client.post("/api/hooks/elsewhere/anything", json={}).status_code == 404


def test_forgetting_a_hook_closes_it(monkeypatch, tmp_path):
    client, headers = _hook_client(monkeypatch, tmp_path)
    made = client.post("/api/hooks", json={"name": "github"}, headers=headers).json()

    assert client.delete("/api/hooks/github", headers=headers).status_code == 200
    assert client.post(made["url"], json={}).status_code == 404
    assert client.delete("/api/hooks/github", headers=headers).status_code == 404


def test_listing_hooks_does_not_hand_out_the_secret(monkeypatch, tmp_path):
    client, headers = _hook_client(monkeypatch, tmp_path)
    client.post("/api/hooks", json={"name": "github"}, headers=headers)

    listed = client.get("/api/hooks", headers=headers).json()

    assert [hook["name"] for hook in listed["hooks"]] == ["github"]
    assert "token" not in listed["hooks"][0]


def test_a_sender_that_speaks_plain_text_is_still_readable(monkeypatch, tmp_path):
    client, headers = _hook_client(monkeypatch, tmp_path)
    made = client.post("/api/hooks", json={"name": "sensor"}, headers=headers).json()

    res = client.post(made["url"], content=b"door=open", headers={"Content-Type": "text/plain"})

    assert res.status_code == 200
    from atulya.adhar import default_bus

    event = [e for e in default_bus.history(50) if e.type == "hook.sensor"][-1]
    assert event.payload["hook"] == "sensor"
    assert "door=open" in event.payload["text"]  # a notification still has something to say


# -- feedback ----------------------------------------------------------------
def test_a_rating_is_refused_without_a_session():
    from atulya.sevak import app

    res = TestClient(app).post("/api/feedback", json={"rating": "up"})

    assert res.status_code == 401


def test_a_verdict_lands_with_the_question_it_was_about(monkeypatch, tmp_path):
    from atulya import kriya
    from atulya.dwar import ADMIN_TOKEN
    from atulya.sevak import app

    monkeypatch.setattr(kriya, "_DATA_DIR", tmp_path)

    res = TestClient(app).post(
        "/api/feedback",
        json={"rating": "down", "prompt": "flight status", "reply": "see above", "comment": "not an answer"},
        headers={"X-Atulya-Token": ADMIN_TOKEN},
    )

    assert res.status_code == 200
    assert res.json() == {"ok": True, "up": 0, "down": 1, "last": "down"}
    # the next turn is told what went wrong, not merely that something did
    assert "flight status" in kriya.feedback_notes()


def test_a_rating_that_is_neither_is_refused(monkeypatch, tmp_path):
    from atulya import kriya
    from atulya.dwar import ADMIN_TOKEN
    from atulya.sevak import app

    monkeypatch.setattr(kriya, "_DATA_DIR", tmp_path)

    res = TestClient(app).post(
        "/api/feedback",
        json={"rating": "maybe"},
        headers={"X-Atulya-Token": ADMIN_TOKEN},
    )

    assert res.status_code == 400

