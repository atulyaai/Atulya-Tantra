from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException

from atulya.sevak.helpers import _require_admin

logger = logging.getLogger(__name__)
router = APIRouter()

from atulya.upakaran.controller import DeviceController

_controller = DeviceController(data_dir=Path(__file__).resolve().parents[3] / "data" / "devices")


@router.get("/api/devices")
def list_devices(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(token)
    return {"devices": [vars(d) for d in _controller._devices.values()]}


@router.post("/api/devices")
def add_device(body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(token)
    name = body.get("name", "").strip()
    device_type = body.get("device_type", "unknown")
    protocol = body.get("protocol", "wifi")
    address = body.get("address", "")
    port = int(body.get("port", 0))
    if not name:
        raise HTTPException(400, "Device name required")
    device_id = _controller.add_device(name, device_type, protocol, address, port)
    return {"ok": True, "device_id": device_id}


@router.post("/api/devices/{device_id}/command")
async def send_command(device_id: str, body: dict, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(token)
    command = body.get("command", "").strip()
    params = body.get("params")
    if not command:
        raise HTTPException(400, "Command required")
    result = await _controller.send_command(device_id, command, params)
    return result


@router.get("/api/devices/stats")
def device_stats(token: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(token)
    return _controller.get_stats()


@router.delete("/api/devices/{device_id}")
def delete_device(device_id: str, token: str | None = Header(default=None, alias="X-Atulya-Token")):
    _require_admin(token)
    if device_id not in _controller._devices:
        raise HTTPException(404, "Device not found")
    del _controller._devices[device_id]
    _controller._save()
    return {"ok": True}
