"""Devices: scan the network, add what is found, and control anything added (the dashboard uses these)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from atulya.devices.base import DeviceError
from atulya.devices.discovery import discover
from atulya.devices.hub import get_hub
from atulya.server.helpers import _require_admin, _require_auth

router = APIRouter()


@router.get("/api/fabric")
def api_fabric(user: dict = Depends(_require_auth)):
    return {"devices": get_hub().describe()}


@router.post("/api/fabric/discover")
async def api_fabric_discover(user: dict = Depends(_require_admin)):
    hub = get_hub()
    found = await discover(profiles=hub.profiles)
    have = {(d.driver, d.address, str(sorted(d.config.items()))) for d in hub.devices.values()}
    fresh = [c for c in found if (c.driver, c.host, str(sorted(c.config.items()))) not in have]
    hub.last_candidates = {c.id: c for c in fresh}
    hub.last_order = [c.id for c in fresh]
    return {"found": [c.to_dict() for c in fresh[:60]]}


@router.post("/api/fabric/add")
async def api_fabric_add(body: dict, user: dict = Depends(_require_admin)):
    try:
        dev = await get_hub().add_candidate(str(body.get("candidate", "")), str(body.get("name", "")), str(body.get("room", "")))
    except DeviceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": dev.id, "name": dev.name, "can": [c.name for c in dev.capabilities]}


@router.post("/api/fabric/{device_id}/do")
async def api_fabric_do(device_id: str, body: dict, user: dict = Depends(_require_auth)):
    hub = get_hub()
    action = str(body.get("action", ""))
    if hub.is_risky(device_id, action) and not body.get("confirmed"):
        raise HTTPException(status_code=409, detail="This needs your confirmation.")
    dev = hub.find(device_id)
    cap = dev.cap(action) if dev else None
    args = {}
    if cap and cap.params and str(body.get("value", "")).strip():
        args[next(iter(cap.params))] = body["value"]
    if body.get("times"):
        args["times"] = body["times"]
    try:
        return {"message": await hub.act(device_id, action, args)}
    except DeviceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/fabric/{device_id}")
def api_fabric_remove(device_id: str, user: dict = Depends(_require_admin)):
    try:
        return {"removed": get_hub().remove(device_id)}
    except DeviceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
