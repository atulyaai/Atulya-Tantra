from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()

_active_connections: set[WebSocket] = set()
_broadcast_history: list[dict[str, Any]] = []


@router.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _active_connections.add(websocket)

    # Send recent history
    for msg in _broadcast_history[-20:]:
        await websocket.send_json(msg)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
            # Handle ping/pong
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        _active_connections.discard(websocket)


async def broadcast(event_type: str, data: dict[str, Any]) -> None:
    payload = {"type": event_type, "data": data, "timestamp": time.time()}
    _broadcast_history.append(payload)
    if len(_broadcast_history) > 200:
        _broadcast_history[:] = _broadcast_history[-200:]

    disconnected = set()
    for ws in _active_connections:
        try:
            await ws.send_json(payload)
        except Exception:
            disconnected.add(ws)
    _active_connections.difference_update(disconnected)


async def broadcast_training(status: dict) -> None:
    await broadcast("training_status", status)


async def broadcast_telemetry(telemetry: dict) -> None:
    await broadcast("telemetry", telemetry)


async def broadcast_event(title: str, desc: str, event_type: str = "info") -> None:
    await broadcast("event", {"title": title, "desc": desc, "type": event_type})
