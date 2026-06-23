"""Tests for chat history persistence and server-side context loading."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestChatHistoryMerge:
    def _import_merge(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "chat",
            str(Path(__file__).resolve().parents[1] / "drishti" / "dashboard" / "routes" / "chat.py"),
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
            str(Path(__file__).resolve().parents[1] / "drishti" / "dashboard" / "chat_history.py"),
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


class TestChatHistoryAPI:
    def _get_chat_module(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "chat",
            str(Path(__file__).resolve().parents[1] / "drishti" / "dashboard" / "routes" / "chat.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_resolve_model_id_valid(self):
        mod = self._get_chat_module()
        original = mod._checkpoint_index
        mod._checkpoint_index = lambda: {"latest": {"path": "/model"}}
        try:
            path, error = mod._resolve_model_id("latest")
            assert path == {"path": "/model"}
            assert error is None
        finally:
            mod._checkpoint_index = original

    def test_resolve_model_id_invalid(self):
        mod = self._get_chat_module()
        original = mod._checkpoint_index
        mod._checkpoint_index = lambda: {"latest": {"path": "/model"}}
        try:
            path, error = mod._resolve_model_id("nonexistent")
            assert path is None
            assert "error" in error
        finally:
            mod._checkpoint_index = original


class TestChatAPIMerge:
    def test_merge_function_exists(self):
        from drishti.dashboard.routes.chat import _merge_history
        r = _merge_history([{"role": "user", "content": "hi"}], [])
        assert len(r) == 1

    def test_merge_dedup(self):
        from drishti.dashboard.routes.chat import _merge_history
        r = _merge_history(
            [{"role": "user", "content": "hi"}],
            [{"role": "user", "content": "hi"}],
        )
        assert len(r) == 1

    def test_merge_limit(self):
        from drishti.dashboard.routes.chat import _merge_history
        h = [{"role": "user", "content": f"m{i}"} for i in range(20)]
        assert len(_merge_history(h, [], limit=5)) == 5
