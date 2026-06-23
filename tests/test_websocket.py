"""Tests for WebSocket route — connect, broadcast, ping/pong."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.websockets import WebSocketDisconnect


class TestWebSocket:
    @pytest.fixture
    def ws_mock(self):
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.receive_text = AsyncMock()
        return ws

    @pytest.fixture
    def clean_state(self):
        import drishti.dashboard.routes.ws as ws_mod
        ws_mod._active_connections.clear()
        ws_mod._broadcast_history.clear()
        yield

    @pytest.mark.asyncio
    async def test_broadcast_adds_to_history(self, clean_state):
        import drishti.dashboard.routes.ws as ws_mod
        await ws_mod.broadcast("test_event", {"key": "value"})
        assert len(ws_mod._broadcast_history) == 1
        entry = ws_mod._broadcast_history[0]
        assert entry["type"] == "test_event"
        assert entry["data"] == {"key": "value"}
        assert "timestamp" in entry

    @pytest.mark.asyncio
    async def test_broadcast_history_capped(self, clean_state):
        import drishti.dashboard.routes.ws as ws_mod
        for i in range(250):
            await ws_mod.broadcast(f"e{i}", {})
        assert len(ws_mod._broadcast_history) <= 200

    @pytest.mark.asyncio
    async def test_broadcast_training(self, clean_state):
        import drishti.dashboard.routes.ws as ws_mod
        await ws_mod.broadcast_training({"status": "running"})
        assert ws_mod._broadcast_history[0]["type"] == "training_status"

    @pytest.mark.asyncio
    async def test_broadcast_telemetry(self, clean_state):
        import drishti.dashboard.routes.ws as ws_mod
        await ws_mod.broadcast_telemetry({"cpu": 50})
        assert ws_mod._broadcast_history[0]["type"] == "telemetry"

    @pytest.mark.asyncio
    async def test_broadcast_event(self, clean_state):
        import drishti.dashboard.routes.ws as ws_mod
        await ws_mod.broadcast_event("Title", "Desc", "warning")
        entry = ws_mod._broadcast_history[0]
        assert entry["type"] == "event"
        assert entry["data"]["title"] == "Title"
        assert entry["data"]["type"] == "warning"

    @pytest.mark.asyncio
    async def test_websocket_connect_and_pong(self, ws_mock, clean_state):
        from drishti.dashboard.routes.ws import websocket_endpoint

        ws_mock.receive_text.side_effect = [
            json.dumps({"type": "ping"}),
            WebSocketDisconnect(),
        ]

        await websocket_endpoint(ws_mock)

        ws_mock.accept.assert_awaited_once()
        ws_mock.send_json.assert_any_await({"type": "pong"})

    @pytest.mark.asyncio
    async def test_websocket_sends_history_on_connect(self, ws_mock, clean_state):
        from drishti.dashboard.routes.ws import websocket_endpoint
        import drishti.dashboard.routes.ws as ws_mod

        await ws_mod.broadcast("past", {"msg": "old"})
        ws_mock.receive_text.side_effect = [WebSocketDisconnect()]

        await websocket_endpoint(ws_mock)

        assert ws_mock.send_json.await_count >= 1

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self, ws_mock, clean_state):
        from drishti.dashboard.routes.ws import websocket_endpoint
        import drishti.dashboard.routes.ws as ws_mod

        ws_mock.receive_text.side_effect = [WebSocketDisconnect()]
        ws_mod._active_connections.add(ws_mock)

        await websocket_endpoint(ws_mock)

        assert ws_mock not in ws_mod._active_connections
